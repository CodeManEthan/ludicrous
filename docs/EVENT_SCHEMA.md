---
type: repo-doc
project: ludicrous
description: "The frozen v1 event-log recording contract: every event type and field, the exact JSON encoding rules, per-round ordering guarantees, which fields the web frontend reads, the recording envelopes that carry events, and the v1 seed contract that makes a recording reproducible."
tags: [reference, contract, simulation]
updated: 2026-08-25
---

# Event log schema (v1)

The Python engine in `engine/` records a game as a list of events. That list is
the whole recording: the web frontend, the CLI, and the test suite replay it
without re-running the simulation. This document freezes the format so a
recording written today still replays in any client that speaks v1, and so the
Rust core in `core-rs/` has a normative target to match byte for byte.

**v1 is frozen.** Do not rename a field, change a field's type, reorder a
dataclass, or change the RNG call sequence without cutting a v2. Adding a new
event type or a new trailing field is the only safe change, and even that
invalidates every stored golden fixture. `tests/test_golden.py` fails when the
bytes move, which is the point.

## What produces a recording

Two entry points emit v1 recordings, and both serialize the same events.

`simulate.py --json PATH` writes a two-key envelope:

```json
{"summary": {...}, "events": [{...}, {...}]}
```

`POST /api/simulate` in `server.py` returns a richer envelope for the browser:

| Key | Type | Present when |
|---|---|---|
| `game` | `"war"` or `"blackjack"` | always |
| `summary` | object | always — the same object `simulate.py` stores |
| `stats` | object | always — headline numbers the UI shows without scanning events |
| `names` | object, id → name | always |
| `strategies` | object, seat → strategy name | blackjack only |
| `mode` | `"full"` or `"condensed"` | always |
| `events` | array of events | `mode == "full"` |
| `chart` | `{rounds: [...], series: {id: [...]}}` | `mode == "condensed"` |
| `eliminations` | `[{round, player}]` | `mode == "condensed"`, war only |

The server streams a game round by round and drops each round's events after
harvesting them. It keeps the full list only while the count stays within
`FULL_EVENT_BUDGET` (250,000 events, roughly 25 MB of JSON). The first round
that pushes the count past the budget switches the response to
`mode: "condensed"` and discards the events entirely — a condensed response
carries no `events` key at all, so a client must branch on `mode` rather than
probe for the key. Condensed responses replace playback with a downsampled
chart of at most `CHART_POINTS` (1200) samples per player, built from
`RoundEnded.card_counts` for war and `RoundSettled.bankrolls` for blackjack.

Responses are gzipped when the request's `Accept-Encoding` allows it. That is
transport only; the decoded bytes are the contract.

`POST /api/batch` returns statistics, not events. Batch games run with
`record_events=False`, so no event log exists for them.

## JSON encoding rules

These rules are what "byte-identical" means. A reimplementation that gets the
values right and the encoding wrong still breaks every replay client.

1. **The serializer is `json.dumps` with CPython defaults.** UTF-8 output,
   `ensure_ascii=True`, separators `", "` and `": "`, no sorting of keys.
2. **Key order is dataclass field order, and `"type"` comes last.**
   `Event.round` is declared on the base class, so `round` is always the first
   key. `to_dict()` then appends `"type"`.
3. **`type` is the event class's Python name**, verbatim: `CardPlayed`,
   `HandSplit`, `RoundSettled`.
4. **A `Card` encodes as a two-element array, `[rank, "SuitWord"]`** — for
   example `[14, "Hearts"]`. `Card` is a `NamedTuple`, so `json` writes it as an
   array with no extra work. Ranks run 2–14 with the ace high (11 = jack,
   12 = queen, 13 = king, 14 = ace). Suits are the exact strings `"Hearts"`,
   `"Diamonds"`, `"Clubs"`, `"Spades"`.
