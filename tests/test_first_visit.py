"""First-visit rules in web/app.js, run under node (tests/first_visit_harness.mjs).

- A visit with no URL parameters plays a 1,000-player showcase game whose deck
  count is the most decks (among the rounds grid's deck counts) estimated to
  simulate in under 2 s. On the committed grid that is 256. A regrid or a new
  wasm speed factor that moves the pick fails here, so the choice is made on
  purpose.
- A War game never starts with a player holding no cards: the page refuses it
  before sending anything to an engine.
- A Blackjack batch over the hand budget is refused before it is sent, with the
  server's own message, and the Blackjack preset fits the budget.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

import server

HARNESS = Path(__file__).with_name("first_visit_harness.mjs")


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class FirstVisitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                              check=True, timeout=60)
        cls.out = json.loads(proc.stdout)

    def test_showcase_picks_256_decks_on_the_committed_grid(self):
        self.assertEqual(self.out["showcasePlayers"], 1000)
        self.assertEqual(self.out["showcaseDecks"], 256)
        # The rule, spelled out: 256 is under 2 s and the next deck count is not.
        est = self.out["estimates"]
        self.assertLess(est["256"]["seconds"], 2)
        self.assertGreaterEqual(est["512"]["seconds"], 2)

    def test_showcase_falls_back_to_256_without_the_grid(self):
        self.assertEqual(self.out["showcaseNoGrid"], 256)

    def test_deck_counts_that_cannot_deal_everyone_are_skipped(self):
        for decks in ("1", "2", "4", "8", "16"):
            with self.subTest(decks=decks):
                self.assertIsNone(self.out["estimates"][decks])

    def test_showcase_seed_is_fixed(self):
        self.assertIsInstance(self.out["showcaseSeed"], int)

    def test_cards_per_player_hint(self):
        hints = self.out["hints"]
        self.assertEqual(hints["6:3"], "26 cards each")
        self.assertEqual(hints["4:1"], "13 cards each")
        self.assertEqual(hints["52:1"], "1 card each")
        self.assertEqual(hints["1000:20"], "≈ 1 card each")
        self.assertEqual(hints["1000:256"], "≈ 13 cards each")
        self.assertEqual(hints["1000:19"], self.out["notEnough"])
        self.assertEqual(hints["53:1"], self.out["notEnough"])

    def test_seat_bias_caption(self):
        captions = self.out["captions"]
        self.assertEqual(captions["1000:20"],
                         "Seats 1–40 get one more card than the rest (1,040 cards, 1,000 players).")
        self.assertEqual(captions["51:1"],
                         "Seat 1 gets one more card than the rest (52 cards, 51 players).")
        self.assertIsNone(captions["4:1"])
        self.assertIsNone(captions["6:3"])

    def test_war_run_with_fewer_cards_than_players_is_refused_before_sending(self):
        runs = self.out["runs"]
        for name in ("warSingleShort", "warBatchShort"):
            with self.subTest(run=name):
                self.assertEqual(runs[name]["error"], self.out["notEnough"])
                self.assertEqual(runs[name]["sent"], [])
                self.assertEqual(runs[name]["workers"], 0)
        # One card each is a legal game, and it does reach the engine.
        self.assertEqual(runs["warSingleExact"]["error"], "")
        self.assertEqual(runs["warSingleExact"]["workers"], 1)

    def test_budget_matches_the_server(self):
        self.assertEqual(self.out["budget"], server.BJ_HAND_BUDGET)
        for case in self.out["budgetMessages"]:
            with self.subTest(**{k: case[k] for k in ("seats", "rounds", "games")}):
                try:
                    server.check_blackjack_budget(case["seats"], case["rounds"], case["games"])
                    expected = None
                except ValueError as error:
                    expected = str(error)
                self.assertEqual(case["msg"], expected)

    def test_over_budget_blackjack_batch_is_refused_before_sending(self):
        runs = self.out["runs"]
        over = runs["bjBatchOver"]
        self.assertEqual(over["sent"], [])
        with self.assertRaises(ValueError) as caught:
            server.check_blackjack_budget(200, 100, 1000)
        self.assertEqual(over["error"], str(caught.exception))
        self.assertEqual(runs["bjBatchFits"]["error"], "")
        self.assertEqual(len(runs["bjBatchFits"]["sent"]), 1)

    def test_blackjack_preset_fits_the_budget(self):
        preset = self.out["showdown"]
        self.assertIsNone(preset["msg"])
        self.assertEqual(len(preset["strategies"]), 5)
        server.check_blackjack_budget(preset["players"], preset["rounds"], preset["games"])


if __name__ == "__main__":
    unittest.main()
