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
import gzip
import json
import math
import os
import random
import subprocess
import sys
import threading
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

# The Python engine paths (single War games replayed from old links, the
# batch fallback, all of Blackjack) keep the old limits: Python at 1000
# players and 1000 decks is hours per request. The native batch runner and
# the browser engine take the larger caps.
PY_MAX_PLAYERS = 200
PY_MAX_DECKS = 200
MAX_PLAYERS = 1000
MAX_DECKS = 1000
DEFAULT_MAX_ROUNDS = 1_000_000  # what a pre-uncapped link meant when it said nothing
MAX_ROUNDS_CEILING = 20_000_000  # Python-run War games stop here even when asked for no cap
NATIVE_BATCH = ROOT / "bin" / "lud-batch"
ROUNDS_GRID = WEB_DIR / "rounds-grid.json"
BATCH_ROUND_BUDGET = 5_000_000_000  # games x typical rounds; a few seconds native here
MAX_BJ_ROUNDS = 10_000
MAX_BATCH_GAMES = 10_000
FULL_EVENT_BUDGET = 250_000  # events; ~25 MB of JSON is the ceiling for playback mode
CHART_POINTS = 1200
GZIP_LEVEL = 6  # event JSON is highly repetitive: ~16x smaller, and level 6
                # costs far less than shipping the extra megabytes


def accepts_gzip(header: str | None) -> bool:
    """True if an Accept-Encoding header asks for gzip (and not with q=0)."""
    for part in (header or "").split(","):
        token, _, params = part.strip().partition(";")
        if token.strip().lower() not in ("gzip", "*"):
            continue
        for param in params.split(";"):
            key, _, value = param.partition("=")
            if key.strip().lower() == "q":
                try:
                    if float(value.strip()) == 0:
                        return False
                except ValueError:
                    pass
        return True
    return False


def make_names(num_players: int, mode: str, rng: random.Random) -> list[str] | None:
    if mode != "random":
        return None
    pool = random_300_first_names()
    rng.shuffle(pool)
    return [
        pool[i % len(pool)] if i < len(pool) else f"{pool[i % len(pool)]} {i // len(pool) + 1}"
        for i in range(num_players)
    ]


# Every round through here is a chart sample, then 2% steps until the uniform
# series is at least that fine. The opening of a big game is a few hundred
# rounds that playback spends real seconds on, and a uniform series puts them
# all in one pixel. Mirrored in web/app.js (chartSampleRounds) and the wasm
# prepare pass (DENSE_ROUNDS / GEO_DIVISOR in prepared.rs).
CHART_DENSE_ROUNDS = 200
CHART_GEO_DIVISOR = 50


