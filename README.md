---
type: repo-readme
project: ludicrous
description: "Top-level README for Ludicrous: card games (War, Blackjack) simulated at absurd scale by a dependency-free Python engine, played back in the browser — features, quickstart, CLI, rules, project layout, history of the tkinter-to-headless rebuild."
tags: [reference, simulation, cli, ui]
updated: 2026-07-30
---

# Ludicrous

Games at impossible scale. Take a game meant for a kitchen table — War,
Blackjack, more to come — and expand it far beyond what could ever be played
in real life: 1,000 players, 1,000 decks, a hundred million rounds, thousands of games in
parallel. Simulate the entire thing in seconds, then play it back in the
browser at any speed: scrub it like a video, watch rounds unfold card by
card, and chart how the game evolved.

The name is the point: *ludicrous* descends from Latin *ludus* — game — so it
means both "of games" and "absurdly extreme." Both senses apply.

Built as a headless Python engine (no dependencies) with a web frontend.

## Features

- **Two games** — War (pure luck, up to 1,000 players) and Blackjack (multi-seat
  vs the dealer, S17, 3:2 blackjacks, doubling, pair splitting)
- **Pluggable strategies** — assign hit/stand policies per blackjack seat
  (basic strategy, hit-below-N, never-bust) and measure which actually wins:
  the batch view charts EV per hand by strategy over hundreds of thousands of
  hands
- **2-1,000 players, 1-1,000 decks** — scale games far beyond what's physically playable
- **Instant simulation** — hundreds of thousands of rounds per second; even a
  2,600-card game finishes in seconds
- **Video-style playback** — play/pause, 1 to 5,000 rounds/sec, a scrubber,
  single-round stepping, and "pause on eliminations"
- **Live table view** — real card faces for every player, war contenders and
  round winners highlighted, eliminated players dimmed with final placements
- **Card-count chart** — the shape of the whole game at a glance; hover for
  values, click to jump to any round
- **Batch statistics** — run thousands of games on the native Rust core across every CPU core;
  histogram of game lengths, wins by seat, and outlier games you can replay
  card by card from their seed
- **Reproducible games** — seeded RNG: the same seed always produces the same
  game, shareable via URL (`/?players=6&decks=3&seed=1&run=1`)
- **Recordings** — save games as JSON from the CLI and import them in the browser
- **Aggregate view** — games too long for card-by-card playback automatically
  show the chart, stats, and elimination timeline instead

## Getting Started

Requires Python 3.10+ — nothing else. No packages to install.

```bash
git clone https://github.com/CodeManEthan/ludicrous.git
cd ludicrous
python3 server.py
```

Open http://localhost:8000, configure a game, and hit **Simulate**.

### CLI

Simulate games without the browser:

```bash
python3 simulate.py -p 100 -d 50 --seed 42      # 100 players, 50 decks, reproducible
python3 simulate.py -p 6 -d 3 --json game.json  # save a recording (importable in the web UI)
python3 simulate.py -p 4 --batch 1000 --seed 0  # 1,000-game batch statistics
python3 simulate.py --game blackjack -p 4 --strategies basic,hit-below-17
python3 simulate.py --game blackjack -p 5 --batch 200 --rounds 500 \
    --strategies basic,never-bust               # compare strategy EVs over 500k hands
```

## Game Rules

War is a simple card game:

1. The deck is shuffled and dealt evenly to all players
2. Each round, all players flip their top card
3. The player with the highest card wins all cards played that round
4. If there's a tie, those players go to "War":
   - Each tied player places 3 cards face down
   - Then draws another card face up
   - Highest card wins all cards
5. The game continues until one player has all the cards

**Card Rankings:** 2 (lowest) through 10, Jack, Queen, King, Ace (highest).

**Multiple Decks:** identical cards are equal rank — two Aces of Spades from
different decks go to War like any other tie.

**Tiebreaker edge cases** (players short on cards, drawn wars) are detailed in
[docs/GAME_RULES.txt](docs/GAME_RULES.txt) and implemented in `engine/war.py`.

## Project Structure

```
ludicrous/
├── engine/                   # Headless game engine — see docs/ENGINE.md
│   ├── cards.py              # Card primitives, deck building
│   ├── events.py             # Event vocabulary (the recording format)
│   ├── war.py                # WarGame: rules, state, event emission
│   ├── blackjack.py          # BlackjackGame + strategies (basic, hit-below-N, …)
│   └── batch.py              # Parallel batch simulation for both games (War batches
│                             #   run on bin/lud-batch when it is present; Python is the fallback)
├── server.py                 # Web server (stdlib only) — python3 server.py
├── web/                      # Browser playback UI (HTML/CSS/JS, no build step)
├── simulate.py               # CLI simulator
├── random_names.py           # Random player-name pool
├── tests/                    # Engine test suite
├── cards/                    # Card image assets (52 faces + backs)
└── docs/
    ├── ENGINE.md             # Engine API and recording format
    ├── GAME_RULES.txt        # Full rules text
    └── archive/              # Docs from the retired tkinter version
```

## Development

The game logic lives entirely in the `engine/` package — pure Python, no UI
imports, fully deterministic under a seed. Any frontend (the web UI, the CLI,
future games) consumes the event recordings it produces. See
[docs/ENGINE.md](docs/ENGINE.md) for the API and event format.

Run the tests:

```bash
python3 -m unittest discover -v
```

## History

This project began as a tkinter desktop app simulating the card game War (my
first Python GUI project). In July 2026 it was rebuilt around a headless
engine with a web frontend; the final tkinter version is preserved in git
history (tag point: the "Snapshot: final tkinter version" commit) and its
docs live in `docs/archive/`. Once Blackjack joined and more games were
planned, "war-card-game" no longer fit — the project was renamed
**Ludicrous**.

## Future Ideas

- [x] Batch statistics — run N seeds, chart the distribution of game lengths
- [x] Second game with player-selectable strategies (Blackjack)
- [x] Blackjack pair splitting (validated: basic strategy measures the published ≈−0.5% EV)
- [ ] Blackjack rule extensions: insurance, surrender, card-counting strategies
- [ ] Go Fish — hidden information and memory-based strategies
- [ ] Sound effects and card animations in playback
- [ ] Network multiplayer / shared spectating

## License

This project is open source and available under the MIT License.

## Credits

- Card faces: [Vector Playing Cards](https://code.google.com/archive/p/vector-playing-cards/) by Byron Knoll, released into the public domain
- Card backs: [Colorful Poker Card Back](https://opengameart.org/content/colorful-poker-card-back) by jeffshee, licensed [CC-BY 3.0](https://creativecommons.org/licenses/by/3.0/)
- Developed as a learning project
