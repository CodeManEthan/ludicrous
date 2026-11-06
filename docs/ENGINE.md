# Headless Engine (`engine/`)

The `engine` package is the games' backend: pure Python, no GUI imports. It
simulates games and emits an **event log** — a complete recording that any
frontend (the web UI, the CLI, tests) can replay at any speed without
re-running the simulation.

## Layout

```
engine/
├── __init__.py    # public exports: WarGame, BlackjackGame, run_batch, events, …
├── cards.py       # Card (rank, suit), deck/shoe building
├── events.py      # event dataclasses (the recording format)
├── war.py         # WarGame: rules, state, event emission
├── blackjack.py   # BlackjackGame: rules, Strategy interface, STRATEGIES registry
└── batch.py       # parallel batch simulation + aggregation for both games
```

## Usage

```python
from engine import WarGame

game = WarGame(num_players=6, num_decks=3, seed=42)
summary = game.run()          # simulate to completion
print(summary["winner_name"], summary["rounds"])

# ...or drive it round by round:
game = WarGame(num_players=4, seed=7)
while not game.is_over:
    round_events = game.play_round()   # events for just this round
```

`seed` makes games fully reproducible: same seed, same game, same event log.

CLI harness:

```bash
python3 simulate.py -p 100 -d 50 --seed 42 --random-names
python3 simulate.py -p 6 -d 3 --json recording.json   # save a recording
python3 simulate.py -p 4 --batch 1000 --seed 0        # 1,000-game statistics
python3 -m unittest discover        # run the engine test suite
```

## Blackjack and the Strategy interface

`BlackjackGame(num_seats, num_decks=6, num_rounds=100, strategies=[...], seed)`
plays a session of flat-bet rounds at one table against the dealer. Rules:
dealer stands on all 17s, blackjack pays 3:2, dealer peeks, double on any
first two cards including after a split (DAS). Pairs of equal-value cards
may be split up to 4 hands per seat, each with a fresh 1-unit bet; split
aces get exactly one card each, can't be resplit, and a split 21 is not a
blackjack. No insurance or surrender yet.

A **strategy** is an object with
`decide(hand, dealer_up_value, can_double, can_split=False) ->
"hit" | "stand" | "double" | "split"` — it sees one hand's cards and the
dealer upcard. Strategies are registered by name in `STRATEGIES` (`basic`,
`never-bust`, `hit-below-15/16/17`) and assigned to seats round-robin, so
one table can race strategies under identical conditions.
`summary()["per_strategy"]` reports hands, net units, and EV per hand for
each — "hands" counts *original* hands (one per seat per round), so EV is
per initial bet, the same basis as published house-edge figures.

Blackjack events: `StrategiesAssigned`, `ShoeShuffled`, `CardDealt` (seat 0 =
dealer; `hand` = hand index within the seat), `SeatAction`, `HandSplit`
(the last card of hand `hand` moves to new hand `new_hand` — replayers must
move it, it is not re-dealt), `DealerRevealed`, `HandResult` (one per hand),
`RoundSettled` (cumulative bankrolls — the frontend's bankroll chart series).

Validation note: over ten million seeded hands, `basic` (with pair
splitting) measures ≈ **-0.5%** EV per hand, matching the published
full-basic ≈ -0.55%, and `hit-below-17` (≈ mimic-the-dealer) measures
≈ **-5.7%** vs the published ≈ -5.5% — the engine reproduces the casino
math. Before splitting was implemented, `basic` measured ≈ -1.0%; the
missing-splits cost accounted for the gap, as predicted.

## Batch simulation

`run_batch(players, decks, games, base_seed)` fans games out across CPU cores
with `ProcessPoolExecutor`, one summary row per game. Games are seeded
`base_seed .. base_seed+N-1`, so every batch is reproducible and any game in
it can be replayed individually from its seed. Workers run with
`record_events=False`: the event log is skipped entirely (headline stats are
tracked inline on the game object), which keeps workers fast and memory-flat.
`summarize_batch(rows)` aggregates: round distribution
(min/max/mean/median/stdev), wins by seat, war stats, and the
shortest/longest games with their seeds. War games stopped by the
`max_rounds` safety cap are counted as `unfinished` and excluded from the
distribution statistics (capped values would bias them low); they remain in
the outlier lists with `completed=False`.

`run_blackjack_batch(seats, decks, rounds, games, strategies, base_seed)` is
the blackjack equivalent (one row per session);
`summarize_blackjack_batch(rows)` aggregates per-strategy hands/net/EV, the
session-net distribution, and the best/worst sessions with their seeds.

## Event vocabulary

| Event | Fields (beyond `round`, `type`) | Meaning |
|---|---|---|
| `GameStarted` | num_players, num_decks, player_names, seed | game configured |
| `CardsDealt` | card_counts | shoe shuffled and dealt |
| `RoundStarted` | players | players participating this round |
| `CardPlayed` | player, card, face_up | a card placed on the table |
| `WarDeclared` | players, rank, depth, tiebreaker | tie at the highest rank |
| `PlayerEliminated` | player, reason | `out_of_cards` or `insufficient_for_war` |
| `RoundWon` | winner, cards_won, via | `high_card`, `war`, or `forfeit` |
| `RoundDrawn` | players, cards_returned | drawn war: table split evenly |
| `RoundEnded` | card_counts | per-player counts after the round |
| `GameOver` | winner, total_rounds | one player holds every card |

JSON recording format (produced by `simulate.py --json`):

```json
{
  "summary": { "winner": 5, "rounds": 1507, "wars": 129, "standings": [5, 2, ...] },
  "events": [
    { "type": "RoundStarted", "round": 1, "players": [1, 2, 3] },
    { "type": "CardPlayed", "round": 1, "player": 1, "card": [14, "Hearts"], "face_up": true },
    ...
  ]
}
```

Notes: cards serialize as `[rank, suit]` pairs; dict keys (player ids) become
strings in JSON. `RoundEnded.card_counts` gives the frontend a free
card-count-over-time series for charts.

## Rules parity with the retired tkinter version

The rules are a faithful port of the original tkinter app's
`war_game_logic.py` (retired; preserved in git history at the "Snapshot:
final tkinter version" commit), including all five tiebreaker types (Default,
Forfeit, Modified, Modified Forfeit, Draw), reserve-deck reshuffling, and even
table splits on drawn wars. Two deliberate differences:

1. **All cards are dealt.** The GUI dropped remainder cards when the deck
   didn't divide evenly (e.g. 3 players, 52 cards → 1 card unused). The
   engine deals round-robin so every card is in play; hands may differ by
   one card.
2. **Wars resolve within `play_round()`.** The GUI required a button click
   per tiebreaker stage. The engine finishes the whole round in one call —
   the event log preserves every war stage for playback.

## Testing

`tests/test_engine.py` covers deck composition, dealing, each tiebreaker
path (rigged decks force wars/forfeits/draws), card conservation after every
round, determinism of seeded games, full games completing with the winner
holding all cards, and JSON serializability of recordings.