def chart_sample_rounds(total_rounds: int) -> list[int]:
    num_samples = min(total_rounds, CHART_POINTS)
    rounds = {round(i * total_rounds / num_samples) for i in range(num_samples + 1)}
    r = 0
    while r < total_rounds:
        r = r + 1 if r < CHART_DENSE_ROUNDS else r + max(1, r // CHART_GEO_DIVISOR)
        rounds.add(min(r, total_rounds))
    return sorted(rounds)


def build_chart(counts_series: dict[int, list[int]], total_rounds: int) -> dict:
    """Downsample per-round card counts to CHART_POINTS uniform samples per
    player plus a dense opening (see chart_sample_rounds).

    counts_series[pid][r] is the player's count after round r (index 0 = deal);
    the list simply ends once the player is eliminated.
    """
    sample_rounds = chart_sample_rounds(total_rounds)
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
    if not 1 <= seats <= PY_MAX_PLAYERS:
        raise ValueError(f"seats must be between 1 and {PY_MAX_PLAYERS}")
    if not 1 <= decks <= PY_MAX_DECKS:
        raise ValueError(f"decks must be between 1 and {PY_MAX_DECKS}")
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


def requested_max_rounds(config: dict) -> int:
    """The cap a request asks for: 0 = none. Absent means the old default,
    so a share link written before caps were optional replays the same game."""
    raw = config.get("max_rounds")
    if raw in (None, ""):
        return DEFAULT_MAX_ROUNDS
    value = int(raw)
    if value < 0:
        raise ValueError("max_rounds must be 0 (no cap) or positive")
    return value


def python_max_rounds(config: dict) -> int:
    """The cap a Python-run War game actually uses: never unlimited."""
    value = requested_max_rounds(config)
    return MAX_ROUNDS_CEILING if value == 0 else min(value, MAX_ROUNDS_CEILING)


_grid_cache: dict | None = None


def typical_rounds(players: int, decks: int) -> float | None:
    """Median round count for a War config from web/rounds-grid.json, the
    same table the page's calculator reads. Nearest cell in log space is
    plenty for a work budget. None when the grid is missing."""
    global _grid_cache
    if _grid_cache is None:
        try:
            _grid_cache = json.loads(ROUNDS_GRID.read_text())
        except (OSError, ValueError):
            _grid_cache = {}
    cells = _grid_cache.get("cells")
    if not cells:
        return None
    best, best_d = None, math.inf
    for key, (median, *_rest) in cells.items():
        p, d = (int(x) for x in key.split(":"))
        dist = (math.log(p) - math.log(players)) ** 2 + 4 * (math.log(d) - math.log(decks)) ** 2
        if dist < best_d:
            best, best_d = median, dist
    return best


def run_simulation(config: dict) -> dict:
    if config.get("game") == "blackjack":
        return run_blackjack_simulation(config)
    players = int(config.get("players", 4))
    decks = int(config.get("decks", 1))
    seed = config.get("seed")
    seed = int(seed) if seed not in (None, "") else random.randrange(1_000_000_000)
    max_rounds = python_max_rounds(config)
    if not 2 <= players <= PY_MAX_PLAYERS:
        raise ValueError(f"the server engine takes 2 to {PY_MAX_PLAYERS} players "
                         f"(the in-browser engine goes to {MAX_PLAYERS})")
    if not 1 <= decks <= PY_MAX_DECKS:
        raise ValueError(f"the server engine takes 1 to {PY_MAX_DECKS} decks "
                         f"(the in-browser engine goes to {MAX_DECKS})")

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


def run_batch_api(config: dict, progress=None) -> dict:
    if config.get("game") == "blackjack":
        seats = int(config.get("players", 4))
        decks = int(config.get("decks", 6))
        rounds = int(config.get("rounds", 100))
        games = int(config.get("games", 100))
        strategies = config.get("strategies") or ["basic"]
        seed = config.get("seed")
        base_seed = int(seed) if seed not in (None, "") else random.randrange(1_000_000)
        if not 1 <= seats <= PY_MAX_PLAYERS:
            raise ValueError(f"seats must be between 1 and {PY_MAX_PLAYERS}")
        if not 1 <= decks <= PY_MAX_DECKS:
            raise ValueError(f"decks must be between 1 and {PY_MAX_DECKS}")
        if not 1 <= rounds <= MAX_BJ_ROUNDS:
            raise ValueError(f"rounds must be between 1 and {MAX_BJ_ROUNDS}")
        if not 1 <= games <= MAX_BATCH_GAMES:
            raise ValueError(f"games must be between 1 and {MAX_BATCH_GAMES}")
        start_time = time.perf_counter()
        rows = run_blackjack_batch(seats, decks, rounds, games, strategies,
                                   base_seed=base_seed, progress=progress)
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
    seed = config.get("seed")
    base_seed = int(seed) if seed not in (None, "") else random.randrange(1_000_000)
    if not 2 <= players <= MAX_PLAYERS:
        raise ValueError(f"players must be between 2 and {MAX_PLAYERS}")
    if not 1 <= decks <= MAX_DECKS:
        raise ValueError(f"decks must be between 1 and {MAX_DECKS}")
    if decks * 52 < players:
        raise ValueError("not enough cards for that many players")
    if not 1 <= games <= MAX_BATCH_GAMES:
        raise ValueError(f"games must be between 1 and {MAX_BATCH_GAMES}")
    wanted = requested_max_rounds(config)

    typical = typical_rounds(players, decks)
    if typical is not None:
        per_game = min(typical, wanted) if wanted else typical
        if games * per_game > BATCH_ROUND_BUDGET:
            raise ValueError(
                f"that batch is about {games * per_game / 1e9:.1f} billion rounds "
                f"({games:,} games x ~{per_game:,.0f} rounds each); the budget is "
                f"{BATCH_ROUND_BUDGET / 1e9:.0f} billion. Fewer games or fewer decks.")

    native = native_batch(players, decks, games, base_seed, wanted, progress)
    if native is not None:
        return native

    # Python fallback: the binary is missing or would not start.
    if not 2 <= players <= PY_MAX_PLAYERS or not 1 <= decks <= PY_MAX_DECKS:
        raise ValueError(f"the native batch runner is unavailable and the Python engine "
                         f"takes at most {PY_MAX_PLAYERS} players and {PY_MAX_DECKS} decks")
    max_rounds = MAX_ROUNDS_CEILING if wanted == 0 else min(wanted, MAX_ROUNDS_CEILING)
    start_time = time.perf_counter()
    rows = run_batch(players, decks, games, base_seed=base_seed,
                     max_rounds=max_rounds, progress=progress)
    elapsed = time.perf_counter() - start_time
    return {
        "game": "war",
        "engine": "v1",
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


_native_warned = False


def native_batch(players, decks, games, base_seed, max_rounds, progress) -> dict | None:
    """Run the batch on bin/lud-batch (the Rust core, all cores, v2 seeds).

    None only when the binary cannot be started -- then the caller falls back
    to Python. A crash or a bad exit mid-run is an error to the client, never
    a silent rerun. Progress lines are forwarded to `progress`; if it returns
    False (the client is gone) the child is killed.
    """
    global _native_warned
    if not NATIVE_BATCH.is_file() or not os.access(NATIVE_BATCH, os.X_OK):
        if not _native_warned:
            _native_warned = True
            print(f"[ludicrous] {NATIVE_BATCH} not found; War batches run in Python", file=sys.stderr)
        return None
    argv = [str(NATIVE_BATCH), "--players", str(players), "--decks", str(decks),
            "--games", str(games), "--seed", str(base_seed), "--max-rounds", str(max_rounds)]
    try:
        child = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError as error:
        if not _native_warned:
            _native_warned = True
            print(f"[ludicrous] could not start {NATIVE_BATCH}: {error}; War batches run in Python",
                  file=sys.stderr)
        return None

    result = None
    error = None
    try:
        for line in child.stdout:
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
            if "progress" in msg:
                if progress is not None and progress(msg["progress"]["done"], msg["progress"]["total"]) is False:
                    child.kill()
                    break
            elif "result" in msg:
                result = msg["result"]
            elif "error" in msg:
                error = msg["error"]
    finally:
        try:
            _out, err = child.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            _out, err = child.communicate()
    if error is not None:
        raise ValueError(error)
    if result is None:
        raise RuntimeError(f"native batch runner exited with {child.returncode}: {err.strip()[:300]}")
    return result


class Handler(SimpleHTTPRequestHandler):
    # Python's mimetypes table doesn't reliably know about .wasm, and a
    # browser refuses to stream-compile a module served as anything else.
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".js": "text/javascript",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean.startswith("/cards/"):
            # Serve card art from the existing cards/ folder (basename only,
            # so no path traversal).
            return str(CARDS_DIR / Path(clean).name)
        return super().translate_path(path)

    def stream_batch(self):
        """POST /api/batch/stream — the batch with live progress.

        The response is newline-delimited JSON over an HTTP/1.0-style
        stream (no Content-Length; the closed connection ends the body):
        throttled {"progress": {"done", "total"}} lines while the pool
        works, then exactly one {"result": ...} line — or {"error": ...},
        since validation happens after the 200 header is already out.
        Not gzipped: progress lines are tiny and the result is one line.
        """
        try:
            length = int(self.headers.get("Content-Length", 0))
            config = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, TypeError):
            self.send_error(400)
            return

        write_lock = threading.Lock()
        throttle = {"at": 0.0, "gone": False}

        def send_line(payload: dict) -> None:
            data = json.dumps(payload).encode() + b"\n"
            with write_lock:
                self.wfile.write(data)
                self.wfile.flush()

        def progress(done: int, total: int) -> None:
            # Called from executor callback threads. Throttled so a fast
            # batch doesn't spend its time writing to the socket, and
            # never raises — a gone client must not poison the pool
            # (the computation is shared and finishes regardless).
            if throttle["gone"]:
                return False
            now = time.perf_counter()
            if done < total and now - throttle["at"] < 0.1:
                return True
            throttle["at"] = now
            try:
                send_line({"progress": {"done": done, "total": total}})
            except OSError:
                throttle["gone"] = True  # the native runner stops; the pool finishes on its own
                return False
            return True

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            result = run_batch_api(config, progress=progress)
            send_line({"result": result})
        except (ValueError, TypeError, KeyError, RuntimeError) as error:
            try:
                send_line({"error": str(error)})
            except OSError:
                pass
        except OSError:
            pass  # client disconnected mid-stream

    def do_POST(self):
        if self.path == "/api/batch/stream":
            self.stream_batch()
            return
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
        # Simulation payloads are megabytes of repetitive JSON; gzip them for
        # any client that asked, and fall back to plain bytes for one that
        # didn't. mtime=0 keeps the compressed bytes reproducible.
        encoding = None
        if accepts_gzip(self.headers.get("Accept-Encoding")):
            body = gzip.compress(body, GZIP_LEVEL, mtime=0)
            encoding = "gzip"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if encoding:
            self.send_header("Content-Encoding", encoding)
        self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Ludicrous web server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Ludicrous running at http://localhost:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
