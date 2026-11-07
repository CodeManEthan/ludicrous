# Design log

Decisions behind the War engine scale-up and the playback UI, in date order.
Each entry gives the problem, what was measured, the design, the trade-offs,
and what was built. Measurements were taken on a 16-thread laptop (Intel
i7-13620H) unless marked as estimates. File and function names are as they
were at the time; later commits may have moved them.

## 2026-09-04: War at 1000 players and 1000 decks

### Measurements

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
At the then-default "game in ~2 min" speed (58.9k rounds/s at that size) the
whole opening played in about a millisecond.

A reported "freeze" at 200p / 200d could not be reproduced headless. The
likely cause was the 1M default Max rounds: every 200-deck game hit it and
showed an unfinished result. Simulate took 0.2 s at the cap and 0.7 s
uncapped.

### Decisions

1. **Compact numbers wherever a number is shown as a value.** Exact with
   separators below 10,000; `45.2k` up to a million; `7.07M` above, three
   significant figures; the exact number in the `title` tooltip. Prose
   sentences (the finale line, the unfinished note) keep exact numbers. The
   live round counter during playback is compact too; its tooltip carries
   the exact round.
2. **Progress screen for single War games, driven by the engine.** The wasm
   `prepare` becomes a stepper so the worker can post rounds-so-far and
   honor cancel. The existing loading overlay (250 ms delay, elapsed clock,
   cancel) is reused; it gains a rounds counter and, when the calculator has
   an estimate, a bar against the typical round count.
3. **Rounds calculator.** An offline lookup grid (players x decks, 50 seeds
   per cell) shipped as JSON with median, p10, p90 and rounds/s,
   interpolated log-log. Shown in the Options box under the inputs and on
   the progress screen. Warns when a cap is set below the p90.
4. **Uncapped by default.** Max rounds becomes an opt-in cap in the Options
   box (a checkbox that reveals the number field). Uncapped is encoded as
   `max_rounds=0` in the URL and API. The engine already treated "unlimited"
   as no cap.
5. **War caps at 1000 players and 1000 decks**, single and batch. Blackjack
   stays at 200 seats on Python.
6. **Native Rust batch behind the server for War.** A `lud-batch` binary the
   Python server runs as a subprocess, streaming progress lines. Batch
   results move to v2 (xoshiro seed namespace), tagged `engine: "v2"` in the
   response. A prebuilt Linux binary is committed alongside the wasm, with a
   Python fallback when the binary is missing or fails to start.
7. **Elimination-aware playback.** The scaled speeds ("game in ~N") split
   the wall-clock budget into opening, middle and duel phases by players
   alive. Absolute speeds are unchanged. A toggle in Options restores
   constant speed.

### 1. Compact numbers

One helper in `web/app.js` replaces the old `compact()`:

```
fmtNum(n)       -> "7.07M" | "45.2k" | "9,812"   (display)
fmtNumExact(n)  -> "7,070,047"                    (tooltip)
```

Three significant figures: `7.07M`, `45.2k`, `135M`, `1.35M`. Trailing zeros
dropped (`9M`, not `9.00M`). Negative numbers keep the sign. Non-finite input
returns "—".

Call sites, all in `web/app.js`:

- `renderStats` tiles: Rounds, Wars, Biggest pot, Players / cards, Hands.
  The tile already sets `title`; it gets the exact value.
- The playback round counter (`Round 0 / 7,070,047`) and the scrubber label.
- `updateSpeedLabels`: `fmtDuration` already compacts hours; rates use
  `fmtNum`. Durations over 99 hours read `~2d` instead of `~1963.9h`.
- Highlight chips (`r7,070,047` becomes `r7.07M`).
- Batch stats tiles and the histogram axis where they use `fmt.format`.
- `renderElimFeed` round numbers.

Prose keeps `fmt.format`: the finale line, the unfinished note, the
condensed note and the console log. A value in a box is compact; a number
inside a sentence is exact.

### 2. Progress screen (engine stepper)

**Rust, `core-rs/crates/ludicrous-wasm/src/prepared.rs`.** `prepare` splits
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
so the oracle tests and the bench keep working. It is also the proof that
the stepper produces byte-identical output: a golden test runs the same seed
both ways and compares the summary JSON, chart series, checkpoints and
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
    reply as before

cancel {id}
    sets a flag the loop checks between steps
