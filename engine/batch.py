"""Run many games in parallel and aggregate the statistics.

Games are seeded base_seed, base_seed+1, ... base_seed+N-1, so a batch is
fully reproducible and any individual game can be replayed later from its
seed. Simulation fans out across CPU cores with one process per core — the
per-game event log is disabled (record_events=False) so workers stay fast
and small.
"""
from __future__ import annotations

import statistics
from concurrent.futures import ProcessPoolExecutor

from .war import WarGame


def _run_one(args: tuple[int, int, int, int]) -> dict:
    num_players, num_decks, seed, max_rounds = args
    game = WarGame(num_players, num_decks, seed=seed, record_events=False)
    game.run(max_rounds=max_rounds)
    return {
        "seed": seed,
        "completed": game.is_over,
        "rounds": game.round,
        "winner": game.winner,
        "wars": game.war_count,
        "deepest_war": game.deepest_war,
        "biggest_pot": game.biggest_pot,
    }


def run_batch(
    num_players: int,
    num_decks: int,
    num_games: int,
    base_seed: int = 0,
    max_rounds: int = 1_000_000,
    workers: int | None = None,
) -> list[dict]:
    """Simulate num_games games; returns one summary row per game, in seed order."""
    # Validate the config once up front (workers would each raise otherwise).
    WarGame(num_players, num_decks, seed=0)
    args = [
        (num_players, num_decks, seed, max_rounds)
        for seed in range(base_seed, base_seed + num_games)
    ]
    if num_games == 1:
        return [_run_one(args[0])]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        chunk = max(1, num_games // ((pool._max_workers or 1) * 8))
        return list(pool.map(_run_one, args, chunksize=chunk))


def summarize_batch(games: list[dict]) -> dict:
    """Aggregate statistics over run_batch() rows."""
    rounds = [g["rounds"] for g in games]
    wins_by_seat: dict[int, int] = {}
    for g in games:
        if g["winner"] is not None:
            wins_by_seat[g["winner"]] = wins_by_seat.get(g["winner"], 0) + 1
    by_rounds = sorted(games, key=lambda g: g["rounds"])
    return {
        "games": len(games),
        "completed": sum(1 for g in games if g["completed"]),
        "rounds": {
            "min": min(rounds),
            "max": max(rounds),
            "mean": statistics.fmean(rounds),
            "median": statistics.median(rounds),
            "stdev": statistics.stdev(rounds) if len(rounds) > 1 else 0.0,
        },
        "mean_wars": statistics.fmean(g["wars"] for g in games),
        "deepest_war": max(g["deepest_war"] for g in games),
        "biggest_pot": max(g["biggest_pot"] for g in games),
        "wins_by_seat": wins_by_seat,
        "shortest": by_rounds[:5],
        "longest": by_rounds[-5:][::-1],
    }
