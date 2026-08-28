"""Run many games in parallel and aggregate the statistics.

Games are seeded base_seed, base_seed+1, ... base_seed+N-1, so a batch is
fully reproducible and any individual game can be replayed later from its
seed. Simulation fans out across CPU cores with one process per core — the
per-game event log is disabled (record_events=False) so workers stay fast
and small.
"""
from __future__ import annotations

import atexit
import statistics
import threading
from concurrent.futures import BrokenExecutor, ProcessPoolExecutor

from .blackjack import BlackjackGame
from .war import WarGame

# One worker pool for the whole process, created on first use. Spinning up a
# ProcessPoolExecutor costs tens of milliseconds — more than a small batch
# takes to run — so the pool is kept alive and shared across calls instead.
_pool: ProcessPoolExecutor | None = None
_pool_lock = threading.Lock()


def _get_pool() -> ProcessPoolExecutor:
    """The shared pool, started on demand.

    Creation is locked because the threaded web server can enter run_batch()
    from several request threads at once. Using the pool needs no lock:
    Executor.submit (and so map) is itself thread-safe.
    """
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ProcessPoolExecutor()
    return _pool


@atexit.register
def _shutdown_pool() -> None:
    """Stop the workers so the CLI and the test runner exit cleanly."""
    global _pool
    pool, _pool = _pool, None
    if pool is not None:
        pool.shutdown(wait=True)


def _run_chunk(worker, chunk: list) -> list:
    """One pool task = one chunk of games (same batching pool.map used)."""
    return [worker(args) for args in chunk]


def _parallel(worker, args_list: list, progress=None) -> list:
    """Run worker over args_list on the pool; results in input order.

    progress, if given, is called as progress(done_items, total_items) from
    executor callback threads as chunks finish. It must be thread-safe and
    should never raise (a raise here would leak into the executor's callback
    machinery, not the caller).
    """
    if len(args_list) == 1:
        results = [worker(args_list[0])]
        if progress is not None:
            progress(1, 1)
        return results

    def attempt() -> list:
        pool = _get_pool()
        chunk = max(1, len(args_list) // ((pool._max_workers or 1) * 8))
        chunks = [args_list[i:i + chunk] for i in range(0, len(args_list), chunk)]
        futures = [pool.submit(_run_chunk, worker, c) for c in chunks]
        if progress is not None:
            total = len(args_list)
            counted = {"done": 0}
            count_lock = threading.Lock()
            sizes = {id(f): len(c) for f, c in zip(futures, chunks)}

            def _on_done(fut):
                with count_lock:
                    counted["done"] += sizes[id(fut)]
                    done = counted["done"]
                progress(done, total)

            for f in futures:
                f.add_done_callback(_on_done)
        results: list = []
        for f in futures:
            results.extend(f.result())
        return results

    try:
        return attempt()
    except BrokenExecutor:
        # A worker died (an OOM kill, say). A fresh pool per call used to
        # absorb that; now the pool outlives the call, so retire the broken
        # one and retry once rather than poisoning every later batch.
        _shutdown_pool()
        return attempt()


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
    progress=None,
) -> list[dict]:
    """Simulate num_games games; returns one summary row per game, in seed order."""
    # Validate the config once up front (workers would each raise otherwise).
    WarGame(num_players, num_decks, seed=0)
    args = [
        (num_players, num_decks, seed, max_rounds)
        for seed in range(base_seed, base_seed + num_games)
    ]
    return _parallel(_run_one, args, progress=progress)


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
    progress=None,
) -> list[dict]:
    """Simulate num_games blackjack sessions; one summary row per session."""
    BlackjackGame(num_seats, num_decks, num_rounds, strategies=strategies, seed=0)
    args = [
        (num_seats, num_decks, num_rounds, tuple(strategies), seed)
        for seed in range(base_seed, base_seed + num_games)
    ]
    return _parallel(_run_one_blackjack, args, progress=progress)


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
