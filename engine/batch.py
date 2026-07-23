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

from .blackjack import BlackjackGame
from .war import WarGame


def _parallel(worker, args_list: list) -> list:
    if len(args_list) == 1:
        return [worker(args_list[0])]
    with ProcessPoolExecutor() as pool:
        chunk = max(1, len(args_list) // ((pool._max_workers or 1) * 8))
        return list(pool.map(worker, args_list, chunksize=chunk))


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
    return _parallel(_run_one, args)


def summarize_batch(games: list[dict]) -> dict:
    """Aggregate statistics over run_batch() rows.

    Games stopped by the max-rounds cap ("unfinished") are excluded from the
    rounds distribution and wars-per-game — including capped values would
    bias every statistic low. They still appear in the outlier lists (their
    rows carry completed=False) and are counted in "unfinished".
    """
    finished = [g for g in games if g["completed"]]
    distribution_source = finished or games  # all-unfinished edge case
    rounds = [g["rounds"] for g in distribution_source]
    wins_by_seat: dict[int, int] = {}
    for g in games:
        if g["winner"] is not None:
            wins_by_seat[g["winner"]] = wins_by_seat.get(g["winner"], 0) + 1
    by_rounds = sorted(games, key=lambda g: g["rounds"])
    return {
        "games": len(games),
        "completed": len(finished),
        "unfinished": len(games) - len(finished),
        "rounds": {
            "min": min(rounds),
            "max": max(rounds),
            "mean": statistics.fmean(rounds),
            "median": statistics.median(rounds),
            "stdev": statistics.stdev(rounds) if len(rounds) > 1 else 0.0,
        },
        "mean_wars": statistics.fmean(g["wars"] for g in distribution_source),
        "deepest_war": max(g["deepest_war"] for g in games),
        "biggest_pot": max(g["biggest_pot"] for g in games),
        "wins_by_seat": wins_by_seat,
        "shortest": by_rounds[:5],
        "longest": by_rounds[-5:][::-1],
    }


# --------------------------------------------------------------- blackjack

def _run_one_blackjack(args: tuple[int, int, int, tuple, int]) -> dict:
    num_seats, num_decks, num_rounds, strategies, seed = args
    game = BlackjackGame(num_seats, num_decks, num_rounds,
                         strategies=list(strategies), seed=seed,
                         record_events=False)
    game.run()
    return {
        "seed": seed,
        "net": round(sum(s.bankroll for s in game.seats.values()), 1),
        "per_strategy": {
            name: {"hands": entry["hands"], "net": entry["net"],
                   "wins": 0}  # per-seat win detail lives in per-session replay
            for name, entry in game.per_strategy().items()
        },
        "best_seat": round(max(s.bankroll for s in game.seats.values()), 1),
        "worst_seat": round(min(s.bankroll for s in game.seats.values()), 1),
    }


def run_blackjack_batch(
    num_seats: int,
    num_decks: int,
    num_rounds: int,
    num_games: int,
    strategies: list[str],
    base_seed: int = 0,
) -> list[dict]:
    """Simulate num_games blackjack sessions; one summary row per session."""
    BlackjackGame(num_seats, num_decks, num_rounds, strategies=strategies, seed=0)
    args = [
        (num_seats, num_decks, num_rounds, tuple(strategies), seed)
        for seed in range(base_seed, base_seed + num_games)
    ]
    return _parallel(_run_one_blackjack, args)


def summarize_blackjack_batch(sessions: list[dict]) -> dict:
    """Aggregate statistics over run_blackjack_batch() rows."""
    per_strategy: dict[str, dict] = {}
    for session in sessions:
        for name, entry in session["per_strategy"].items():
            agg = per_strategy.setdefault(name, {"hands": 0, "net": 0.0})
            agg["hands"] += entry["hands"]
            agg["net"] += entry["net"]
    for agg in per_strategy.values():
        agg["net"] = round(agg["net"], 1)
        agg["ev"] = agg["net"] / agg["hands"] if agg["hands"] else 0.0
    nets = [s["net"] for s in sessions]
    total_hands = sum(a["hands"] for a in per_strategy.values())
    total_net = round(sum(a["net"] for a in per_strategy.values()), 1)
    by_net = sorted(sessions, key=lambda s: s["net"])
    return {
        "games": len(sessions),
        "hands": total_hands,
        "net": total_net,
        "ev": total_net / total_hands if total_hands else 0.0,
        "per_strategy": per_strategy,
        "session_net": {
            "min": min(nets),
            "max": max(nets),
            "mean": statistics.fmean(nets),
            "stdev": statistics.stdev(nets) if len(nets) > 1 else 0.0,
        },
        "worst": by_net[:5],
        "best": by_net[-5:][::-1],
    }
