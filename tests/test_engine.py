"""Tests for the headless War engine.

Rigged games overwrite player decks after start() to force specific
scenarios (wars, forfeits, draws) deterministically.
"""
import json
import unittest
from collections import Counter, deque

from engine import Card, WarGame, build_shoe
from engine import events as ev


def rigged_game(hands: dict[int, list[Card]]) -> WarGame:
    game = WarGame(num_players=len(hands), seed=0)
    game.start()
    for pid, cards in hands.items():
        game.players[pid].deck = deque(cards)
        game.players[pid].reserve = []
    return game


def events_of(game: WarGame, event_type) -> list:
    return [e for e in game.events if isinstance(e, event_type)]


class TestCards(unittest.TestCase):
    def test_single_deck_composition(self):
        shoe = build_shoe(1)
        self.assertEqual(len(shoe), 52)
        self.assertEqual(len(set(shoe)), 52)
        self.assertEqual({card.rank for card in shoe}, set(range(2, 15)))

    def test_multi_deck_composition(self):
        shoe = build_shoe(3)
        self.assertEqual(len(shoe), 156)
        counts = Counter(shoe)
        self.assertTrue(all(count == 3 for count in counts.values()))


class TestSetup(unittest.TestCase):
    def test_validation(self):
        with self.assertRaises(ValueError):
            WarGame(num_players=1)
        with self.assertRaises(ValueError):
            WarGame(num_players=2, num_decks=0)
        with self.assertRaises(ValueError):
            WarGame(num_players=60, num_decks=1)  # 52 cards < 60 players
        with self.assertRaises(ValueError):
            WarGame(num_players=3, player_names=["only", "two"])

    def test_all_cards_dealt_evenly(self):
        game = WarGame(num_players=3, seed=1)
        game.start()
        counts = list(game.card_counts().values())
        self.assertEqual(sum(counts), 52)  # remainder card is dealt, not dropped
        self.assertLessEqual(max(counts) - min(counts), 1)


class TestRounds(unittest.TestCase):
    def test_high_card_wins_and_eliminates(self):
        game = rigged_game({
            1: [Card(14, "Hearts"), Card(5, "Clubs")],
            2: [Card(2, "Spades")],
        })
        game.play_round()
        self.assertTrue(game.is_over)
        self.assertEqual(game.winner, 1)
        self.assertEqual(game.players[1].card_count, 3)
        self.assertEqual(game.players[2].round_out, 1)
        eliminated = events_of(game, ev.PlayerEliminated)
        self.assertEqual(len(eliminated), 1)
        self.assertEqual(eliminated[0].reason, "out_of_cards")
        self.assertEqual(events_of(game, ev.RoundWon)[0].via, "high_card")

    def test_default_war(self):
        game = rigged_game({
            1: [Card(14, "Spades"), Card(2, "Hearts"), Card(2, "Diamonds"),
                Card(2, "Clubs"), Card(13, "Spades")],
            2: [Card(14, "Hearts"), Card(3, "Hearts"), Card(3, "Diamonds"),
                Card(3, "Clubs"), Card(12, "Spades")],
        })
        game.play_round()
        wars = events_of(game, ev.WarDeclared)
        self.assertEqual(len(wars), 1)
        self.assertEqual(wars[0].tiebreaker, "Default")
        self.assertEqual(wars[0].players, [1, 2])
        self.assertEqual(wars[0].rank, 14)
        won = events_of(game, ev.RoundWon)[0]
        self.assertEqual(won.winner, 1)  # King beats Queen
        self.assertEqual(won.via, "war")
        self.assertEqual(won.cards_won, 10)  # 2 aces + 4 + 4 war cards
        self.assertTrue(game.is_over)
        self.assertEqual(game.players[1].card_count, 10)

    def test_war_face_down_cards(self):
        game = rigged_game({
            1: [Card(14, "Spades"), Card(2, "Hearts"), Card(2, "Diamonds"),
                Card(2, "Clubs"), Card(13, "Spades")],
            2: [Card(14, "Hearts"), Card(3, "Hearts"), Card(3, "Diamonds"),
                Card(3, "Clubs"), Card(12, "Spades")],
        })
        game.play_round()
        plays = events_of(game, ev.CardPlayed)
        # 2 initial plays face up, then per player: 3 face down + 1 face up
        self.assertEqual(len(plays), 10)
        self.assertEqual(sum(1 for p in plays if not p.face_up), 6)

    def test_forfeit_war(self):
        game = rigged_game({
            1: [Card(14, "Spades"), Card(2, "Hearts"), Card(2, "Diamonds"),
                Card(2, "Clubs"), Card(13, "Spades")],
            2: [Card(14, "Hearts"), Card(3, "Hearts")],  # only 1 card after the tie
        })
        game.play_round()
        wars = events_of(game, ev.WarDeclared)
        self.assertEqual(wars[0].tiebreaker, "Forfeit")
        eliminated = events_of(game, ev.PlayerEliminated)
        self.assertEqual(eliminated[0].player, 2)
        self.assertEqual(eliminated[0].reason, "insufficient_for_war")
        won = events_of(game, ev.RoundWon)[0]
        self.assertEqual(won.winner, 1)
        self.assertEqual(won.via, "forfeit")
        self.assertTrue(game.is_over)
        self.assertEqual(game.players[1].card_count, 7)

    def test_modified_war_then_draw_splits_table(self):
        game = rigged_game({
            1: [Card(14, "Diamonds"), Card(7, "Clubs")],
            2: [Card(14, "Clubs"), Card(7, "Hearts")],
        })
        game.play_round()
        wars = events_of(game, ev.WarDeclared)
        self.assertEqual([w.tiebreaker for w in wars], ["Modified", "Draw"])
        self.assertEqual([w.depth for w in wars], [1, 2])
        self.assertEqual(len(events_of(game, ev.RoundWon)), 0)
        drawn = events_of(game, ev.RoundDrawn)[0]
        self.assertEqual(drawn.cards_returned, {1: 2, 2: 2})
        self.assertFalse(game.is_over)
        self.assertEqual(game.table, [])
        self.assertEqual(game.players[1].card_count, 2)
        self.assertEqual(game.players[2].card_count, 2)