```

The worker is single-threaded, so `cancel` cannot be received while `step`
runs. The loop yields to the event loop between steps with a macrotask
(`setTimeout(0)` or a MessageChannel ping); a microtask yield (`await` on a
resolved promise) would never let the cancel message land. The previous
prepared game is freed only after `finish` succeeds, so a canceled run
leaves the previous game playable.

**Page, `web/app.js`.** Three things change, each of which would otherwise
break:

- `v2Worker.onmessage` deleted the pending entry and rejected on any message
  without `ok: true`. It must branch on `progress` first and leave the entry
  in place.
- `simulate()` caught any rejection from `simulateV2` and fell back to the
  Python server. A cancel, and an engine validation error, must surface as
  an error instead: `simulateV2` rejects with a tagged error
  (`error.v2Final = true`) and `simulate` rethrows those.
- The overlay's cancel button only called `loadingAbort.abort()`.
  `simulateV2` sets `loadingAbort` to an AbortController whose abort
  listener sends `{type:"cancel"}` to the worker and rejects the pending
  prepare.

`simulateV2` wraps `v2Send` in `showLoading` with the config as the title
and the calculator's estimate as the note. `v2Send` gains an `onProgress`
callback. The loading overlay shows:

```
Simulating War — 1000 players, 1000 decks
Typically ~135M rounds (40M to 300M), about 12 s
[=========          ]  48.2M rounds · 3 players left · 4.1 s      [Cancel]
```

The bar is against the calculator's p90 and clamps at 95% until the run
finishes, so it never sits at 100% while still working. Without an estimate
(a cell outside the grid) the bar is hidden and only the counter shows.

Blackjack and v1 server games keep their existing overlay.

### 3. Rounds calculator

**Grid.** `core-rs/crates/ludicrous-bench/examples/grid.rs` runs 50 seeds
per cell and writes `web/rounds-grid.json`:

```
{ "players": [2,4,8,16,32,64,128,256,512,1000],
  "decks":   [1,2,4,8,16,32,64,128,256,512,1000],
  "cells":   { "p:d": [median, p10, p90, native_rounds_per_sec] },
  "wasm_speed_factor": 0.35,
  "generated": "2026-09-04", "seeds": 50 }
