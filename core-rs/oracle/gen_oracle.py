"""Run the Python War engine over a fixed grid and dump one JSON row per game.

The Rust port replays exactly these (players, decks, seed) triples with its
test-only CPython RNG and must reproduce every field. Different RNG designs
can't be compared directly, so this is how the *rules* get proved equal
before the seed namespace moves to xoshiro.

    python3 core-rs/oracle/gen_oracle.py

Writes core-rs/crates/ludicrous-core/tests/data/oracle_war.jsonl.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)

from engine.war import WarGame  # noqa: E402

DATA = os.path.join(HERE, "..", "crates", "ludicrous-core", "tests", "data")
OUT = os.path.join(DATA, "oracle_war.jsonl")
OUT_CAPPED = os.path.join(DATA, "oracle_war_capped.jsonl")

# A safety cap both sides share, so a pathological game can't hang the suite.
# Games that hit it are still compared -- `completed: false` is a real result.
MAX_ROUNDS = 2_000_000


def grid():
    """(players, decks, seed) triples.

    Weighted towards tiny games: 2-4 players on a single deck is where the
    Modified / Modified Forfeit / Draw tiebreakers actually fire. The big
    configs are there to prove the round-robin deal and the reserve
    reshuffle hold up at scale.
    """
    cases = []
    # Exotic-tiebreaker territory.
    for p in (2, 3, 4, 5):
        for seed in range(30):
            cases.append((p, 1, seed))
    # The everyday shapes.
    for p in (2, 3, 4, 6, 8, 10, 13, 26, 52):
        for d in (1, 2, 3, 5, 13):
            if d * 52 < p:
                continue
            for seed in range(4):
                cases.append((p, d, seed + 100))
    # Wide tables.
    for p in (60, 100):
        for d in (2, 13, 50):
            if d * 52 < p:
                continue
            for seed in range(3):
                cases.append((p, d, seed + 200))
    # Awkward deals: card count doesn't divide evenly by player count.
    for p, d in ((7, 1), (11, 1), (15, 2), (33, 3), (99, 5)):
        for seed in range(6):
            cases.append((p, d, seed + 300))
    return cases


def row(players, decks, seed, max_rounds=MAX_ROUNDS):
    g = WarGame(num_players=players, num_decks=decks, seed=seed, record_events=False)
    s = g.run(max_rounds=max_rounds)
    return {
        "num_players": players,
        "num_decks": decks,
        "seed": seed,
        "max_rounds": max_rounds,
        "completed": s["completed"],
        "rounds": s["rounds"],
        "wars": g.war_count,
        "deepest_war": g.deepest_war,
        "biggest_pot": g.biggest_pot,
        "winner": s["winner"],
        "standings": s["standings"],
        "eliminations": sum(1 for p in g.players.values() if not p.in_game),
        "card_counts": [g.players[i].card_count for i in range(1, players + 1)],
        "round_out": [
            -1 if g.players[i].round_out is None else g.players[i].round_out
            for i in range(1, players + 1)
        ],
    }


def main():
    cases = grid()
    t0 = time.perf_counter()
    with open(OUT, "w") as fh:
        for i, (p, d, seed) in enumerate(cases):
            fh.write(json.dumps(row(p, d, seed), separators=(",", ":")) + "\n")
            if (i + 1) % 100 == 0:
                print(
                    f"  {i + 1}/{len(cases)}  ({time.perf_counter() - t0:.1f}s)",
                    flush=True,
                )
    print(f"{len(cases)} games -> {os.path.relpath(OUT, REPO)} "
          f"in {time.perf_counter() - t0:.1f}s")

    # Same grid, stopped early. Comparing a game frozen mid-flight checks
    # per-round bookkeeping -- live card counts, elimination rounds,
    # standings among survivors -- that a finished game hides, and it is the
    # only thing that exercises the max_rounds cap.
    t0 = time.perf_counter()
    n = 0
    with open(OUT_CAPPED, "w") as fh:
        for i, (p, d, seed) in enumerate(cases):
            cap = (7, 40, 250, 1500)[i % 4]
            fh.write(
                json.dumps(row(p, d, seed, max_rounds=cap), separators=(",", ":")) + "\n"
            )
            n += 1
    print(f"{n} capped games -> {os.path.relpath(OUT_CAPPED, REPO)} "
          f"in {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
