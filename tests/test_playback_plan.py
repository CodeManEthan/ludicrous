"""The "game in ~N" playback plans must actually take about N seconds.

Regression for 2026-09-08: a 100-player, 1000-deck War game (270M rounds) was
still in its "crowded opening" at round 45,431, and the opening was pinned at
one round per frame with no time limit — over a minute in, playback was at
round 6,000. The plan builders live in web/app.js; this runs them under node
with stubbed browser globals (tests/playback_plan_harness.mjs).
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

HARNESS = Path(__file__).with_name("playback_plan_harness.mjs")
MIN_SCALED_SPEED = 3  # web/app.js: tiny games run at this floor and finish early
OPENING_SHARE = 0.20


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class PlaybackPlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True, check=True)
        cls.plans = json.loads(proc.stdout)

    def test_plans_cover_every_round_contiguously(self):
        for key, spans in self.plans.items():
            with self.subTest(plan=key):
                self.assertEqual(spans[0]["from"], 0)
                for a, b in zip(spans, spans[1:]):
                    self.assertEqual(a["to"], b["from"])
                    self.assertGreater(a["speed"], 0)

    def test_total_duration_fits_the_budget(self):
        for key, spans in self.plans.items():
            budget = int(key.split(":")[1][1:])
            total = sum(s["secs"] for s in spans)
            with self.subTest(plan=key, seconds=round(total, 1)):
                # Within 1% of the budget, or shorter when the whole game runs
                # at the speed floor (a 67-round game does not need a minute).
                rounds = spans[-1]["to"]
                if all(s["speed"] <= MIN_SCALED_SPEED for s in spans):
                    self.assertLessEqual(total, rounds / MIN_SCALED_SPEED + 1e-6)
                else:
                    self.assertLessEqual(total, budget * 1.01)

    def test_opening_never_takes_more_than_its_share(self):
        for key, spans in self.plans.items():
            budget = int(key.split(":")[1][1:])
            opening = sum(s["secs"] for s in spans if s["phase"] == "opening")
            with self.subTest(plan=key, opening_seconds=round(opening, 1)):
                self.assertLessEqual(opening, OPENING_SHARE * budget + 1e-6)

    def test_short_openings_still_play_slowly(self):
        # The cap must not speed up an opening that already fits: 44 rounds
        # at one per frame is under a second.
        spans = self.plans["huge_short_opening:d60:straight"]
        opening = [s for s in spans if s["phase"] == "opening"]
        self.assertEqual(len(opening), 1)
        self.assertEqual(opening[0]["speed"], 60)

    def test_the_reported_game_finishes_in_about_a_minute(self):
        spans = self.plans["big_crowded:d60:straight"]
        self.assertAlmostEqual(sum(s["secs"] for s in spans), 60, delta=0.6)


if __name__ == "__main__":
    unittest.main()
