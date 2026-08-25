"""Golden-file regression tests for the v1 recording contract.

Each fixture in `tests/golden/` is the exact JSON `simulate.py --json` writes
for a fixed configuration and seed, gzipped so the repo stays small. The tests
rebuild every recording in-process and compare the bytes, so any change to the
event vocabulary, the field order, the JSON encoding, or the RNG call sequence
shows up here instead of in a frontend that can no longer replay old games.

The contract these fixtures freeze is documented in `docs/EVENT_SCHEMA.md`.

To regenerate after an intentional contract change:

    LUDICROUS_REGEN_GOLDEN=1 python3 -m unittest tests.test_golden

The regeneration run rewrites the fixtures and then fails, so a regenerated
fixture is always a deliberate act with a diff to review — never a silent
side effect of a normal test run.
"""
import functools
import gzip
import json
import os
import unittest
from pathlib import Path

from engine import (
    BlackjackGame,
    WarGame,
    run_batch,
    run_blackjack_batch,
    summarize_batch,
    summarize_blackjack_batch,
)

GOLDEN_DIR = Path(__file__).parent / "golden"
REGEN_ENV = "LUDICROUS_REGEN_GOLDEN"
GZIP_LEVEL = 9  # fixtures are written once and read forever; spend the CPU
DEFAULT_MAX_ROUNDS = 1_000_000  # simulate.py's --max-rounds default


# ------------------------------------------------------------- recordings

def war_recording(players: int, decks: int, seed: int,
                  max_rounds: int = DEFAULT_MAX_ROUNDS) -> dict:
    """The `{summary, events}` payload `simulate.py --json` writes for War."""
    game = WarGame(players, decks, seed=seed)
    game.run(max_rounds=max_rounds)
    return {
        "summary": game.summary(),
        "events": [event.to_dict() for event in game.events],
    }


def blackjack_recording(seats: int, decks: int, rounds: int,
                        strategies: list[str], seed: int) -> dict:
    """The `{summary, events}` payload `simulate.py --json` writes for Blackjack."""
    game = BlackjackGame(seats, decks, rounds, strategies=strategies, seed=seed)
    game.run()
    return {
        "summary": game.summary(),
        "events": [event.to_dict() for event in game.events],
    }


def war_batch_summary(players: int, decks: int, games: int, base_seed: int,
                      max_rounds: int = DEFAULT_MAX_ROUNDS) -> dict:
    rows = run_batch(players, decks, games, base_seed=base_seed,
                     max_rounds=max_rounds)
    return {
        "config": {
            "game": "war",
            "players": players,
            "decks": decks,
            "games": games,
            "base_seed": base_seed,
            "max_rounds": max_rounds,
        },
        "aggregate": summarize_batch(rows),
        "games": rows,
    }


def blackjack_batch_summary(seats: int, decks: int, rounds: int, games: int,
                            strategies: list[str], base_seed: int) -> dict:
    rows = run_blackjack_batch(seats, decks, rounds, games, strategies,
                               base_seed=base_seed)
    return {
        "config": {
            "game": "blackjack",
            "players": seats,
            "decks": decks,
            "rounds": rounds,
            "games": games,
            "strategies": strategies,
            "base_seed": base_seed,
        },
        "aggregate": summarize_blackjack_batch(rows),
        "games": rows,
    }


# ---------------------------------------------------------------- fixtures

# name -> zero-argument builder. The name is both the fixture filename
# (name + ".json.gz") and the generated test method's suffix.
CASES = {
    # War: the shapes the web UI actually offers — heads-up, a small table,
    # a multi-deck table, and a crowded one.
    "war_2p_1d_seed0": functools.partial(war_recording, 2, 1, 0),
    "war_2p_1d_seed1": functools.partial(war_recording, 2, 1, 1),
    "war_2p_1d_seed2": functools.partial(war_recording, 2, 1, 2),
    "war_4p_1d_seed0": functools.partial(war_recording, 4, 1, 0),
    "war_4p_1d_seed1": functools.partial(war_recording, 4, 1, 1),
    "war_4p_1d_seed2": functools.partial(war_recording, 4, 1, 2),
    "war_6p_3d_seed0": functools.partial(war_recording, 6, 3, 0),
    "war_6p_3d_seed1": functools.partial(war_recording, 6, 3, 1),
    "war_6p_3d_seed2": functools.partial(war_recording, 6, 3, 2),
    "war_10p_2d_seed0": functools.partial(war_recording, 10, 2, 0),
    "war_10p_2d_seed1": functools.partial(war_recording, 10, 2, 1),
    "war_10p_2d_seed2": functools.partial(war_recording, 10, 2, 2),
    # Rare-path coverage, found by scanning seeds: seed 76 contains a Draw
    # tiebreaker (a RoundDrawn event, the only round with no winner), seed
    # 204 contains a depth-4 war (a war inside a war inside a war).
    "war_4p_1d_seed76_drawn_round": functools.partial(war_recording, 4, 1, 76),
    "war_2p_1d_seed204_deep_war": functools.partial(war_recording, 2, 1, 204),
    # Blackjack: a plain basic-strategy table, and a mixed table whose
    # recordings contain splits, doubles and mid-session reshuffles.
    "bj_4s_6d_50r_basic_seed0": functools.partial(
        blackjack_recording, 4, 6, 50, ["basic"], 0),
    "bj_4s_6d_50r_basic_seed1": functools.partial(
        blackjack_recording, 4, 6, 50, ["basic"], 1),
    "bj_5s_6d_100r_mixed_seed0": functools.partial(
        blackjack_recording, 5, 6, 100, ["basic", "never-bust", "hit-below-16"], 0),
    "bj_5s_6d_100r_mixed_seed1": functools.partial(
        blackjack_recording, 5, 6, 100, ["basic", "never-bust", "hit-below-16"], 1),
    # Batch aggregates: the statistics path, which has no event log at all.
    "batch_war_4p_1d_25g_seed1000": functools.partial(
        war_batch_summary, 4, 1, 25, 1000),
    "batch_bj_3s_6d_40r_20g_seed500": functools.partial(
        blackjack_batch_summary, 3, 6, 40, 20, ["basic", "never-bust"], 500),
}