5. **Integer dictionary keys become strings.** JSON has no integer keys, so
   every player or seat id used as a key arrives as a string. This affects
   `GameStarted.player_names`, `CardsDealt.card_counts`,
   `RoundEnded.card_counts`, `RoundDrawn.cards_returned`,
   `StrategiesAssigned.strategies`, and `RoundSettled.bankrolls`. Ids used as
   *values* — `CardPlayed.player`, `CardDealt.seat`, `RoundWon.winner` — stay
   numbers. A consumer that indexes a map by a numeric id must stringify it
   first.
6. **`round` is the round the event belongs to; `0` means pre-game.** Setup
   events (`GameStarted`, `CardsDealt`, `StrategiesAssigned`, and the opening
   `ShoeShuffled`) carry `round: 0`. Rounds are 1-based after that.
7. **Floats stay floats.** `HandResult.payout` and the values in
   `RoundSettled.bankrolls` encode as JSON numbers with a decimal point
   (`1.0`, `-1.0`, `1.5`, `0.0`). Bankrolls are rounded to one decimal place
   before serialization; payouts are not rounded because they are already
   exact halves.
8. **`seed` is an integer or `null`.** It is `null` only when a game is
   constructed directly with `seed=None`; the CLI and the server always
   substitute a random integer first.

## War events

Ten event types. The engine emits them from `engine/war.py`.

| Event | Fields after `round` | Meaning |
|---|---|---|
| `GameStarted` | `num_players`, `num_decks`, `player_names`, `seed` | configuration, before the deal |
| `CardsDealt` | `card_counts` | shoe shuffled and dealt round-robin |
| `RoundStarted` | `players` | ids still in the game this round |
| `CardPlayed` | `player`, `card`, `face_up` | one card onto the table |
| `WarDeclared` | `players`, `rank`, `depth`, `tiebreaker` | a tie at the highest rank |
| `PlayerEliminated` | `player`, `reason` | a player leaves the game |
| `RoundWon` | `winner`, `cards_won`, `via` | the table goes to one player |
| `RoundDrawn` | `players`, `cards_returned` | drawn war: the table splits, nobody wins |
| `RoundEnded` | `card_counts` | counts after the round settles |
| `GameOver` | `winner`, `total_rounds` | one player holds every card |

### Field detail

- `GameStarted.player_names` — `{"1": "Player 1", ...}`. Ids are 1-based and
  contiguous. The web UI uses this when the envelope has no `names` key, so
  imported recordings still show names.
- `CardsDealt.card_counts` and `RoundEnded.card_counts` — `{id: count}` for
  **in-game players only**. An eliminated player disappears from every later
  `RoundEnded`, which is how a chart line ends.
- `CardPlayed.face_up` — `true` for the card that gets compared. During a war,
  a player's buried cards are `false` and only the last one is `true`, and a
  player who cannot cover the war plays every remaining card face down and gets
  no face-up card at all.
- `WarDeclared.depth` — 1 for the first war of a round, 2 for a war inside that
  war, and so on.
- `WarDeclared.tiebreaker` — one of `"Default"`, `"Forfeit"`, `"Modified"`,
  `"Modified Forfeit"`, `"Draw"`. See `engine/war.py` for what each one does.
- `PlayerEliminated.reason` — `"out_of_cards"` (ran the pile dry at the end of
  a round) or `"insufficient_for_war"` (could not cover the war and forfeited).
- `RoundWon.via` — `"high_card"`, `"war"`, or `"forfeit"`, describing the
  **last** war stage that resolved. A round that opens with a Default war and
  ends with a Forfeit reports `"forfeit"`.
- `RoundWon.cards_won` — the size of the whole table, war cards included.
- `RoundDrawn.cards_returned` — `{id: count}` summing to the table size. The
  table divides evenly and any leftover cards go to a shuffled subset of the
  tied players, so counts can differ by one.
- `GameOver.winner` — the surviving player's id, or `null` in the unreachable
  case where the last players are eliminated together.

## Blackjack events

Eleven event types, from `engine/blackjack.py`. `GameStarted`, `RoundStarted`,
and `GameOver` are shared with war; the rest are blackjack's own.

