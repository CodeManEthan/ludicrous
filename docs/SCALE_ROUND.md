---
type: design
project: ludicrous
description: "Scale round, 2026-09-04: compact numbers, a progress screen for single games, a rounds calculator, uncapped rounds, War caps to 1000, native Rust batch behind the server, and elimination-aware playback. Measured basis, decisions, seams, verification plan."
tags: [design, scale, playback, engine]
updated: 2026-09-04
---

# Scale round

Ethan's notes, 2026-09-04, and the design that came out of the discussion.
Everything below was agreed in conversation before build. Numbers are
measured on this machine (i7-13620H) unless marked as estimates.

## What we measured

Rounds in a War game are driven by decks, almost not by players. Rounds grow
roughly with the square of the total card count. Seed-to-seed spread is 2x to
5x. Native single-thread speed is 25M to 37M rounds/s; the browser wasm build
ran 7.07M rounds in 692 ms, about 10M rounds/s.

| Config | Mean rounds | Spread (min to max) | Native time per game |
|---|---|---|---|
| 200p / 16d | 40k | 18k to 73k | ms |
| 200p / 64d | 1.3M | 0.5M to 2.3M | 0.06 s |
| 200p / 200d | 9.7M | 3.3M to 17.9M | 0.4 s |
| 1000p / 200d | 9.8M | one seed | 0.3 s |
| 1000p / 500d | 24M | one seed | 0.7 s |
| 1000p / 1000d | 135M | one seed | 3.7 s |

Where eliminations fall (200p / 200d, seed 1, 7.07M rounds):

| Moment | Round | Share of game |
|---|---|---|
| 142 players left | 36 | 0.0% |
| 46 left | 48 | 0.0% |
| 10 left | 19,063 | 0.3% |
| 3 left | 404,094 | 5.7% |
| 2 left | 1,885,266 | 26.7% |
| final duel | the rest | 73% |

The opening lasts about one starting hand of rounds (52 x decks / players),
because only one player gains cards per round and everyone else loses one.
At the current "game in ~2 min" speed (58.9k rounds/s at that size) the whole
opening plays in about a millisecond.

The reported "freeze" at 200p / 200d could not be reproduced headless. The
likely cause is the 1M default Max rounds: every 200-deck game hits it and
shows an unfinished result. Simulate took 0.2 s at the cap and 0.7 s uncapped.

## Decisions

1. **Compact numbers everywhere a number is displayed as a value.** Rule:
   exact with separators below 10,000; `45.2k` up to a million; `7.07M` above,
   three significant figures; exact number in the `title` tooltip. Prose
   sentences (the finale line, the unfinished note) keep exact numbers. The
   live round counter during playback is compact too; the tooltip carries the
   exact round.
2. **Progress screen for single War games, driven by the engine.** The wasm
   `prepare` becomes a stepper so the worker can post rounds-so-far and honor
   cancel. The existing loading overlay (250 ms delay, elapsed clock, cancel)
   is reused; it gains a rounds counter and, when the calculator has an
   estimate, a bar against the typical round count.
3. **Rounds calculator.** An offline lookup grid (players x decks, 50 seeds
   per cell) shipped as JSON with median, p10, p90 and rounds/s. Interpolated
   log-log. Shown in the Options box under the inputs and on the progress
   screen. Warns when a cap is set below the p90.
4. **Uncapped by default.** Max rounds becomes an opt-in cap in the Options
   box (a checkbox that reveals the number field). Uncapped is encoded as
   `max_rounds=0` in the URL and API. The engine already treats "unlimited"
   as no cap.
5. **War caps to 1000 players and 1000 decks.** Single and batch. Blackjack
   stays at 200 seats on Python.
6. **Native Rust batch behind the server for War.** A `lud-batch` binary the
   Python server runs as a subprocess, streaming progress lines. Batch
   results become v2 (xoshiro seed namespace), tagged `engine: "v2"` in the
   response. Prebuilt Linux binary committed alongside the wasm, with Python
   fallback when the binary is missing or fails to start.
7. **Elimination-aware playback.** The scaled speeds ("game in ~N") split
   the wall-clock budget into opening, middle, and duel phases by players
   alive. Absolute speeds are unchanged. A toggle in Options restores
   constant speed.