class TestFullGames(unittest.TestCase):
    def test_determinism(self):
        game_a = WarGame(num_players=5, num_decks=2, seed=123)
        game_b = WarGame(num_players=5, num_decks=2, seed=123)
        game_a.run(max_rounds=100_000)
        game_b.run(max_rounds=100_000)
        self.assertEqual(game_a.winner, game_b.winner)
        self.assertEqual(game_a.round, game_b.round)
        self.assertEqual(
            [e.to_dict() for e in game_a.events],
            [e.to_dict() for e in game_b.events],
        )

    def test_card_conservation_every_round(self):
        game = WarGame(num_players=6, num_decks=2, seed=7)
        game.start()
        total = 104
        while not game.is_over and game.round < 100_000:
            game.play_round()
            in_hands = sum(p.card_count for p in game.players.values())
            self.assertEqual(in_hands + len(game.table), total)
            self.assertEqual(game.table, [])  # table always empty between rounds

    def test_games_complete_with_winner_holding_all_cards(self):
        for num_players in (2, 3, 10):
            for seed in range(3):
                with self.subTest(players=num_players, seed=seed):
                    game = WarGame(num_players=num_players, seed=seed)
                    summary = game.run(max_rounds=500_000)
                    self.assertTrue(summary["completed"])
                    self.assertEqual(game.players[game.winner].card_count, 52)
                    self.assertEqual(summary["standings"][0], game.winner)
                    # everyone else was eliminated with a recorded round
                    for player in game.players.values():
                        if player.id != game.winner:
                            self.assertFalse(player.in_game)
                            self.assertIsNotNone(player.round_out)

    def test_recording_is_json_serializable(self):
        game = WarGame(num_players=4, num_decks=1, seed=99)
        game.run(max_rounds=100_000)
        recording = {
            "summary": game.summary(),
            "events": [e.to_dict() for e in game.events],
        }
        parsed = json.loads(json.dumps(recording))
        self.assertEqual(parsed["summary"]["winner"], game.winner)
        self.assertEqual(parsed["events"][0]["type"], "GameStarted")
        self.assertEqual(parsed["events"][-1]["type"], "GameOver")

    def test_play_round_after_game_over_raises(self):
        game = rigged_game({
            1: [Card(14, "Hearts")],
            2: [Card(2, "Spades")],
        })
        game.play_round()
        self.assertTrue(game.is_over)
        with self.assertRaises(RuntimeError):
            game.play_round()


if __name__ == "__main__":
    unittest.main()
