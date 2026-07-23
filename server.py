#!/usr/bin/env python3
"""Local web server for the War simulator.

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

from engine import WarGame, run_batch, summarize_batch
from engine import events as ev
from random_names import random_300_first_names

ROOT = Path(__file__).parent
WEB_DIR = ROOT / "web"
CARDS_DIR = ROOT / "cards"

MAX_PLAYERS = 100
MAX_DECKS = 100
MAX_ROUNDS = 1_000_000
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


def run_simulation(config: dict) -> dict:
    players = int(config.get("players", 4))
    decks = int(config.get("decks", 1))
    seed = config.get("seed")
    seed = int(seed) if seed not in (None, "") else random.randrange(1_000_000_000)
    if not 2 <= players <= MAX_PLAYERS:
        raise ValueError(f"players must be between 2 and {MAX_PLAYERS}")
    if not 1 <= decks <= MAX_DECKS:
        raise ValueError(f"decks must be between 1 and {MAX_DECKS}")

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
    while not game.is_over and game.round < MAX_ROUNDS:
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
    players = int(config.get("players", 4))
    decks = int(config.get("decks", 1))
    games = int(config.get("games", 100))
    seed = config.get("seed")
    base_seed = int(seed) if seed not in (None, "") else random.randrange(1_000_000)
    if not 2 <= players <= MAX_PLAYERS:
        raise ValueError(f"players must be between 2 and {MAX_PLAYERS}")
    if not 1 <= decks <= MAX_DECKS:
        raise ValueError(f"decks must be between 1 and {MAX_DECKS}")
    if not 1 <= games <= MAX_BATCH_GAMES:
        raise ValueError(f"games must be between 1 and {MAX_BATCH_GAMES}")

    start_time = time.perf_counter()
    rows = run_batch(players, decks, games, base_seed=base_seed, max_rounds=MAX_ROUNDS)
    elapsed = time.perf_counter() - start_time
    return {
        "config": {
            "players": players,
            "decks": decks,
            "games": games,
            "base_seed": base_seed,
            "total_cards": decks * 52,
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
    parser = argparse.ArgumentParser(description="War simulator web server")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"War simulator running at http://localhost:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