| Event | Fields after `round` | Meaning |
|---|---|---|
| `GameStarted` | `num_players`, `num_decks`, `player_names`, `seed` | `num_players` is the seat count |
| `StrategiesAssigned` | `strategies` | seat → strategy name |
| `ShoeShuffled` | `cards` | a fresh shoe; `cards` is its size |
| `RoundStarted` | `players` | every seat id, always |
| `CardDealt` | `seat`, `card`, `face_up`, `hand` | one card to a seat's hand |
| `SeatAction` | `seat`, `action`, `total`, `hand` | a decision after it resolves |
| `HandSplit` | `seat`, `hand`, `new_hand` | a pair splits into two hands |
| `DealerRevealed` | `card`, `total` | the hole card turns over |
| `HandResult` | `seat`, `outcome`, `payout`, `player_total`, `dealer_total`, `hand` | one settled hand |
| `RoundSettled` | `bankrolls` | seat → cumulative units after the round |

### Field detail

- **`CardDealt.seat` uses 0 for the dealer.** Player seats are 1-based, so seat
  0 never appears in `player_names`, `strategies`, or `bankrolls`. This is the
  single most load-bearing convention in the blackjack log.
- `CardDealt.hand` — the hand index within the seat. The original hand is 0;
  splits create 1, 2, 3, up to `MAX_SPLIT_HANDS` (4) hands per seat. The dealer
  always uses hand 0.
- `CardDealt.face_up` — `false` only for the dealer's hole card.
- **`HandSplit` moves a card; it does not deal one.** The pair's second card was
  already reported by an earlier `CardDealt` for hand `hand`. On `HandSplit`,
  remove the **last** card of hand `hand` and append it to hand `new_hand`.
  `new_hand` is always the next free index, appended after the seat's existing
  hands. A `CardDealt` for hand `hand` follows immediately with its replacement
  card; hand `new_hand` receives its second card later, when the seat's turn
  loop reaches that index. A split emits no `SeatAction`.
- `SeatAction.action` — `"hit"`, `"stand"`, or `"double"`. `"split"` is never
  an action value; splits get their own event.
- `SeatAction.total` — the hand total **after** the action resolves. For a hit
  or a double, the `CardDealt` for the new card precedes the `SeatAction`, so a
  consumer replaying in stream order already holds the card the total describes.
- `DealerRevealed.card` — the hole card, repeated from its face-down
  `CardDealt`. `total` is the dealer's two-card total before any draw. The
  event fires **before** the dealer draws, and only when the dealer has
  blackjack or at least one non-natural hand is still standing. A round with no
  such hand — every non-natural hand busted, or every seat held a natural — has
  no `DealerRevealed` at all, and the hole card stays face down.
- `HandResult.outcome` — `"win"`, `"lose"`, `"push"`, `"blackjack"`, or
  `"bust"`. `"bust"` is a loss that also counts toward the seat's bust tally.
- `HandResult.payout` — units won or lost on that hand: `±1.0` normally,
  `±2.0` on a doubled hand, `+1.5` on a natural (3:2), `0.0` on a push. A
  natural can be neither doubled nor split, so `+1.5` never scales.
- `HandResult.dealer_total` — can exceed 21 when the dealer busts, and equals
  the two-card total when the dealer never drew.
- `HandResult.hand` — split seats emit one `HandResult` per hand, in ascending
  hand order.
- `RoundSettled.bankrolls` — every seat, cumulative units, rounded to one
  decimal place. This is the blackjack chart's data source.
- `GameOver.winner` — the seat with the highest bankroll; ties break toward the
  lower seat id.

## Ordering guarantees

Event order is part of the contract. A consumer that buckets events by round
and then processes them by type reconstructs the wrong hands, because
`HandSplit` and `CardDealt` only make sense in the order they were emitted.
**Replay in stream order.**

### War

Pre-game, in this order: `GameStarted`, `CardsDealt`.

Each round, in this order:

