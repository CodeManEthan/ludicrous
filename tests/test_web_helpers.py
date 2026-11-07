"""Pure helpers in web/app.js, run under node (tests/web_helpers_harness.mjs).

- A run's URL reproduces the run: runQuery and configFromQuery round-trip
  every kind of run (War and Blackjack, single and batch, with and without a
  round cap). A link with neither `game` nor `mode`, the shape every link had
  before, keeps its old defaults (the server engine, the 1M cap); no other
  link gets them. A War game run on the server writes no `game` and no
  `engine`, so its link replays on the server.
- The round banner counts a crowd of eliminations instead of naming each.
- A short game's speed labels say how long it really plays.
- The rounds estimate is built from measured cells only, and every players
  row is defined at every deck count.
"""
import json
import math
import shutil
import subprocess
import unittest
from pathlib import Path

HARNESS = Path(__file__).with_name("web_helpers_harness.mjs")


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class WebHelpersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                              check=True, timeout=60)
        cls.out = json.loads(proc.stdout)

    # ------------------------------------------------------------ run URLs

    def test_every_run_round_trips_through_its_url(self):
        for name, case in self.out["roundTrips"].items():
            with self.subTest(run=name, query=case["query"]):
                back = dict(case["back"])
                self.assertIs(back.pop("run"), True)
                self.assertEqual(back, case["config"])

    def test_war_runs_always_write_the_cap(self):
        for name, case in self.out["roundTrips"].items():
            if case["config"]["game"] == "war":
                with self.subTest(run=name):
                    self.assertIn("max_rounds=", case["query"])

    def test_war_on_the_server_writes_no_game_and_no_engine(self):
        query = self.out["serverWar"]
        self.assertNotIn("game=", query)
        self.assertNotIn("engine=", query)
        self.assertIn("seed=777", query)
        self.assertEqual(self.out["serverWarBack"]["engine"], "v1")
        self.assertEqual(self.out["serverWarBack"]["maxRounds"], 0)

    def test_blackjack_and_batch_runs_write_their_seed_and_kind(self):
        self.assertTrue(self.out["serverBlackjack"].startswith("game=blackjack&"))
        self.assertIn("seed=778", self.out["serverBlackjack"])
        self.assertIn("mode=batch&engine=v2&", self.out["batchNative"])
        self.assertIn("seed=4242", self.out["batchNative"])
        self.assertNotIn("engine=", self.out["batchPython"])
        self.assertIn("seed=4243", self.out["batchPython"])
        self.assertTrue(self.out["batchBlackjack"].startswith("game=blackjack&mode=batch&"))
        self.assertIn("seed=4244", self.out["batchBlackjack"])

    def test_legacy_war_link_keeps_its_old_defaults(self):
        legacy = self.out["legacy"]
        self.assertEqual(legacy["noEngineNoCap"]["engine"], "v1")
        self.assertEqual(legacy["noEngineNoCap"]["maxRounds"], 1_000_000)
        self.assertEqual(legacy["deepLink"]["round"], 42)
        # engine=v2 links were always written with their cap; none is invented.
        self.assertEqual(legacy["v2NoCap"]["engine"], "v2")
        self.assertNotIn("maxRounds", legacy["v2NoCap"])
        self.assertEqual(legacy["withCap"]["maxRounds"], 0)
        # Without run=1 a link only fills the form.
        self.assertNotIn("engine", legacy["prefillOnly"])
        self.assertNotIn("maxRounds", legacy["prefillOnly"])

    def test_blackjack_and_batch_links_never_get_the_legacy_defaults(self):
        for name, config in self.out["modern"].items():
            with self.subTest(link=name):
                self.assertNotIn("engine", config)
                self.assertNotIn("maxRounds", config)

    # ------------------------------------------------------------- banner

    def test_banner_summarizes_more_than_three_eliminations(self):
        n = self.out["narration"]
        self.assertEqual(n["one"], "Ada eliminated (#7)")
        self.assertEqual(n["three"], "Ada eliminated (#5) · Bo eliminated (#6) · Cy eliminated (#4)")
        self.assertEqual(n["fourContiguous"], "4 players eliminated (#9–#12)")
        self.assertEqual(n["big"], "210 players eliminated (#791–#1000)")
        self.assertEqual(n["gapped"], "5 players eliminated (#2, #4, #9 and 2 more)")

    # ------------------------------------------------------- speed labels

    def test_short_game_speed_labels_say_the_real_time(self):
        labels = self.out["speedLabels"]
        self.assertEqual(labels["d60"], "game in ~33 s · 3 rnd/s")
        self.assertEqual(labels["d240"], labels["d60"])
        self.assertEqual(labels["d30"], "game in ~30 s · 3 rnd/s")
        self.assertEqual(labels["1"], "1 rnd/s · game in ~2 min")
        self.assertEqual(labels["10"], "10 rnd/s · game in ~10 s")

    # ---------------------------------------------------- rounds estimate

    def test_every_lattice_cell_estimate_is_the_measured_cell(self):
        cells = self.out["grid"]["cells"]
        for key, est in self.out["latticeEstimates"].items():
            median, p10, p90, _rps = cells[key]
            with self.subTest(cell=key):
                self.assertAlmostEqual(est["median"] / median, 1, places=9)
                self.assertAlmostEqual(est["p10"] / p10, 1, places=9)
                self.assertAlmostEqual(est["p90"] / p90, 1, places=9)

    def test_edges_are_where_rows_first_deal_everyone(self):
        grid = self.out["grid"]
        for p in grid["players"]:
            edge = math.ceil(p / 52)
            with self.subTest(players=p):
                if edge in grid["decks"]:
                    self.assertIn(f"{p}:{edge}", grid["cells"])
                    self.assertNotIn(str(p), grid["edges"])
                else:
                    self.assertEqual(grid["edges"][str(p)][0], edge)

    def test_1000_players_on_20_decks(self):
        est = self.out["queries"]["1000:20"]["estimate"]
        # A measured 200-game run: median 1,334, p10 101, p90 75,389.
        self.assertGreaterEqual(est["median"], 1000)
        self.assertLess(est["median"], 5000)
        self.assertLessEqual(est["p10"], 200)
        self.assertGreaterEqual(est["p90"], 75_000)

    def test_queries_whose_upper_row_cannot_be_dealt(self):
        for key in ("700:14", "200:4", "100:2", "300:6"):
            q = self.out["queries"][key]
            with self.subTest(query=key):
                est = q["estimate"]
                for i, field in enumerate(("median", "p10", "p90")):
                    value = est[field]
                    self.assertTrue(math.isfinite(value))
                    lo, hi = sorted((q["rows"]["lo"][i], q["rows"]["hi"][i]))
                    self.assertGreaterEqual(value, lo * (1 - 1e-9))
                    self.assertLessEqual(value, hi * (1 + 1e-9))

    def test_too_few_cards_has_no_estimate(self):
        self.assertIsNone(self.out["queries"]["1000:19"]["estimate"])


if __name__ == "__main__":
    unittest.main()
