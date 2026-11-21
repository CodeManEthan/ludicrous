"""The welcome popup in web/app.js, run under node (tests/intro_harness.mjs).

- A bare visit (no URL key the page reads; tracking keys like utm_source
  don't count) runs nothing. Until the visitor has closed the welcome popup
  once, it opens. Closing it by any route stores one flag,
  localStorage["ludicrous-intro"] = "seen", and with the flag set a bare
  visit opens nothing.
- A URL with a key the page reads behaves as before: a run URL runs with no
  popup, a form-only URL fills the form, and neither touches the flag.
- Storage that throws, or no localStorage at all, counts as no flag: the
  popup opens and start-up doesn't fail.
- "Simulate a game" plays the 1,000-player showcase game, seed 10. Without
  WebAssembly it is disabled and a line says why.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).parent
HARNESS = HERE / "intro_harness.mjs"
HELPERS = HERE / "web_helpers_harness.mjs"


def run_node(path):
    proc = subprocess.run(["node", str(path)], capture_output=True, text=True,
                          check=True, timeout=60)
    return json.loads(proc.stdout)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class IntroTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = run_node(HARNESS)

    def assertBooted(self, case):
        self.assertIsNone(case["bootError"])

    # ------------------------------------------------------- the bare visit

    def test_bare_visit_opens_the_popup_and_runs_nothing(self):
        for name in ("bare", "tracking"):
            with self.subTest(case=name):
                case = self.out[name]
                self.assertBooted(case)
                self.assertTrue(case["introOpen"])
                self.assertEqual(case["workers"], 0)
                self.assertEqual(case["fetches"], ["/rounds-grid.json"])
                self.assertIsNone(case["flag"])

    def test_bare_visit_with_the_flag_opens_nothing_and_runs_nothing(self):
        for name in ("flagSet", "flagSetTracking"):
            with self.subTest(case=name):
                case = self.out[name]
                self.assertBooted(case)
                self.assertFalse(case["introOpened"])
                self.assertEqual(case["workers"], 0)
                self.assertEqual(case["fetches"], ["/rounds-grid.json"])

    # ------------------------------------------------------ URLs with keys

    def test_run_url_runs_with_no_popup_and_leaves_the_flag_alone(self):
        case = self.out["runUrl"]
        self.assertBooted(case)
        self.assertFalse(case["introOpened"])
        self.assertEqual(case["workers"], 1)
        [message] = case["messages"]
        self.assertEqual((message["type"], message["players"], message["decks"], message["seed"]),
                         ("prepare", 6, 3, 1))
        self.assertEqual(case["flagCalls"], [])

    def test_form_only_url_fills_the_form_with_no_popup(self):
        case = self.out["prefill"]
        self.assertBooted(case)
        self.assertFalse(case["introOpened"])
        self.assertEqual(case["workers"], 0)
        self.assertEqual(case["fetches"], ["/rounds-grid.json"])
        self.assertEqual(case["flagCalls"], [])

    def test_query_keys_hold_every_key_a_run_url_writes(self):
        keys = set(self.out["queryKeys"])
        trips = run_node(HELPERS)["roundTrips"]
        self.assertTrue(trips)
        for name, trip in trips.items():
            with self.subTest(run=name, query=trip["query"]):
                written = {pair.split("=", 1)[0] for pair in trip["query"].split("&")}
                self.assertLessEqual(written, keys)
        self.assertIn("round", keys)  # a deep link's key, added by hand, not by runQuery

    # ----------------------------------------------------- blocked storage

    def test_storage_that_cannot_be_used_counts_as_no_flag(self):
        for name in ("storage_throw", "storage_absent"):
            with self.subTest(case=name):
                case = self.out[name]
                self.assertBooted(case)
                self.assertTrue(case["introOpen"])
                self.assertEqual(case["workers"], 0)

    # -------------------------------------------------------- closing it

    def test_every_way_out_of_the_popup_sets_the_flag(self):
        for name, case in self.out["routes"].items():
            with self.subTest(route=name):
                self.assertBooted(case)
                self.assertFalse(case["introOpen"])
                self.assertEqual(case["flag"], "seen")

    def test_a_click_inside_the_popup_leaves_it_open(self):
        case = self.out["innerClick"]
        self.assertTrue(case["introOpen"])
        self.assertIsNone(case["flag"])

    def test_only_simulate_a_game_runs_anything(self):
        for name, case in self.out["routes"].items():
            if name != "simulate":
                with self.subTest(route=name):
                    self.assertEqual(case["workers"], 0)

    def test_simulate_a_game_closes_the_popup_then_plays_the_showcase_game(self):
        case = self.out["routes"]["simulate"]
        self.assertEqual(case["workers"], 1)
        [message] = case["messages"]
        self.assertEqual(message["type"], "prepare")
        self.assertEqual(message["players"], 1000)
        self.assertEqual(message["decks"], 256)
        self.assertEqual(message["seed"], 10)
        calls = case["calls"]
        self.assertLess(calls.index(["close", "#intro"]), calls.index(["worker"]))

    def test_without_webassembly_simulate_a_game_is_disabled_and_says_why(self):
        case = self.out["noEngine"]
        self.assertBooted(case)
        self.assertTrue(case["introOpen"])
        self.assertTrue(case["disabled"])
        self.assertEqual(case["title"], "Needs a browser with WebAssembly and Web Workers")
        self.assertFalse(case["noteHidden"])
        self.assertFalse(case["simulateAutofocus"])
        self.assertTrue(case["tourAutofocus"])
        self.assertEqual(self.out["noEngineAfter"]["workers"], 0)

    def test_with_webassembly_simulate_a_game_is_the_first_choice(self):
        case = self.out["withEngine"]
        self.assertFalse(case["disabled"])
        self.assertTrue(case["noteHidden"])
        self.assertTrue(case["simulateAutofocus"])
        self.assertFalse(case["tourAutofocus"])

    def test_page_keys_wait_while_the_popup_is_open(self):
        self.assertTrue(self.out["keysPopupOpen"]["boxOpen"])
        self.assertFalse(self.out["keysNoPopup"]["boxOpen"])


if __name__ == "__main__":
    unittest.main()
