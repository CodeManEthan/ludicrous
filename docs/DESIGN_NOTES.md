---
type: design-notes
project: ludicrous
description: Operator design notes from live use, spoken 2026-09-05, one per numbered item. Each carries the observation, what the code did at the time, and what was built on 2026-09-06 (uncommitted at time of writing).
---

# Design notes, 2026-09-05

## 1. Mobile: the screen jumps on every event

**Observation.** First time using Ludicrous on a phone. Events keep popping up during playback and each one moves the page up and down. Needs a fix so new events stop shifting the layout on mobile.

**What the code does today.**
- `web/index.html` has no mobile layout at all: `web/*.css` contains no `@media` rule.
- The round banner (`#banner`, `.banner` with `min-height: 22px`) is rewritten every rendered round by `describeRound` / `describeBlackjackRound`. On a narrow screen the text wraps to a varying number of lines, so its height changes round to round and everything below it (the table, the chart, the elimination timeline) moves.
- The out-strip (`#outStrip`) appears and grows as players go out, and tiles leave the grid in "collapse into a strip" mode, both of which reflow the grid.
- The elimination timeline (`#elimFeed`) is a list that grows during live playback.

**Direction to consider.** Reserve fixed space for the banner on small screens (fixed line count with ellipsis, or a fixed-height sticky strip), and keep the grid and out-strip from changing height when a player goes out. Open question for the operator: on mobile, should events land in a fixed overlay or ticker rather than in the page flow?

## 2. Big games: the chart looks frozen through the slow opening

**Observation.** Phased playback (from the scale round) plays the crowded opening of a big game slowly. The chart was not adjusted to match: for the first several seconds nothing visibly happens on it, and the lines only start to move once playback speeds up. The chart needs to start smaller so the early rounds are actually visible.

**What the code does today.**
- In suspense mode the x-axis already follows the playhead (`drawChart` in `web/app.js`), but its window has a floor of `max(pos * 1.25, sampleGap * 20, 50)` rounds. The series is downsampled to at most 1,200 samples across the game, so `sampleGap` is `rounds / 1200`. For a 7M-round game that floor is about 118,000 rounds.
- The opening phase plays at `OPENING_RATE = 3` rounds per second for up to 20% of the budget. So during a 6 s opening the playhead reaches round 18 inside a 118,000-round window: a fraction of a pixel of motion.
- The y-axis spans 0 to total cards for the whole game. With 200 players every line starts at 1/200 of the height, so early card swings are also invisible vertically.

**Direction to consider.** Give the opening its own axis window: keep full-resolution (undownsampled) samples for the opening rounds so the x floor can be small, and let the y-axis start near the opening's card range and grow toward the leader, the way the x-axis already grows. The floor of 20 samples exists so the early window is not too sparse to draw; that constraint moves to the sampling, not the axis.

## 3. Chart above the table by default, and a denser table on mobile

**Observation.** With the table on top and a big field, a phone shows about three players per row, and scrolling past all those cards to reach the chart is impractical. Put the chart on top by default. Then talk about how the table could adapt on mobile: more cards per row, smaller cards, or some shrinking.

**What the code does today.**
- "Chart above cards" already exists as a toggle in the playback Options popover (`chartTopChk`, stored as `layoutPrefs.chartFirst` in localStorage, applied as the `chart-first` class on `#results`). It defaults to off. Flipping the default is a one-line change in `applyLayoutPrefs` in `web/app.js`, plus deciding whether people who never touched the toggle should get the new default (they should: the pref is only written when the box is clicked, so treat "unset" as chart-first).
- The player grid is `repeat(auto-fill, minmax(76px, 1fr))` with an 8 px column gap, and each player tile carries a card image and a meta line. Nothing adapts to viewport width; there are no media queries.
- The out-strip already compacts eliminated players into chips, so late in a big game the grid is small. The problem is the opening, when everyone is still in.

**Direction to consider.**
- Default chart-first. Keep the toggle.
- A mobile grid: on narrow viewports drop the tile minimum to roughly 48 px, shrink or hide the card image, and put the name and count on one line, so a phone gets six to eight players per row.
- Above some player count on a phone, start the table collapsed (the collapse button already exists, stored as `layoutPrefs.tableCollapsed`) so the chart and banner are what you see, with the table one tap away.
- Whatever fixes note 1 (fixed-height banner and grid) should be designed together with this, since both are the first mobile layout the app has had.

## As built, 2026-09-06

All three notes are in the working tree. Verified headless in Chromium at 375 px and 1280 px on a 200-player, 200-deck War game, plus a Python-served 8-player game.

- **Note 1.** `web/style.css` gained its first media query (`max-width: 640px`, also read by `app.js` as `narrowScreen`). The round banner is clamped to exactly two lines (44 px) on phones, so the chart and table below it stay put during playback. Panel and page padding tighten, the chart drops to 220 px.
- **Note 2.** Chart sampling is now the 1,200 uniform points plus a dense opening: every round through 200, then 2% steps (`r += r/50`) until the uniform series is at least that fine. Implemented identically in the wasm prepare pass (`DENSE_ROUNDS`, `GEO_DIVISOR`, merged in `finish`), `web/app.js` (`chartSampleRounds`), and `server.py` (`chart_sample_rounds`). A 7M-round game has 1,600 samples instead of 1,201. In suspense mode `drawChart` keeps at least 12 samples on screen (so the opening window is 13 rounds, not 118,000), and the War y-axis starts at 2.5 opening stacks and follows the biggest stack so far, snapped to 5% steps. Series are clipped to the plot so future values above the live axis cannot leak.
- **Note 3.** Chart above the cards is the default (`layoutPrefs.chartFirst !== false`); the toggle still works. On a phone, a table with more than 24 players starts collapsed until the viewer presses the button, and the grid tile minimum drops to 44 px, six per row at 375 px. Desktop is unchanged.

Still open for mobile: the header (title, mode toggle, game, players, decks, Options, Simulate) is 220 px tall at phone width, so the stats and chart start below the fold.
