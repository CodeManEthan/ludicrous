#!/usr/bin/env python3
"""Local web server for Ludicrous.

Serves the browser UI from web/, card images from cards/, and a single API
endpoint:

    POST /api/simulate   {"players": 6, "decks": 3, "seed": 42, "names": "random"}

The response is a game recording. Small games return mode "full" (every event,
for card-by-card playback). Games whose event log exceeds FULL_EVENT_BUDGET
return mode "condensed" (chart timeline + milestones only) to keep the payload
browser-sized. Standard library only — no dependencies.

Run:  python3 server.py  [--port 8000]
"""
import argparse
import json
import random
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from engine import (
    BlackjackGame,
    WarGame,
    run_batch,
    run_blackjack_batch,
    summarize_batch,
    summarize_blackjack_batch,
)
from engine import events as ev
from random_names import random_300_first_names

ROOT = Path(__file__).parent
WEB_DIR = ROOT / "web"
CARDS_DIR = ROOT / "cards"

MAX_PLAYERS = 100
MAX_DECKS = 100
DEFAULT_MAX_ROUNDS = 1_000_000  # war safety cap (games stopped here are "unfinished")
MAX_ROUNDS_CEILING = 20_000_000
MAX_BJ_ROUNDS = 10_000
MAX_BATCH_GAMES = 10_000
FULL_EVENT_BUDGET = 250_000  # events; ~25 MB of JSON is the ceiling for playback mode
CHART_POINTS = 1200


def make_names(num_players: int, mode: str, rng: random.Random) -> list[str] | None:
    if mode != "random":
        return None
    pool = random_300_first_names()
    rng.shuffle(pool)
    return [
        pool[i % len(pool)] if i < len(pool) else f"{pool[i % len(pool)]} {i // len(pool) + 1}"
        for i in range(num_players)
    ]


def build_chart(counts_series: dict[int, list[int]], total_rounds: int) -> dict:
    """Downsample per-round card counts to <= CHART_POINTS samples per player.

    counts_series[pid][r] is the player's count after round r (index 0 = deal);
    the list simply ends once the player is eliminated.
    """
    num_samples = min(total_rounds, CHART_POINTS)
    sample_rounds = sorted({round(i * total_rounds / num_samples) for i in range(num_samples + 1)})
    series = {
        pid: [counts[r] if r < len(counts) else None for r in sample_rounds]
        for pid, counts in counts_series.items()
    }
    return {"rounds": sample_rounds, "series": series}


def run_blackjack_simulation(config: dict) -> dict:
    seats = int(config.get("players", 4))
    decks = int(config.get("decks", 6))
    rounds = int(config.get("rounds", 100))
    strategies = config.get("strategies") or ["basic"]
    seed = config.get("seed")
    seed = int(seed) if seed not in (None, "") else random.randrange(1_000_000_000)
    if not 1 <= seats <= MAX_PLAYERS:
        raise ValueError(f"seats must be between 1 and {MAX_PLAYERS}")
    if not 1 <= decks <= MAX_DECKS:
        raise ValueError(f"decks must be between 1 and {MAX_DECKS}")
    if not 1 <= rounds <= MAX_BJ_ROUNDS:
        raise ValueError(f"rounds must be between 1 and {MAX_BJ_ROUNDS}")

    game = BlackjackGame(seats, decks, rounds, strategies=strategies, seed=seed)
    game.start()
    full_events = [e.to_dict() for e in game.events]
    bankroll_series = {sid: [0.0] for sid in game.seats}
    game.events.clear()
    condensed = False

    while not game.is_over:
        round_events = game.play_round()
        for event in round_events:
            if isinstance(event, ev.RoundSettled):
                for sid, bankroll in event.bankrolls.items():
                    bankroll_series[sid].append(bankroll)
        if not condensed:
            full_events.extend(event.to_dict() for event in round_events)
            if len(full_events) > FULL_EVENT_BUDGET:
                condensed = True
                full_events = None
        game.events.clear()

    summary = game.summary()
    response = {
        "game": "blackjack",
        "summary": summary,
        "stats": {
            "hands": seats * rounds,
            "net": round(sum(s.bankroll for s in game.seats.values()), 1),
            "blackjacks": sum(s.blackjacks for s in game.seats.values()),
            "busts": sum(s.busts for s in game.seats.values()),
            "splits": sum(s.splits for s in game.seats.values()),
        },
        "names": {s.id: s.name for s in game.seats.values()},
        "strategies": {s.id: s.strategy_name for s in game.seats.values()},
    }
    if condensed:
        response["mode"] = "condensed"
        response["chart"] = build_chart(bankroll_series, game.round)
    else:
        response["mode"] = "full"
        response["events"] = full_events
    return response