## Design

### 1. Compact numbers

One helper in `web/app.js` replaces the current `compact()`:

```
fmtNum(n)       -> "7.07M" | "45.2k" | "9,812"   (display)
fmtNumExact(n)  -> "7,070,047"                    (tooltip)
```

Three significant figures: `7.07M`, `45.2k`, `135M`, `1.35M`. Trailing zeros
dropped (`9M`, not `9.00M`). Negative numbers keep the sign. Non-finite input
returns "—".

Call sites to change (all in `web/app.js`):

- `renderStats` tiles: Rounds, Wars, Biggest pot, Players / cards, Hands.
  The tile already sets `title`; it gets the exact value.
- The playback round counter (`Round 0 / 7,070,047`) and the scrubber label.
- `updateSpeedLabels`: `fmtDuration` already compacts hours; rates use
  `fmtNum`. Durations over 99 hours read `~2d` instead of `~1963.9h`.
- Highlight chips (`r7,070,047` becomes `r7.07M`).
- Batch stats tiles and the histogram axis where they use `fmt.format`.
- `renderElimFeed` round numbers.

Prose keeps `fmt.format`: the finale line, the unfinished note, the condensed
note, and the console log. Rule of thumb: a value in a box is compact, a
number inside a sentence is exact.

### 2. Progress screen (engine stepper)

**Rust, `core-rs/crates/ludicrous-wasm/src/prepared.rs`.** Split `prepare`
into a job object. The loop body stays identical; it moves into `step`.

```
#[wasm_bindgen]
pub struct WarPrepareJob { g, sample state, checkpoint state, elim state, cfg }

#[wasm_bindgen]
impl WarPrepareJob {
    pub fn new(num_players, num_decks, seed, max_rounds) -> Result<WarPrepareJob, JsError>
    pub fn step(&mut self, budget_rounds: u32) -> bool   // true when the game is over or capped
    pub fn round(&self) -> u32
    pub fn alive(&self) -> u32
    pub fn finish(self) -> Result<WarPrepared, JsError>  // the transpose + summary + view
}
```

`prepare` stays as a one-call wrapper (`new` + `step(u32::MAX)` + `finish`)
so the oracle tests and the bench keep working, and it is the proof that the
stepper produces byte-identical output: a golden test runs the same seed
both ways and compares the summary JSON, chart series, checkpoints, and
elimination arrays.

**Worker, `web/war-worker.js`.** `prepare` becomes:

```
prepare {players, decks, seed, maxRounds}
    job = WarPrepareJob.new(...)
    loop:
        done = job.step(STEP_ROUNDS)            // 250,000 rounds, ~25 ms in wasm
        if canceled: job.free(); reply {ok:false, error:"canceled"}
        every ~100 ms: postMessage {id, progress:{rounds, alive}}
        if done: break
    prepared = job.finish()
    reply as today

cancel {id}
    sets a flag the loop checks between steps
```

The worker is single-threaded, so `cancel` cannot be received while `step`
runs. The loop yields to the event loop between steps with a macrotask
(`setTimeout(0)` or a MessageChannel ping); a microtask yield (`await` on a
resolved promise) would never let the cancel message land. The old
`prepared` game is freed only after `finish` succeeds, so a canceled run
leaves the previous game playable.

**Page, `web/app.js`.** Three things change, all named because the
verification pass found each one would otherwise break:

- `v2Worker.onmessage` (app.js:211) today deletes the pending entry and
  rejects on any message without `ok: true`. It must branch on `progress`
  first and leave the entry in place.
- `simulate()` (app.js:491) catches any rejection from `simulateV2` and
  falls back to the Python server. A cancel, and an engine validation
  error, must surface as an error instead: `simulateV2` rejects with a
  tagged error (`error.v2Final = true`) and `simulate` rethrows those.
- The overlay's cancel button only calls `loadingAbort.abort()`. `simulateV2`
  sets `loadingAbort` to an AbortController whose abort listener sends
  `{type:"cancel"}` to the worker and rejects the pending prepare.

`simulateV2` wraps `v2Send` in `showLoading` with the config as the title and
the calculator's estimate as the note. `v2Send` grows an `onProgress`
callback. The loading overlay shows:

```
Simulating War — 1000 players, 1000 decks
Typically ~135M rounds (40M to 300M), about 12 s
[=========          ]  48.2M rounds · 3 players left · 4.1 s      [Cancel]
```

The bar is against the calculator's p90 and clamps at 95% until the run
finishes, so it never sits at 100% while still working. Without an estimate
(cell outside the grid) the bar is hidden and only the counter shows.

Blackjack and v1 server games keep the overlay they have today.

### 3. Rounds calculator

**Grid.** `core-rs/crates/ludicrous-bench/examples/grid.rs` (grown from the
throwaway `scale.rs`) runs 50 seeds per cell and writes `web/rounds-grid.json`:

```
{ "players": [2,4,8,16,32,64,128,256,512,1000],
  "decks":   [1,2,4,8,16,32,64,128,256,512,1000],
  "cells":   { "p:d": [median, p10, p90, native_rounds_per_sec] },
  "wasm_speed_factor": 0.35,
  "generated": "2026-09-04", "seeds": 50 }
```

Cells with fewer cards than players are absent. The 1000 x 1000 cell is 50
games at 3.7 s each, so the full grid is a few minutes native; it runs
once and the JSON is committed. About 100 cells, under 10 KB.

**Lookup, `web/app.js`.** `estimateRounds(players, decks)` interpolates
bilinearly in log space over the four surrounding cells. Off-grid (fewer
cards than players) returns null and the Options box says "not enough
cards for that many players", which is also the engine's error. The time
estimate is `median / (native_rps * wasm_speed_factor)`; the factor is
measured once on this machine and is a coarse guide, labeled "about".

**Display.** A line under the Players/Decks inputs in the Options box:

```
Typical game: ~9.7M rounds (3.3M to 17.9M) · about 1 s to simulate
```

Updates on input. If a cap is on and below p90: "Your cap of 1M rounds will
stop most games early." The same line is the note on the progress screen.

### 4. Uncapped by default

- Options box: `[ ] Cap rounds at [1,000,000]`. Unchecked by default. The
  number field is disabled while unchecked.
- URL and API: `max_rounds=0` means no cap. Old links with a value keep it.
  Missing `max_rounds` in an old URL means the old default (1M), so old
  share links replay as they did.
- Three places today turn 0 into the 1M default and must distinguish
  "missing" from "0": app.js:334 (`|| 1_000_000`), server.py:161 and
  server.py:258 (`or DEFAULT_MAX_ROUNDS`). The Python single-game loop at
  server.py:182 compares against `max_rounds` and needs a None guard.
- Worker: pass 0 straight through. The wasm `config()` helper
  (ludicrous-wasm/src/lib.rs:22) already maps `max_rounds <= 0` to
  unlimited.
- URL replay sets the cap checkbox before writing the number field, and the
  field's `min` drops to 1, so a `0` never fails form validation.
- Python-run War (v1 fallback, old links) keeps its own ceiling: capped at
  `MAX_ROUNDS_CEILING` (20M) even when asked for unlimited, and still limited
  to 200 players and 200 decks. Python at 1000 x 1000 is hours per request.
  The 1000 caps and unlimited apply to the wasm and native paths only. The
  HTML `max` on the field goes away.
- The unfinished note and the "safety cap" finale wording stay for capped
  games.

### 5. Caps to 1000

- `web/index.html`: `max="1000"` on both inputs, titles updated.
- `server.py`: `MAX_PLAYERS = 1000`, `MAX_DECKS = 1000` for the native batch
  path; the Python paths (v1 single War, Blackjack, Python batch fallback)
  keep 200 as `PY_MAX_PLAYERS` / `PY_MAX_DECKS`.
- The Rust core already validates up to 1260 decks and any player count that
  fits the shoe.
- The table at 1000 tiles. Today `paintWarRound` (app.js:1178) touches
  every tile every round, including an unconditional `img.src` write and an
  O(n) `standings.indexOf` per out tile. It gains a per-tile cache of the
  last painted (face, count, state) and skips unchanged tiles, and
  standings become a `Map` built once per round.
- The chart. `drawChart` strokes every non-leading series each frame, up to
  1000 lines of 1200 points. The non-leading series move to an offscreen
  "field" canvas redrawn only when the chart size, the reveal state, or the
  zoom window changes; each frame blits it and strokes only the top few
  series and the playhead.