def fixture_path(name: str) -> Path:
    return GOLDEN_DIR / f"{name}.json.gz"


def encode(payload: dict) -> bytes:
    """Exactly what `json.dump(payload, file)` writes, as bytes."""
    return json.dumps(payload).encode()


def regenerating() -> bool:
    return os.environ.get(REGEN_ENV, "") not in ("", "0")


# ------------------------------------------------------------- diffing

def describe_mismatch(name: str, expected: bytes, actual: bytes) -> str:
    """A message that points at the first real difference, not 300 KB of JSON."""
    lines = [
        f"golden fixture {name}.json.gz does not match the engine's output.",
        f"stored {len(expected):,} bytes, produced {len(actual):,} bytes.",
    ]
    try:
        want = json.loads(expected)
        got = json.loads(actual)
    except ValueError:
        want = got = None
    if isinstance(want, dict) and isinstance(got, dict):
        if want.get("summary") != got.get("summary"):
            lines.append(f"  summary stored:   {want.get('summary')}")
            lines.append(f"  summary produced: {got.get('summary')}")
        want_events = want.get("events") or want.get("games") or []
        got_events = got.get("events") or got.get("games") or []
        if len(want_events) != len(got_events):
            lines.append(f"  record count stored {len(want_events):,}, "
                         f"produced {len(got_events):,}")
        for i, (a, b) in enumerate(zip(want_events, got_events)):
            if a != b:
                lines.append(f"  first differing record at index {i}:")
                lines.append(f"    stored:   {a}")
                lines.append(f"    produced: {b}")
                break
        if "aggregate" in want and want["aggregate"] != got.get("aggregate"):
            lines.append(f"  aggregate stored:   {want['aggregate']}")
            lines.append(f"  aggregate produced: {got.get('aggregate')}")
    else:
        offset = next((i for i, (a, b) in enumerate(zip(expected, actual)) if a != b),
                      min(len(expected), len(actual)))
        lines.append(f"  first differing byte at offset {offset}:")
        lines.append(f"    stored:   {expected[max(0, offset - 40):offset + 40]!r}")
        lines.append(f"    produced: {actual[max(0, offset - 40):offset + 40]!r}")
    lines.append(f"If the change is intentional, regenerate with "
                 f"{REGEN_ENV}=1 python3 -m unittest tests.test_golden "
                 f"and review the diff.")
    return "\n".join(lines)


# ---------------------------------------------------------------- tests

class TestGoldenRecordings(unittest.TestCase):
    """One test per fixture, generated below from CASES."""

    maxDiff = None

    def _check(self, name: str) -> None:
        payload = CASES[name]()
        actual = encode(payload)
        path = fixture_path(name)

        if regenerating():
            GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
            path.write_bytes(gzip.compress(actual, GZIP_LEVEL, mtime=0))
            self.fail(f"{REGEN_ENV} is set: rewrote {path.name} "
                      f"({len(actual):,} bytes of JSON). Review the diff, then "
                      f"unset {REGEN_ENV} and rerun to confirm it passes.")

        self.assertTrue(
            path.exists(),
            f"missing golden fixture {path}. Create it with "
            f"{REGEN_ENV}=1 python3 -m unittest tests.test_golden",
        )
        expected = gzip.decompress(path.read_bytes())
        if expected != actual:
            self.fail(describe_mismatch(name, expected, actual))


def _make_test(name: str):
    def test(self):
        self._check(name)
    test.__name__ = f"test_{name}"
    test.__doc__ = f"{name} still replays byte-for-byte"
    return test


for _name in CASES:
    setattr(TestGoldenRecordings, f"test_{_name}", _make_test(_name))
del _name


class TestGoldenDirectory(unittest.TestCase):
    def test_every_stored_fixture_has_a_case(self):
        """A fixture nobody regenerates is a fixture nobody can trust."""
        stored = {p.name[: -len(".json.gz")] for p in GOLDEN_DIR.glob("*.json.gz")}
        self.assertEqual(
            stored - set(CASES),
            set(),
            "golden files with no entry in CASES — delete them or add a case",
        )

    def test_fixtures_decompress_to_the_documented_envelope(self):
        for name in CASES:
            with self.subTest(fixture=name):
                path = fixture_path(name)
                if not path.exists():
                    self.skipTest(f"{path.name} not generated yet")
                payload = json.loads(gzip.decompress(path.read_bytes()))
                self.assertIsInstance(payload, dict)
                if name.startswith("batch_"):
                    self.assertEqual({"config", "aggregate", "games"},
                                     set(payload))
                else:
                    self.assertEqual({"summary", "events"}, set(payload))
                    self.assertTrue(payload["events"])
                    self.assertTrue(
                        all("type" in event for event in payload["events"]),
                        "every event carries its class name in \"type\"",
                    )


if __name__ == "__main__":
    unittest.main()
