"""Tests for the batch runner and the no-recording fast path."""
import unittest

from engine import WarGame, run_batch, summarize_batch


class TestRecordEventsOff(unittest.TestCase):
    def test_no_events_but_same_game(self):
        recorded = WarGame(4, 2, seed=11)
        recorded.run(max_rounds=100_000)
        fast = WarGame(4, 2, seed=11, record_events=False)
        fast.run(max_rounds=100_000)

        self.assertEqual(fast.events, [])
        self.assertGreater(len(recorded.events), 0)
        # identical game, identical stats
        self.assertEqual(fast.winner, recorded.winner)
        self.assertEqual(fast.round, recorded.round)
        self.assertEqual(fast.war_count, recorded.war_count)
        self.assertEqual(fast.deepest_war, recorded.deepest_war)
        self.assertEqual(fast.biggest_pot, recorded.biggest_pot)

    def test_inline_stats_match_event_log(self):
        from engine import events as ev
        game = WarGame(6, 2, seed=3)
        game.run(max_rounds=100_000)
        from_events_deepest = max(e.depth for e in game.events if isinstance(e, ev.WarDeclared))
        from_events_pot = max(e.cards_won for e in game.events if isinstance(e, ev.RoundWon))
        self.assertEqual(game.deepest_war, from_events_deepest)
        self.assertEqual(game.biggest_pot, from_events_pot)


class TestBatch(unittest.TestCase):
    def test_batch_runs_and_is_deterministic(self):
        a = run_batch(num_players=4, num_decks=1, num_games=12, base_seed=100)
        b = run_batch(num_players=4, num_decks=1, num_games=12, base_seed=100)
        self.assertEqual(len(a), 12)
        self.assertEqual(a, b)
        self.assertEqual([g["seed"] for g in a], list(range(100, 112)))
        self.assertTrue(all(g["completed"] for g in a))

    def test_batch_matches_individual_games(self):
        batch = run_batch(num_players=3, num_decks=1, num_games=4, base_seed=7)
        for row in batch:
            game = WarGame(3, 1, seed=row["seed"])
            game.run(max_rounds=1_000_000)
            self.assertEqual(row["winner"], game.winner)
            self.assertEqual(row["rounds"], game.round)

    def test_summarize(self):
        games = [
            {"seed": 0, "completed": True, "rounds": 100, "winner": 1, "wars": 5, "deepest_war": 1, "biggest_pot": 10},
            {"seed": 1, "completed": True, "rounds": 300, "winner": 2, "wars": 15, "deepest_war": 3, "biggest_pot": 30},
            {"seed": 2, "completed": True, "rounds": 200, "winner": 1, "wars": 10, "deepest_war": 2, "biggest_pot": 20},
        ]
        agg = summarize_batch(games)
        self.assertEqual(agg["games"], 3)
        self.assertEqual(agg["rounds"]["min"], 100)
        self.assertEqual(agg["rounds"]["max"], 300)
        self.assertEqual(agg["rounds"]["mean"], 200)
        self.assertEqual(agg["rounds"]["median"], 200)
        self.assertEqual(agg["wins_by_seat"], {1: 2, 2: 1})
        self.assertEqual(agg["deepest_war"], 3)
        self.assertEqual(agg["biggest_pot"], 30)
        self.assertEqual(agg["shortest"][0]["seed"], 0)
        self.assertEqual(agg["longest"][0]["seed"], 1)

    def test_summarize_excludes_unfinished_from_distribution(self):
        games = [
            {"seed": 0, "completed": True, "rounds": 100, "winner": 1, "wars": 5, "deepest_war": 1, "biggest_pot": 10},
            {"seed": 1, "completed": True, "rounds": 200, "winner": 2, "wars": 10, "deepest_war": 2, "biggest_pot": 20},
            {"seed": 2, "completed": False, "rounds": 1_000_000, "winner": None, "wars": 900, "deepest_war": 6, "biggest_pot": 99},
        ]
        agg = summarize_batch(games)
        self.assertEqual(agg["unfinished"], 1)
        self.assertEqual(agg["completed"], 2)
        # capped game excluded from the rounds distribution...
        self.assertEqual(agg["rounds"]["max"], 200)
        self.assertEqual(agg["rounds"]["mean"], 150)
        self.assertEqual(agg["mean_wars"], 7.5)
        # ...but still present in the outlier list and event-derived maxima
        self.assertEqual(agg["longest"][0]["seed"], 2)
        self.assertEqual(agg["deepest_war"], 6)

    def test_batch_respects_max_rounds(self):
        rows = run_batch(num_players=4, num_decks=2, num_games=6, base_seed=0, max_rounds=50)
        self.assertTrue(all(g["rounds"] <= 50 for g in rows))
        self.assertTrue(any(not g["completed"] for g in rows))

    def test_invalid_config_raises_before_spawning(self):
        with self.assertRaises(ValueError):
            run_batch(num_players=60, num_decks=1, num_games=5)


if __name__ == "__main__":
    unittest.main()