- Verified by the 1000 x 1000 playback check in the plan below.
- README and the header line ("200 players, 200 decks") updated.

### 6. Native batch

**Binary, `core-rs/crates/ludicrous-bench` gains a second bin `lud-batch`**
(or its own crate `ludicrous-batch`; own crate, so the bench stays a bench):

```
lud-batch --players P --decks D --games N --seed S [--max-rounds M] [--threads T]
```

stdout, NDJSON: throttled `{"progress":{"done","total"}}` lines then one
`{"result": {...}}` in exactly the shape `summarize_batch` returns plus the
per-game rows, so `run_batch_api` returns the same JSON either way. Threads
via `std::thread::scope` over a shared atomic counter, chunked by seed; no
new dependencies beyond a JSON writer (hand-rolled, the shapes are flat).

**Server, `server.py`.** `run_batch_api` for War: if `bin/lud-batch` exists
and is executable, spawn it, forward progress lines to the existing
`progress` callback, parse the result. Fallback to the Python pool happens
only when the binary cannot be started (missing, not executable, exec
error), logged once. A crash or non-zero exit mid-run is an error to the
client, never a silent rerun in Python. Cancel: `progress()` swallows the
write error when the client is gone (server.py:346); it now also sets a
flag, and the spawn loop kills the child when it sees it.