```

Cells with fewer cards than players are absent. The 1000 x 1000 cell is 50
games at 3.7 s each, so the full grid takes a few minutes native; it runs
once and the JSON is committed. About 100 cells, under 10 KB.

**Lookup, `web/app.js`.** `estimateRounds(players, decks)` interpolates
bilinearly in log space over the four surrounding cells. Off-grid (fewer
cards than players) returns null and the Options box says "not enough
cards for that many players", which is also the engine's error. The time
estimate is `median / (native_rps * wasm_speed_factor)`; the factor is
measured once on the laptop above and is a coarse guide, labeled "about".

**Display.** A line under the Players/Decks inputs in the Options box:

```
Typical game: ~9.7M rounds (3.3M to 17.9M) · about 1 s to simulate
```

It updates on input. If a cap is on and below p90: "Your cap of 1M rounds
will stop most games early." The same line is the note on the progress
screen.

### 4. Uncapped by default

- Options box: `[ ] Cap rounds at [1,000,000]`, unchecked by default. The
  number field is disabled while unchecked.
- URL and API: `max_rounds=0` means no cap. Old links with a value keep it.
  A missing `max_rounds` in an old URL means the old default (1M), so old
  share links replay as they did.
- Three places turned 0 into the 1M default and must tell "missing" from
  "0": the URL reader in `web/app.js` (`|| 1_000_000`) and the single-game
  and batch handlers in `server.py` (`or DEFAULT_MAX_ROUNDS`). The Python
  single-game loop compares against `max_rounds` and needs a None guard.
- Worker: pass 0 straight through. The wasm `config()` helper in
  `ludicrous-wasm/src/lib.rs` already maps `max_rounds <= 0` to unlimited.
- URL replay sets the cap checkbox before writing the number field, and the
  field's `min` drops to 1, so a `0` never fails form validation.
- Python-run War (the v1 fallback, old links) keeps its own ceiling: capped
  at `MAX_ROUNDS_CEILING` (20M) even when asked for unlimited, and still
  limited to 200 players and 200 decks. Python at 1000 x 1000 is hours per
  request. The 1000 caps and unlimited apply to the wasm and native paths
  only. The HTML `max` on the field goes away.
- The unfinished note and the "safety cap" finale wording stay for capped
  games.

### 5. Caps to 1000

- `web/index.html`: `max="1000"` on both inputs, titles updated.
- `server.py`: `MAX_PLAYERS = 1000`, `MAX_DECKS = 1000` for the native batch
  path; the Python paths (v1 single War, Blackjack, the Python batch
  fallback) keep 200 as `PY_MAX_PLAYERS` / `PY_MAX_DECKS`.
- The Rust core already validates up to 1260 decks and any player count
  that fits the shoe.
- The table at 1000 tiles. `paintWarRound` touched every tile every round,
  including an unconditional `img.src` write and an O(n)
  `standings.indexOf` per out tile. It gains a per-tile cache of the last
  painted (face, count, state) and skips unchanged tiles, and standings
  become a `Map` built once per round.
- The chart. `drawChart` stroked every non-leading series each frame, up to
  1000 lines of 1200 points. The non-leading series move to an offscreen
  "field" canvas, redrawn only when the chart size, the reveal state or the
  zoom window changes; each frame blits it and strokes only the top few
  series and the playhead.
- README and the header line ("200 players, 200 decks") updated.

### 6. Native batch

**Binary.** `lud-batch` gets its own crate, `ludicrous-batch`, so the bench
stays a bench:

```
lud-batch --players P --decks D --games N --seed S [--max-rounds M] [--threads T]
```

stdout, NDJSON: throttled `{"progress":{"done","total"}}` lines, then one
`{"result": {...}}` in exactly the shape `summarize_batch` returns plus the
per-game rows, so `run_batch_api` returns the same JSON either way. Threads
via `std::thread::scope` over a shared atomic counter, chunked by seed; no
new dependencies beyond a JSON writer (hand-rolled, since the shapes are
flat).

**Server, `server.py`.** `run_batch_api` for War: if `bin/lud-batch` exists
and is executable, spawn it, forward progress lines to the existing
`progress` callback and parse the result. Fallback to the Python pool
happens only when the binary cannot be started (missing, not executable,
exec error), logged once. A crash or non-zero exit mid-run is an error to
the client, never a silent rerun in Python. Cancel: `progress()` swallowed
the write error when the client was gone; it now also sets a flag, and the
spawn loop kills the child when it sees it.

**Work budget.** `MAX_BATCH_GAMES` x 1000p/1000d is hours even native. The
server reads `web/rounds-grid.json` and rejects a War batch whose
`games x median_estimate` exceeds 5e9 rounds (a few seconds on the laptop,
a few minutes on the hosted server) with a message that names the number.

**Replay.** `replaySeed` forced the v1 engine for a batch row. It picks v2
when `batchData.engine === "v2"`, so the row replays the same game.

**Build and deploy.** `core-rs/build-native.sh` builds a static
`x86_64-unknown-linux-musl` binary into `bin/lud-batch` (musl, so the
`python:3.12-slim` image needs nothing). Committed like the wasm. Local
development uses the same file.

**Seeds.** Batch results move to the v2 seed namespace, matching single
games. The response gains `"engine": "v2"`. Old batch share URLs replay with
different per-seed outcomes; the aggregate statistics are the same
distribution. Single games made the same trade in August 2026, when they
moved to the browser engine.

### 7. Elimination-aware playback

Computed once in `activate` for War games with `elimSorted` available (v2
and v1 both build it as `{player, round}` ascending), and only for scaled
speeds (values starting with `d`).

The elimination rounds split the game into spans. Each span gets a
wall-clock allotment; speed inside a span is constant,
`spanRounds / spanSeconds`. `tick` finds the span for `pos` by binary search
and uses its speed, in place of the position-blind `speedFor`.

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
much as before. A minimum span speed of 3 rounds/s applies throughout, so no
span crawls.

The speed menu label for a scaled speed shows the duel rate, since that is
the phase watched longest. The scrubber and round counter are untouched.
Options gains `[x] slow the opening`, on by default; off restores the single
constant speed. (Two days later the default flipped to off; see the
2026-09-06 entry on pacing.)

Games with no elimination data (v1 recordings, Blackjack) use the constant
speed.

### Left out

- Blackjack on the Rust core. It stays Python at 200 seats.
- Single-game replay from a batch row at 1000 players.
- Any change to the checkpoint format.

### Toolchain

Neither the `wasm-bindgen` CLI nor the musl target was installed at the
start. Both are needed and both install from the network:

```
cargo install wasm-bindgen-cli --version 0.2.127
rustup target add x86_64-unknown-linux-musl
```

The version must match `core-rs/Cargo.lock`. `wasm-opt` is optional and
`build-wasm.sh` tolerates its absence. A glibc build from a Fedora host
would not run on the `python:3.12-slim` image, so musl is required for the
batch binary.

These setup steps were replaced on 2026-11-07: the build scripts now pin the
toolchain, install their own locked wasm-bindgen and run no `wasm-opt`. See
the entry for that date.

### Acceptance checks

- Golden: `prepare` versus `new + step + finish` on 20 seeds across small
  and large configs, byte-identical outputs.
- `cargo test` in core-rs and the Python tests stay green.
- Headless browser: 200p/200d and 1000p/1000d simulate with the progress
  screen visible, cancel mid-run returns to the form within 300 ms,
  main-thread lag under 100 ms during playback at the top scaled speed,
  Skip to results under 2 s.
- Calculator: for 10 random cells the estimate's p10 to p90 band contains
  the actual round count of a fresh seed at least 7 times.
- Native batch: 100 games at 200p/200d return in under 10 s with the same
  JSON keys as the Python path; killing the binary mid-run does not trigger
  the Python fallback (a crash mid-run is an error, not a fallback).
- Numbers: every remaining `fmt.format` in `web/app.js` is inside prose.

### As built (2026-09-04)

Where the build differed from the design, and what it measured:

- **Progress screen.** In headless Chromium, 200p/200d uncapped simulates in
  0.7 to 0.9 s, 1000p/1000d in 8.8 s with the counter reading
  "35.5M rounds · 2 still in · 3.0 s" on the way. Cancel returns to the form
  inside 300 ms with "Simulation canceled." and no server fallback.
- **Calculator.** The grid is 95 cells, 50 seeds each, 4.9 KB. Ten off-grid
  configs against a fresh seed: 8 of 10 inside the p10 to p90 band (the two
  misses were short games under the band). The wasm speed factor is 0.5,
  not the 0.35 first sketched: the browser ran 200-deck games at about a third of native speed
  and 1000-deck games at about three quarters, so "about N s" is a coarse
  guide.
- **Playback.** 200p/200d at "game in ~30 s": opening 6 s (rounds 0 to 48 at
  3 rounds/s), middle 6 s across 40 eliminations, duel 18 s. Main-thread lag
  stayed under 40 ms with 1000 tiles on screen; a seek to round 70M in a
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
- **Toolchain:** wasm-bindgen-cli 0.2.127, the musl target, and binaryen 123,
  so the wasm is optimized again (108 KB, as before). The builds have since
  dropped `wasm-opt` (2026-11-07 entry).
- The throwaway measurement programs became
  `core-rs/crates/ludicrous-bench/examples/grid.rs`, which generates the
  calculator grid.

## 2026-09-05: mobile layout and the chart's opening

### Events move the page on a phone

**Problem.** On a phone, each event during playback moves the page up and
down.

**Code at the time.**

- `web/index.html` had no mobile layout: `web/*.css` contained no `@media`
  rule.
- The round banner (`#banner`, `.banner` with `min-height: 22px`) is
  rewritten every rendered round by `describeRound` /
  `describeBlackjackRound`. On a narrow screen the text wraps to a varying
  number of lines, so its height changes round to round and everything below
  it (the table, the chart, the elimination timeline) moves.
- The out-strip (`#outStrip`) appears and grows as players go out, and tiles
  leave the grid in "collapse into a strip" mode; both reflow the grid.
- The elimination timeline (`#elimFeed`) is a list that grows during live
  playback.

**Design.** Reserve fixed space for the banner on small screens (a fixed
line count with ellipsis, or a fixed-height sticky strip), and keep the grid
and out-strip from changing height when a player goes out. The alternative,
events in a fixed overlay or ticker outside the page flow, was not built.

### The chart looks frozen through the slow opening

**Problem.** Phased playback (from the 2026-09-04 entry) plays the crowded
opening of a big game slowly, but the chart was not adjusted to match: for
the first several seconds nothing visibly happens on it, and the lines only
start to move once playback speeds up.

**Code at the time.**

- In suspense mode the x-axis already follows the playhead (`drawChart` in
  `web/app.js`), but its window had a floor of
  `max(pos * 1.25, sampleGap * 20, 50)` rounds. The series is downsampled to
  at most 1,200 samples across the game, so `sampleGap` is `rounds / 1200`.
  For a 7M-round game that floor is about 118,000 rounds.
- The opening phase plays at `OPENING_RATE = 3` rounds per second for up to
  20% of the budget. So during a 6 s opening the playhead reaches round 18
  inside a 118,000-round window: a fraction of a pixel of motion.
- The y-axis spans 0 to total cards for the whole game. With 200 players
  every line starts at 1/200 of the height, so early card swings are also
  invisible vertically.

**Design.** Give the opening its own axis window: keep full-resolution
samples for the opening rounds so the x floor can be small, and let the
y-axis start near the opening's card range and grow toward the leader, the
way the x-axis already grows. The floor of 20 samples exists so the early
window is not too sparse to draw; that constraint moves to the sampling,
not the axis.

### Chart above the table, and a denser table on a phone

**Problem.** With the table on top and a big field, a phone shows about
three players per row, and scrolling past all those cards to reach the chart
is impractical.

**Code at the time.**

- "Chart above cards" already existed as a toggle in the playback Options
  popover (`chartTopChk`, stored as `layoutPrefs.chartFirst` in
  localStorage, applied as the `chart-first` class on `#results`), off by
  default. The pref is written only when the box is clicked, so "unset" can
  be read as chart-first and everyone who never touched the toggle gets the
  new default.
- The player grid is `repeat(auto-fill, minmax(76px, 1fr))` with an 8 px
  column gap, and each player tile carries a card image and a meta line.
  Nothing adapted to viewport width.
- The out-strip already compacts eliminated players into chips, so late in a
  big game the grid is small. The problem is the opening, when everyone is
  still in.

**Design.**

- Chart first by default; keep the toggle.
- A mobile grid: on narrow viewports drop the tile minimum to roughly 48 px,
  shrink or hide the card image, and put the name and count on one line, so
  a phone gets six to eight players per row.
- Above some player count on a phone, start the table collapsed (the
  collapse button already existed, stored as `layoutPrefs.tableCollapsed`),
  so the chart and banner are what you see, with the table one tap away.
- Designed together with the fixed banner above, since both are the app's
  first mobile layout.

### As built (2026-09-06)

Verified headless in Chromium at 375 px and 1280 px on a 200-player,
200-deck War game, plus a Python-served 8-player game.

- **Banner.** `web/style.css` gained its first media query
  (`max-width: 640px`, also read by `app.js` as `narrowScreen`). The round
  banner is clamped to exactly two lines (44 px) on phones, so the chart and
  table below it stay put during playback. Panel and page padding tighten,
  and the chart drops to 220 px.
- **Chart opening.** Chart sampling is now the 1,200 uniform points plus a
  dense opening: every round through 200, then 2% steps (`r += r/50`) until
  the uniform series is at least that fine. Implemented identically in the
  wasm prepare pass (`DENSE_ROUNDS`, `GEO_DIVISOR`, merged in `finish`),
  `web/app.js` (`chartSampleRounds`) and `server.py`
  (`chart_sample_rounds`). A 7M-round game has 1,600 samples instead of
  1,201. In suspense mode `drawChart` keeps at least 12 samples on screen
  (so the opening window is 13 rounds, not 118,000), and the War y-axis
  starts at 2.5 opening stacks and follows the biggest stack so far, snapped
  to 5% steps. Series are clipped to the plot so future values above the
  live axis cannot leak.
- **Layout.** Chart above the cards is the default
  (`layoutPrefs.chartFirst !== false`); the toggle still works. On a phone,
  a table with more than 24 players starts collapsed until the viewer
  presses the button, and the grid tile minimum drops to 44 px, six per row
  at 375 px. Desktop is unchanged.

Known limit at the time: the header (title, mode toggle, game, players,
decks, Options, Simulate) is 220 px tall at phone width, so the stats and
chart start below the fold.

## 2026-09-06: pacing, highlights and spoilers

### Playback pacing: straight, not phased

**Problem.** On a 40M-round game the phased plan spent the first half of
playback on the first hundred rounds. Straight playback reads better: the
field falling away almost at once is the truth of the game, and the chart
only colors a handful of lines anyway.

**Built.** "Slow the opening" is off by default (the phased plan is still
there behind the toggle). Off means one constant rate across the budget,
capped at one round per frame (60 rounds/s) while the field is crowded, so a
1000-player opening is about two seconds of cards flipping and then the game
runs proportionally. Small games never hit the cap. The default speed is
"game in ~1 min" ("game in ~30 s" since 2026-11-07).

### Highlight the top ten, configurable to twenty

**Problem.** Five colored lines came from a five-hue palette, not from a
decision about players. Ten reads better, and the count should be a setting
with a cap.

**Built.** The palette is ten hues (the original five plus five more); from
the eleventh highlight the hues come back paler and thinner. "Highlight the
top N" in the playback Options popover offers 5, 10 (the default), 15 and
20, saved per viewer and clamped to the player count. The tooltip lists at
most ten rows and says how many more are highlighted.

### No spoilers: color the leaders of the moment

**Problem.** Coloring the final top N from round 0 gives away the standings.

**Built.** While the outcome is hidden, everyone is ranked by what has
happened so far: players still in by cards held, then players already out,
most recent first. An eliminated player's rank is their final place and
never changes, so third place stays colored from the moment they go out.
The top N of that ranking are colored. Colors are sticky: a player keeps
their color until they fall well below the cutoff, and a player held by that
margin gives up their color when a real top-N entrant needs one. Scrubbing
backwards rebuilds the assignment deterministically. At the last round the
ranking equals the final standings, so nothing switches at the reveal.
Verified on a 200-player, 200-deck v2 game, an 8-player v1 game and a
6-seat Blackjack session.

## 2026-11-07: reproducible artifact builds, and a 30-second default

### The committed builds rebuild byte for byte

**Problem.** The WebAssembly bundle (`web/core/`) and `bin/lud-batch` are
committed so the server runs without a Rust toolchain, but nothing checked
that they matched the source. The wasm also embedded a home-directory path
from the cargo registry, and the bytes depended on host tools: the
`wasm-opt` version, the system linker and `strip`, and the wasm-bindgen
build on PATH.

**Built.** The artifacts are a function of the source and pinned tools only.
`core-rs/pinned-env.sh`, sourced by both build scripts, holds the pins:

- rustc 1.98.0 with the `wasm32-unknown-unknown` and
  `x86_64-unknown-linux-musl` targets. When they are missing, the scripts
  stop and print the `rustup toolchain install` command. The pin lives in
  the scripts, not a `rust-toolchain.toml`, so `cargo test` keeps running on
  current stable.
- wasm-bindgen 0.2.127, installed by `build-wasm.sh` with `cargo install
  --locked` under `core-rs/target/pinned-tools` and never taken from PATH. A
  copy installed without `--locked` pulled a newer walrus, which writes its
  version into the wasm and changed one byte.
- Every `cargo build` runs with `--locked`, and `--remap-path-prefix` maps
  the cargo home and the repo to fixed names, so no host path is embedded.

Neither script runs `wasm-opt`: its output depends on the binaryen version.
The wasm is 137 KB unoptimized. `build-native.sh` links the musl binary with
the rust-lld that ships with rustc and strips symbols through rustc
(`-C strip=symbols`). The system linker would tie the bytes to the host:
Fedora's binutils 2.45.1 and Ubuntu 24.04's 2.42 laid out the same code as
537,184 and 541,344 bytes. A C compiler is still needed, for the host-side proc
macros only.

`core-rs/check-artifacts.sh` rebuilds all three files and fails unless each
matches the committed copy byte for byte. CI runs it in an `artifacts` job on
`ubuntu-24.04`. It also passed in a clean `ubuntu:24.04` container as a
non-root user.

To rebuild by hand:

```
rustup toolchain install 1.98.0 --profile minimal \
  --target wasm32-unknown-unknown,x86_64-unknown-linux-musl
RUSTUP_TOOLCHAIN=1.98.0 core-rs/build-wasm.sh
RUSTUP_TOOLCHAIN=1.98.0 core-rs/build-native.sh
```

### Default speed: 30 seconds

The default playback speed is "game in ~30 s", down from a minute. The game
the demo plays on arrival (1,000 players, 256 decks) plays at it.
