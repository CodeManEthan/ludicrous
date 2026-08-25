"""Dump a Python event recording as NDJSON, for the Rust JSON sink to match.

One line per event, exactly `json.dumps(event.to_dict())`. The Rust writer
is hand-rolled, so this is the only thing standing between it and a subtle
key-order or spacing drift that would break every replay client.

    python3 core-rs/oracle/gen_event_fixture.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)

from engine.war import WarGame  # noqa: E402

OUT_DIR = os.path.join(HERE, "..", "crates", "ludicrous-core", "tests", "data")

# Small games, chosen because they hit wars, forfeits and a draw between
# them -- a 6-player game would produce a megabyte of high-card rounds and
# prove less.
CASES = [(4, 1, 3), (2, 1, 0), (5, 1, 11)]


def main():
    for players, decks, seed in CASES:
        g = WarGame(num_players=players, num_decks=decks, seed=seed)
        g.run(max_rounds=2_000_000)
        name = f"events_{players}p{decks}d_seed{seed}.ndjson"
        path = os.path.join(OUT_DIR, name)
        with open(path, "w") as fh:
            for e in g.events:
                fh.write(json.dumps(e.to_dict()) + "\n")
        print(f"{name}: {len(g.events)} events, {g.round} rounds")


if __name__ == "__main__":
    main()