**Work budget.** `MAX_BATCH_GAMES` x 1000p/1000d is hours even native. The
server reads `web/rounds-grid.json` and rejects a War batch whose
`games x median_estimate` exceeds 5e9 rounds (a few seconds here, a few
minutes on Railway's box) with a message that names the number.

**Replay.** `replaySeed` (app.js:1951) forces the v1 engine for a batch row.
It picks v2 when `batchData.engine === "v2"` so the row replays the same
game.

**Build and deploy.** `core-rs/build-native.sh` builds a static
`x86_64-unknown-linux-musl` binary into `bin/lud-batch` (musl so the
`python:3.12-slim` image needs nothing). Committed like the wasm. Local dev
on this machine uses the same file.

**Seeds.** Batch results move to the v2 seed namespace, matching single
games. The response gains `"engine": "v2"`. Old batch share URLs replay with
different per-seed outcomes; the aggregate statistics are the same
distribution. This is the trade the August ruling already made for single
games.

### 7. Elimination-aware playback

Computed once in `activate` for War games with `elimSorted` available
(v2 and v1 both build it as `{player, round}` ascending), and only for
scaled speeds (values starting with `d`).

The elimination rounds split the game into spans. Each span gets a wall-clock
allotment; speed inside a span is constant, `spanRounds / spanSeconds`.
`tick` finds the span for `pos` by binary search and uses its speed, in place
of the position-blind `speedFor`.

Spans fall into three phases by players alive at the start of the span:

- **Opening**: alive > max(10, players / 4). The first hand's worth of
  rounds, when three quarters of the field goes out. Played at 3 rounds/s,
  total capped at 20% of the budget N. For 200p/200d that is rounds 0 to 48,
  about 16 s at "game in 2 min".
- **Middle**: from there until 2 alive. Its 20% of N is divided equally
  across the spans, so every elimination gets the same beat, at least 0.5 s
  when the budget allows. At 200p/200d that is 44 eliminations over 24 s.
- **Duel**: the final two, everything left, never under 60% of N.

Unused opening and middle time flows to the duel, so a 6-player game plays
much as it does today. A minimum span speed of 3 rounds/s applies
throughout, so no span crawls.

The speed menu label for a scaled speed shows the duel rate, since that is
the phase you watch longest. The scrubber and round counter are untouched.
Options gains `[x] slow the opening`, on by default; off restores the single
constant speed.

> As of 2026-09-06 the toggle is **off by default** (see `docs/DESIGN_NOTES.md`,
> note 4): at 40M rounds the phased plan spent 40% of the budget on a few
> hundred rounds. Off now means one constant rate with a one-round-per-frame
> cap while the field is crowded, so the opening still reads on screen.

Games with no elimination data (v1 recordings, Blackjack) use the constant
speed.

## Not in this round

- Blackjack on the Rust core. Stays Python at 200 seats.
- Batch single-game replay from a batch row at 1000 players.
- Any change to the checkpoint format.

## Toolchain

The verification pass found neither the `wasm-bindgen` CLI nor the musl
target installed. Both are needed and both install from the network:

```
cargo install wasm-bindgen-cli --version 0.2.127
rustup target add x86_64-unknown-linux-musl
```

The version must match `core-rs/Cargo.lock`. `wasm-opt` is optional and
`build-wasm.sh` tolerates its absence. A glibc build from this Fedora box
would not run on the `python:3.12-slim` image, so musl is required for the
batch binary.

## Build order

1. Grid generator and `rounds-grid.json`. Nothing depends on the rest, and
   the numbers feed the progress screen.
2. Engine stepper, golden parity test, wasm rebuild.
3. Worker and page: progress, cancel, uncapped, caps to 1000, calculator
   line, compact numbers.
4. Elimination-aware playback.
5. Native batch binary, server wiring, musl build.
6. README, docs, deploy.

## Verification

- Golden: `prepare` versus `new + step + finish` on 20 seeds across small and
  large configs, byte-identical outputs.
- `cargo test` in core-rs and `python -m pytest tests/` stay green.
- Headless browser (playwright-cli, unique session): 200p/200d and
  1000p/1000d simulate with the progress screen visible, cancel mid-run
  returns to the form within 300 ms, main-thread lag under 100 ms during
  playback at the top scaled speed, Skip to results under 2 s.
- Calculator: for 10 random cells the estimate's p10 to p90 band contains the
  actual round count of a fresh seed at least 7 times.
- Native batch: 100 games at 200p/200d returns in under 10 s on this machine
  with the same JSON keys as the Python path; kill the binary mid-run and
  confirm the Python fallback is not triggered (a crash mid-run is an error,
  not a fallback).
- Numbers: grep for `fmt.format` in `web/app.js` and confirm every remaining
  use is inside prose.

## As built (2026-09-04, same day)

Everything above shipped in the working tree. Where the build differed from
the design:

- **Progress screen.** Measured in headless Chromium: 200p/200d uncapped
  simulates in 0.7 to 0.9 s, 1000p/1000d in 8.8 s with the counter reading
  "35.5M rounds · 2 still in · 3.0 s" on the way. Cancel returns to the form
  inside 300 ms with "Simulation canceled." and no server fallback.
- **Calculator.** The grid is 95 cells, 50 seeds each, 4.9 KB. Ten off-grid
  configs against a fresh seed: 8 of 10 inside the p10 to p90 band (the two
  misses were short games under the band). The wasm speed factor is 0.5, not
  0.33: the browser ran 200-deck games at about a third of native speed and
  1000-deck games at about three quarters, so "about N s" is a coarse guide.
- **Playback.** 200p/200d at "game in ~30 s": opening 6 s (rounds 0 to 48
  at 3 rounds/s), middle 6 s across 40 eliminations, duel 18 s. Main-thread
  lag stayed under 40 ms with 1000 tiles on screen; a seek to round 70M in a
  135M-round game rendered in well under a second. At 1000 players the
  middle phase has 248 eliminations in 20% of the budget, so each gets a
  fraction of a second at the 30 s setting; the 4-minute setting gives them
  a beat.
- **Native batch.** 100 games at 200p/200d through the server: 3.6 s on 16
  threads, 31 progress lines, the same JSON keys as the Python path plus
  `engine: "v2"` and `threads`. A batch of 1000 games at 1000p/1000d is
  refused by the budget with the number named. Killing the client mid-batch
  killed the runner within 1.5 s. `bin/lud-batch` is a 537 KB static musl
  binary, built by `core-rs/build-native.sh`.
- **Blackjack** single games on the server keep 200 seats and 200 decks, as
  do Python-run War games from old links (they get a message pointing at the
  browser engine when asked for more).
- **Toolchain** installed on this machine: wasm-bindgen-cli 0.2.127, the
  musl target, and binaryen 123 under ~/.local/opt/binaryen (so the wasm is
  optimized again, 108 KB as before).
- The throwaway measurement programs became
  `core-rs/crates/ludicrous-bench/examples/grid.rs`, which generates the
  calculator grid.
