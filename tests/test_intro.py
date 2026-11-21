"""The welcome popup in web/app.js, run under node (tests/intro_harness.mjs).

- A bare visit (no URL key the page reads; tracking keys like utm_source
  don't count) runs nothing and opens the welcome popup, unless one of two
  flags is set. Every close, by any route, sets
  sessionStorage["ludicrous-intro"] = "closed", which keeps the popup shut
  for that tab only. "Don't show again" also sets
  localStorage["ludicrous-intro"] = "never", before it closes the popup,
  and that lasts. The "seen" value older builds stored doesn't keep it shut.
- A URL with a key the page reads behaves as before: a run URL runs with no
  popup, a form-only URL fills the form, and neither reads nor writes
  either flag.
- Either store throwing, or missing, counts as no flag: the popup opens and
  start-up doesn't fail. With localStorage blocked, "Don't show again"
  still closes the popup; with sessionStorage blocked, closing it raises
  nothing.
- "Simulate a game" plays the 1,000-player showcase game, seed 10. Without
  WebAssembly it is disabled and a line says why.
- The guided tour ("Show me around", or the header's Tour link) walks the
  steps whose elements are on screen, stores nothing, pauses playback, and
  never overlaps a run: it won't open while a run is claimed, a preset
  claims the run before waiting on the rounds grid, and Back or Forward or a
  newly loaded game ends it.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
HARNESS = HERE / "intro_harness.mjs"
HELPERS = HERE / "web_helpers_harness.mjs"
SIMULATE = HERE.parent / "simulate.py"

TOUR_KEYS = ["mode", "game", "size", "options", "run", "presets", "playback", "chart", "help"]
WITHOUT_GAME = ["mode", "game", "size", "options", "run", "presets", "help"]


def run_node(path, env=None):
    proc = subprocess.run(["node", str(path)], capture_output=True, text=True,
                          check=True, timeout=60, env=env)
    return json.loads(proc.stdout)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class IntroTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A small saved game for the Import case.
        with tempfile.TemporaryDirectory() as tmp:
            recording = Path(tmp) / "game.json"
            subprocess.run([sys.executable, str(SIMULATE), "-p", "3", "-d", "1", "--seed", "3",
                            "--json", str(recording)], capture_output=True, check=True, timeout=60)
            cls.out = run_node(HARNESS, {**os.environ, "LUDICROUS_RECORDING": str(recording)})

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
                self.assertIsNone(case["session"])

    def test_bare_visit_with_either_flag_opens_nothing_and_runs_nothing(self):
        for name in ("closedForNow", "closedForNowTracking", "never", "neverTracking"):
            with self.subTest(case=name):
                case = self.out[name]
                self.assertBooted(case)
                self.assertFalse(case["introOpened"])
                self.assertEqual(case["workers"], 0)
                self.assertEqual(case["fetches"], ["/rounds-grid.json"])
                self.assertEqual(case["flagSets"], [])

    def test_bare_visit_with_the_old_seen_value_opens_the_popup(self):
        case = self.out["oldSeen"]
        self.assertBooted(case)
        self.assertTrue(case["introOpen"])
        self.assertEqual(case["flag"], "seen")

    # ------------------------------------------------------ URLs with keys

    def test_run_url_runs_with_no_popup_and_leaves_both_flags_alone(self):
        for name in ("runUrl", "runUrlFlags"):
            with self.subTest(case=name):
                case = self.out[name]
                self.assertBooted(case)
                self.assertFalse(case["introOpened"])
                self.assertEqual(case["workers"], 1)
                [message] = case["messages"]
                self.assertEqual(
                    (message["type"], message["players"], message["decks"], message["seed"]),
                    ("prepare", 6, 3, 1))
                self.assertEqual(case["flagCalls"], [])

    def test_form_only_url_fills_the_form_with_no_popup(self):
        for name in ("prefill", "prefillFlags"):
            with self.subTest(case=name):
                case = self.out[name]
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

    def test_query_keys_are_exactly_the_keys_config_from_query_reads(self):
        src = (Path(__file__).parent.parent / "web" / "app.js").read_text()
        start = src.index("function configFromQuery(")
        body = src[start:src.index("\n}\n", start)]
        read = set(re.findall(r'params\.(?:get|has)\("([a-z_]+)"\)', body))
        # Numeric fields are read through a helper, from a list of [key, field] pairs.
        read |= set(re.findall(r'\["([a-z_]+)", "[A-Za-z]+"\]', body))
        self.assertEqual(read, set(self.out["queryKeys"]))

    # ----------------------------------------------------- blocked storage

    def test_storage_that_cannot_be_used_counts_as_no_flag(self):
        for name in ("storage_throw", "storage_absent", "session_throw", "session_absent"):
            with self.subTest(case=name):
                case = self.out[name]
                self.assertBooted(case)
                self.assertTrue(case["introOpen"])
                self.assertEqual(case["workers"], 0)

    def test_dont_show_again_closes_the_popup_when_local_storage_is_blocked(self):
        for name in ("storage_throw_never", "storage_absent_never"):
            with self.subTest(case=name):
                case = self.out[name]
                self.assertIsNone(case["clickError"])
                self.assertFalse(case["introOpen"])
                self.assertEqual(case["session"], "closed")  # this tab still holds it

    def test_closing_the_popup_when_session_storage_is_blocked_raises_nothing(self):
        for name in ("session_throw_closed", "session_absent_closed"):
            with self.subTest(case=name):
                case = self.out[name]
                self.assertIsNone(case["closeError"])
                self.assertFalse(case["introOpen"])
                self.assertIsNone(case["flag"])  # nothing lasting was written instead

    # -------------------------------------------------------- closing it

    def test_every_way_out_of_the_popup_sets_the_session_flag(self):
        for name, case in self.out["routes"].items():
            with self.subTest(route=name):
                self.assertBooted(case)
                self.assertFalse(case["introOpen"])
                self.assertEqual(case["session"], "closed")

    def test_only_dont_show_again_writes_the_lasting_flag(self):
        for name, case in self.out["routes"].items():
            if name != "never":
                with self.subTest(route=name):
                    self.assertEqual(case["flagSets"], [["set", "ludicrous-intro", "session"]])
                    self.assertIsNone(case["flag"])

    def test_dont_show_again_writes_never_then_closes_the_popup(self):
        case = self.out["routes"]["never"]
        self.assertEqual(case["flag"], "never")
        self.assertEqual(case["session"], "closed")
        calls = case["calls"]
        never = calls.index(["set", "local", "ludicrous-intro", "never"])
        close = calls.index(["close", "#intro"])
        closed = calls.index(["set", "session", "ludicrous-intro", "closed"])
        self.assertLess(never, close)
        self.assertLess(close, closed)
        self.assertEqual(case["workers"], 0)
        self.assertNotIn(["showModal", "#tour"], calls)

    def test_a_click_inside_the_popup_leaves_it_open(self):
        case = self.out["innerClick"]
        self.assertTrue(case["introOpen"])
        self.assertIsNone(case["flag"])
        self.assertIsNone(case["session"])

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

    # ------------------------------------------------------------ the tour

    def test_tour_steps_are_the_nine_in_order(self):
        steps = self.out["tourSteps"]
        self.assertEqual([step["key"] for step in steps], TOUR_KEYS)
        for step in steps:
            with self.subTest(step=step["key"]):
                self.assertTrue(step["title"])
                self.assertTrue(step["text"])

    def test_step_texts_name_what_holds_only_in_some_states(self):
        text = {step["key"]: step["text"] for step in self.out["tourSteps"]}
        self.assertIn("In War, the hint", text["size"])
        self.assertNotIn("in seconds", text["run"])
        self.assertIn("When you watch from the start", text["chart"])

    def test_tour_link_walks_the_steps_on_screen(self):
        expected = {"empty": WITHOUT_GAME, "game": TOUR_KEYS,
                    "condensed": WITHOUT_GAME, "blackjackBatch": WITHOUT_GAME}
        for screen, keys in expected.items():
            with self.subTest(screen=screen):
                walk = self.out["walks"][screen]
                steps = walk["steps"]
                self.assertEqual(steps[0]["tour"], {"keys": keys, "index": 0})
                self.assertEqual([s["count"] for s in steps],
                                 [f"{i} of {len(keys)}" for i in range(1, len(keys) + 1)])
                self.assertTrue(steps[0]["backDisabled"])
                self.assertTrue(all(not s["backDisabled"] for s in steps[1:]))
                self.assertEqual([s["next"] for s in steps], ["Next"] * (len(keys) - 1) + ["Done"])
                self.assertTrue(all(s["focus"] == "#tourNext" for s in steps))
                # Done ends it, and focus goes back to the Tour link.
                self.assertFalse(walk["after"]["open"])
                self.assertEqual(walk["after"]["focus"], "#tourBtn")

    def test_each_element_of_a_step_gets_a_ring(self):
        war = self.out["walks"]["empty"]["steps"][2]
        self.assertEqual((war["title"], war["rings"]), ("How big", 3))
        blackjack = self.out["walks"]["blackjackBatch"]["steps"][2]
        self.assertEqual((blackjack["title"], blackjack["rings"]), ("How big", 2))

    def test_tour_pauses_playback_and_writes_nothing(self):
        for screen, walk in self.out["walks"].items():
            with self.subTest(screen=screen):
                self.assertTrue(walk["paused"])
                self.assertEqual(walk["writes"], 0)
        self.assertEqual(self.out["tourControls"]["writes"], 0)
        self.assertEqual(self.out["showMeAround"]["writesInTour"], 0)

    def test_back_end_tour_and_escape(self):
        c = self.out["tourControls"]
        self.assertEqual(c["third"]["tour"]["index"], 2)
        self.assertEqual(c["back"]["tour"]["index"], 1)
        self.assertFalse(c["ended"]["open"])
        self.assertEqual(c["ended"]["focus"], "#tourBtn")
        self.assertEqual(c["again"]["tour"]["index"], 0)  # the Tour link starts at step 1
        self.assertFalse(c["escaped"]["open"])
        self.assertIsNone(c["escaped"]["tour"])

    def test_show_me_around_closes_the_popup_then_opens_step_1(self):
        case = self.out["showMeAround"]
        self.assertEqual(case["opened"]["tour"], {"keys": WITHOUT_GAME, "index": 0})
        self.assertEqual(case["opened"]["focus"], "#tourNext")
        calls = case["calls"]
        self.assertLess(calls.index(["close", "#intro"]), calls.index(["showModal", "#tour"]))
        self.assertEqual(case["session"], "closed")
        self.assertIsNone(case["flag"])
        self.assertEqual(case["flagSets"], [["set", "ludicrous-intro", "session"]])
        self.assertFalse(case["after"]["open"])
        self.assertEqual(case["after"]["focus"], "#simulateBtn")

    def test_panel_placement(self):
        place = self.out["place"]
        # 1,280 x 800 viewport, a 340 x 150 panel, 10 px gap, 12 px margin.
        self.assertEqual(place["below"], {"left": "900px", "top": "104px", "rings": 1})
        self.assertEqual(place["above"], {"left": "300px", "top": "540px", "rings": 1})
        self.assertEqual(place["right"], {"left": "928px", "top": "104px", "rings": 1})
        # No box left: centred, no ring, and the steps still move.
        self.assertEqual(place["none"]["rings"], 0)
        self.assertEqual((place["none"]["left"], place["none"]["top"]), ("470px", "325px"))
        self.assertEqual(place["stepsOn"], "Pick a game")

    def test_tour_does_not_open_while_a_run_is_claimed(self):
        self.assertFalse(self.out["claimedTourLink"]["open"])
        case = self.out["claimedShowMeAround"]
        self.assertFalse(case["open"])
        self.assertFalse(case["introOpen"])

    def test_preset_claims_the_run_before_the_grid_wait(self):
        case = self.out["presetWait"]
        self.assertTrue(case["claimedAtOnce"])
        self.assertFalse(case["tourDuringWait"])
        self.assertEqual(case["workersDuringWait"], 0)
        [message] = case["messages"]
        self.assertEqual((message["players"], message["seed"]), (1000, 10))

    def test_run_started_during_a_preset_grid_wait_keeps_its_claim(self):
        case = self.out["presetRunDuringWait"]
        [message] = case["messages"]  # the preset gave way: one run
        self.assertEqual((message["players"], message["decks"]), (6, 3))
        self.assertTrue(case["stillClaimed"])

    def test_run_that_finishes_during_a_preset_grid_wait_still_wins(self):
        case = self.out["presetRunDoneDuringWait"]
        [message] = case["messages"]  # the preset gave way though the button was free
        self.assertEqual((message["players"], message["decks"]), (6, 3))

    def test_keys_are_ignored_while_the_tour_is_open(self):
        case = self.out["keysTourOpen"]
        self.assertTrue(case["opened"])
        self.assertTrue(case["boxOpen"])

    def test_back_or_forward_ends_the_tour_before_the_run(self):
        case = self.out["popstateTour"]
        self.assertTrue(case["opened"])
        self.assertFalse(case["tourOpen"])
        calls = case["calls"]
        self.assertLess(calls.index(["close", "#tour"]), calls.index(["worker"]))
        self.assertEqual(case["workers"], 1)

    def test_a_game_loading_ends_the_tour(self):
        case = self.out["importDuringTour"]
        self.assertTrue(case["opened"])
        self.assertFalse(case["tourOpen"])
        self.assertIsNone(case["tour"])
        self.assertIsNone(case["error"])  # the import itself went through


if __name__ == "__main__":
    unittest.main()