1. `RoundStarted` with the active ids in ascending order.
2. One `CardPlayed` per active player, ascending by id, all `face_up: true`.
3. Zero or more war stages. Each stage is a `WarDeclared` followed by the
   contenders' `CardPlayed` events in ascending id order, with a
   `PlayerEliminated` (`insufficient_for_war`) inserted right after the cards
   of any contender who could not cover the war. A `"Draw"` tiebreaker emits
   `RoundDrawn` immediately after `WarDeclared` and plays no cards. Stages
   repeat with `depth` incrementing while two or more face-up cards still tie.
4. `RoundWon`, unless the round ended in `RoundDrawn`.
5. `PlayerEliminated` (`out_of_cards`) for any player who ran dry, ascending
   by id.
6. `RoundEnded`.
7. `GameOver`, on the final round only.

A round therefore contains at most one `RoundWon` **or** one `RoundDrawn`,
never both, and it may contain several `WarDeclared` events. The web frontend
keeps only the last `WarDeclared` per round, so it displays the deepest stage.

### Blackjack

Pre-game, in this order: `GameStarted`, `StrategiesAssigned`, `ShoeShuffled`
(all with `round: 0`).

Each round, in this order:

1. `ShoeShuffled`, when the shoe fell below the reshuffle threshold. It carries
   the new round's number and precedes `RoundStarted`. A shoe that empties
   mid-round triggers another `ShoeShuffled` wherever the draw happened; that
   is rare but legal, so treat `ShoeShuffled` as possible at any point.
2. `RoundStarted` with every seat id.
3. The opening deal, in exactly this order: one `CardDealt` per seat ascending
   (hand 0), the dealer's upcard (`seat: 0`, `face_up: true`), a second
   `CardDealt` per seat ascending, the dealer's hole card (`seat: 0`,
   `face_up: false`).
4. Seat turns, ascending by seat. A seat holding a natural is skipped, and if
   the dealer has blackjack every seat is skipped. Within a seat, hands play in
   ascending index, including hands that splits appended during the turn. Per
   hand: an owed second card for a split hand (`CardDealt`), then a sequence of
   `HandSplit` + `CardDealt`, `CardDealt` + `SeatAction("hit")`,
   `CardDealt` + `SeatAction("double")`, or a bare `SeatAction("stand")`.
5. `DealerRevealed`, when it fires at all.
6. The dealer's draws, as `CardDealt` with `seat: 0`.
7. One `HandResult` per hand, ordered by seat ascending then hand ascending.
8. `RoundSettled`.
9. `GameOver`, on the final round only.

Because splits happen during step 4 and the opening deal is step 3, **every
`HandSplit` in a round follows that round's opening `CardDealt` events** — the
card it moves has always already been reported.

## What the frontend reads

`web/app.js` builds its replay index in `buildIndex` (war) and
`buildIndexBlackjack` (blackjack). These fields are load-bearing: change one
and playback breaks.

**War** — `GameStarted.player_names`; `CardsDealt.card_counts`;
`CardPlayed.round`, `.player`, `.card`, `.face_up`; `WarDeclared.round`,
`.players`, `.depth`, `.tiebreaker`; `PlayerEliminated.round`, `.player`;
`RoundWon.round`, `.winner`, `.cards_won`, `.via`; `RoundDrawn.round`,
`.players`; `RoundEnded.round`, `.card_counts`.

**Blackjack** — `GameStarted.player_names`; `StrategiesAssigned.strategies`;
`ShoeShuffled.round`; `CardDealt.round`, `.seat`, `.card`, `.face_up`,
`.hand`; `HandSplit.round`, `.seat`, `.hand`, `.new_hand`;
`DealerRevealed.round`; `HandResult.round`, `.seat`, `.hand`, `.outcome`,
`.payout`, `.player_total`, `.dealer_total`; `RoundSettled.round`,
`.bankrolls`.

From the envelope the frontend reads `summary.game`, `.rounds`, `.standings`,
`.num_players`, `.num_decks`, `.seed`, `.completed`, `.winner`, and
`.seats` (blackjack), plus `mode`, `names`, `strategies`, `stats`, `chart`,
and `eliminations`.

### Fields no client reads today

The following are emitted, stored in every fixture, and read by nobody. They
stay in v1 unchanged. They are the first candidates for omission in **v2**
recordings, where the goal is a smaller log:

- `RoundStarted` (war) — the whole event. `CardPlayed` already names every
  participant.
- `SeatAction` (blackjack) — the whole event. Hand contents from `CardDealt`
  imply the totals, and a stand is inferable from the hand ending.
- `WarDeclared.rank` — the tied rank. The face-up cards carry it.
- `PlayerEliminated.reason`.
- `RoundDrawn.cards_returned`.
- `DealerRevealed.card` and `.total` — the frontend uses the event only as a
  "reveal now" flag.
- `ShoeShuffled.cards`.
- `GameOver` (both games) — the whole event. `summary` carries the winner and
  the round count.

Anything not on this list is load-bearing. Removing a field from this list
still breaks a client that reads the raw JSON, so v2 recordings are a separate
format, not a v1 variant.

## The v1 seed contract

A v1 recording is reproducible from `(game, config, seed)` alone. That holds
because the engine draws every random decision from `random.Random(seed)` —
CPython's Mersenne Twister — and because **the exact sequence of RNG calls is
part of the contract**. Adding, removing, or reordering a single call changes
every card from that point on.

War consumes the stream in exactly these places:

1. `rng.shuffle(shoe)` once in `start()`, on the full `num_decks * 52` list
   built by `build_shoe` in suit-then-rank order.
2. `rng.shuffle(player.reserve)` each time a player's draw pile empties and the
   won-cards reserve folds back in.
3. `rng.shuffle(order)` in `_split_table`, to decide who gets the leftover
   cards on a drawn round.

Blackjack consumes it in exactly one place: `rng.shuffle(self.shoe)` on every
reshuffle, including the opening one in `start()`.

Two more notes on seeds:

- **Player names use a different stream.** `build_names` in `simulate.py` and
  `make_names` in `server.py` each construct their own `random.Random(seed)`.
  Naming never perturbs the game's RNG, so the same seed produces the same
  cards with or without `--random-names`.
- **Batches are seed ranges.** `run_batch` and `run_blackjack_batch` run games
  at `base_seed, base_seed + 1, ..., base_seed + N - 1` and return rows in seed
  order regardless of how work was distributed across processes. Any row can be
  replayed on its own from its `seed`.

`build_shoe` order matters as much as the shuffle: it emits `num_decks`
repetitions of suits in `("Hearts", "Diamonds", "Clubs", "Spades")` order, each
with ranks 2 through 14 ascending. Shuffling a differently ordered list with
the same RNG gives a different deck.

## v2 uses a separate seed namespace

The Rust core in `core-rs/` is v2. It does **not** reproduce v1 seeds. Seed 42
in v2 is a different game from seed 42 in v1, on purpose: v2 seeds a
SplitMix64 stream to fill a `xoshiro256**` state, draws bounded integers with
Lemire's method, and shuffles forward rather than backward. The reference
implementation, written independently of the Rust so that agreement means
something, is `core-rs/oracle/v2_rng_reference.py`.

Parity between the two engines is still tested, through a test-only
`cpython-rng` feature in `ludicrous-core` that reimplements MT19937. That
feature never ships — it exists so `cargo test` can play the same v1 game as
Python and compare rules and event JSON. See
`core-rs/crates/ludicrous-core/tests/oracle_parity.rs` and `event_json.rs`.

## How the contract stays frozen

- `tests/golden/` holds gzipped recordings for a seed matrix across both games,
  including a drawn war round, a depth-4 war, and blackjack sessions with
  splits, doubles, and mid-session reshuffles. `tests/test_golden.py` rebuilds
  each one in process and compares the bytes.
- `core-rs/crates/ludicrous-core/tests/event_json.rs` holds the same guarantee
  from the Rust side, against NDJSON fixtures from
  `core-rs/oracle/gen_event_fixture.py`.
- Regenerate the Python fixtures only on a deliberate contract change:

  ```
  LUDICROUS_REGEN_GOLDEN=1 python3 -m unittest tests.test_golden
  ```

  The run rewrites the fixtures and then fails, so the diff always gets read.
