# Headless Engine (`engine/`)

The `engine` package is the game's backend: pure Python, no tkinter, no GUI
imports. It simulates games and emits an **event log** — a complete recording
that any frontend (the upcoming web UI, the CLI, tests) can replay at any
speed without re-running the simulation.

## Layout

```
engine/
├── __init__.py    # public exports: WarGame, Card, build_shoe, events
├── cards.py       # Card (rank, suit), deck/shoe building
├── events.py      # event dataclasses (the recording format)
└── war.py         # WarGame: rules, state, event emission
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
python3 -m unittest discover        # run the engine test suite
```

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