def run_simulation(config: dict) -> dict:
    if config.get("game") == "blackjack":
        return run_blackjack_simulation(config)
    players = int(config.get("players", 4))
    decks = int(config.get("decks", 1))
    seed = config.get("seed")
    seed = int(seed) if seed not in (None, "") else random.randrange(1_000_000_000)
    max_rounds = int(config.get("max_rounds") or DEFAULT_MAX_ROUNDS)
    if not 2 <= players <= MAX_PLAYERS:
        raise ValueError(f"players must be between 2 and {MAX_PLAYERS}")
    if not 1 <= decks <= MAX_DECKS:
        raise ValueError(f"decks must be between 1 and {MAX_DECKS}")
    if not 1 <= max_rounds <= MAX_ROUNDS_CEILING:
        raise ValueError(f"max_rounds must be between 1 and {MAX_ROUNDS_CEILING:,}")

    names = make_names(players, config.get("names", "default"), random.Random(seed))
    game = WarGame(players, decks, player_names=names, seed=seed)

    game.start()
    full_events = [e.to_dict() for e in game.events]
    counts_series = {pid: [count] for pid, count in game.card_counts().items()}
    game.events.clear()

    eliminations = []
    condensed = False

    # Stream rounds: harvest each round's events, then drop them so memory
    # stays bounded no matter how long the game runs.
    while not game.is_over and game.round < max_rounds:
        round_events = game.play_round()
        for event in round_events:
            if isinstance(event, ev.RoundEnded):
                for pid, count in event.card_counts.items():
                    counts_series[pid].append(count)
            elif isinstance(event, ev.PlayerEliminated):
                counts_series[event.player].append(0)  # let chart lines touch zero
                eliminations.append({"round": event.round, "player": event.player})
        if not condensed:
            full_events.extend(event.to_dict() for event in round_events)
            if len(full_events) > FULL_EVENT_BUDGET:
                condensed = True
                full_events = None
        game.events.clear()

    response = {
        "game": "war",
        "summary": game.summary(),
        "stats": {
            "wars": game.war_count,
            "deepest_war": game.deepest_war,
            "biggest_pot": game.biggest_pot,
            "total_cards": decks * 52,
        },
        "names": {pid: p.name for pid, p in game.players.items()},
    }
    if condensed:
        response["mode"] = "condensed"
        response["chart"] = build_chart(counts_series, game.round)
        response["eliminations"] = eliminations
    else:
        response["mode"] = "full"
        response["events"] = full_events
    return response


def run_batch_api(config: dict) -> dict:
    if config.get("game") == "blackjack":
        seats = int(config.get("players", 4))
        decks = int(config.get("decks", 6))
        rounds = int(config.get("rounds", 100))
        games = int(config.get("games", 100))
        strategies = config.get("strategies") or ["basic"]
        seed = config.get("seed")
        base_seed = int(seed) if seed not in (None, "") else random.randrange(1_000_000)
        if not 1 <= seats <= MAX_PLAYERS:
            raise ValueError(f"seats must be between 1 and {MAX_PLAYERS}")
        if not 1 <= decks <= MAX_DECKS:
            raise ValueError(f"decks must be between 1 and {MAX_DECKS}")
        if not 1 <= rounds <= MAX_BJ_ROUNDS:
            raise ValueError(f"rounds must be between 1 and {MAX_BJ_ROUNDS}")
        if not 1 <= games <= MAX_BATCH_GAMES:
            raise ValueError(f"games must be between 1 and {MAX_BATCH_GAMES}")
        start_time = time.perf_counter()
        rows = run_blackjack_batch(seats, decks, rounds, games, strategies,
                                   base_seed=base_seed)
        elapsed = time.perf_counter() - start_time
        return {
            "game": "blackjack",
            "config": {
                "players": seats,
                "decks": decks,
                "rounds": rounds,
                "games": games,
                "strategies": strategies,
                "base_seed": base_seed,
            },
            "elapsed": elapsed,
            "aggregate": summarize_blackjack_batch(rows),
            "games": rows,
        }

    players = int(config.get("players", 4))
    decks = int(config.get("decks", 1))
    games = int(config.get("games", 100))
    max_rounds = int(config.get("max_rounds") or DEFAULT_MAX_ROUNDS)
    seed = config.get("seed")
    base_seed = int(seed) if seed not in (None, "") else random.randrange(1_000_000)
    if not 2 <= players <= MAX_PLAYERS:
        raise ValueError(f"players must be between 2 and {MAX_PLAYERS}")
    if not 1 <= decks <= MAX_DECKS:
        raise ValueError(f"decks must be between 1 and {MAX_DECKS}")
    if not 1 <= games <= MAX_BATCH_GAMES:
        raise ValueError(f"games must be between 1 and {MAX_BATCH_GAMES}")
    if not 1 <= max_rounds <= MAX_ROUNDS_CEILING:
        raise ValueError(f"max_rounds must be between 1 and {MAX_ROUNDS_CEILING:,}")

    start_time = time.perf_counter()
    rows = run_batch(players, decks, games, base_seed=base_seed, max_rounds=max_rounds)
    elapsed = time.perf_counter() - start_time
    return {
        "game": "war",
        "config": {
            "players": players,
            "decks": decks,
            "games": games,
            "base_seed": base_seed,
            "total_cards": decks * 52,
            "max_rounds": max_rounds,
        },
        "elapsed": elapsed,
        "aggregate": summarize_batch(rows),
        "games": rows,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean.startswith("/cards/"):
            # Serve card art from the existing cards/ folder (basename only,
            # so no path traversal).
            return str(CARDS_DIR / Path(clean).name)
        return super().translate_path(path)

    def do_POST(self):
        routes = {"/api/simulate": run_simulation, "/api/batch": run_batch_api}
        handler = routes.get(self.path)
        if handler is None:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            config = json.loads(self.rfile.read(length) or b"{}")
            body = json.dumps(handler(config)).encode()
            status = 200
        except (ValueError, TypeError, KeyError) as error:
            body = json.dumps({"error": str(error)}).encode()
            status = 400
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Ludicrous web server")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Ludicrous running at http://localhost:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
