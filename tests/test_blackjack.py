"""Tests for the Blackjack engine and strategies.

Rigged games overwrite the shoe after start(); cards are listed in deal
order (the engine pops from the end, so the helper reverses them). Deal
order each round: one card per seat, dealer upcard, second card per seat,
dealer hole card, then hit/double cards as requested.
"""
import unittest

from engine import events as ev
from engine.blackjack import (
    DOUBLE, HIT, STAND, BasicStrategy, BlackjackGame, hand_value,
)
from engine.cards import Card


def C(rank, suit="Spades"):
    return Card(rank, suit)


def rigged(cards_in_deal_order, seats=1, strategies=None, rounds=1):
    game = BlackjackGame(seats, 1, rounds, strategies=strategies or ["basic"], seed=0)
    game.start()
    game.shoe = list(reversed(cards_in_deal_order))
    game._reshuffle_at = 0  # keep the rigged shoe
    return game


def results(game):
    return [e for e in game.events if isinstance(e, ev.HandResult)]


class TestHandValue(unittest.TestCase):
    def test_values(self):
        self.assertEqual(hand_value([C(14)]), (11, True))
        self.assertEqual(hand_value([C(14), C(14, "Hearts")]), (12, True))
        self.assertEqual(hand_value([C(14), C(13)]), (21, True))
        self.assertEqual(hand_value([C(14), C(6)]), (17, True))
        self.assertEqual(hand_value([C(14), C(6), C(10)]), (17, False))
        self.assertEqual(hand_value([C(10), C(9), C(5)]), (24, False))
        self.assertEqual(hand_value([C(14), C(14, "Hearts"), C(9)]), (21, True))


class TestRounds(unittest.TestCase):
    def test_player_blackjack_pays_three_to_two(self):
        game = rigged([C(14), C(9, "Diamonds"), C(13), C(5, "Clubs")])
        game.play_round()
        self.assertEqual(results(game)[0].outcome, "blackjack")
        self.assertEqual(game.seats[1].bankroll, 1.5)
        self.assertEqual(game.seats[1].blackjacks, 1)

    def test_dealer_blackjack_beats_ordinary_hand(self):
        game = rigged([C(10), C(14, "Diamonds"), C(9, "Hearts"), C(13, "Clubs")])
        game.play_round()
        self.assertEqual(results(game)[0].outcome, "lose")
        self.assertEqual(game.seats[1].bankroll, -1.0)
        # dealer peeked: the player never acted
        self.assertEqual([e for e in game.events if isinstance(e, ev.SeatAction)], [])

    def test_both_blackjacks_push(self):
        game = rigged([C(14), C(14, "Diamonds"), C(13), C(12, "Clubs")])
        game.play_round()
        self.assertEqual(results(game)[0].outcome, "push")
        self.assertEqual(game.seats[1].bankroll, 0.0)

    def test_player_busts(self):
        game = rigged(
            [C(10, "Hearts"), C(7, "Diamonds"), C(6, "Hearts"), C(9, "Diamonds"), C(10)],
            strategies=["hit-below-17"],
        )
        game.play_round()
        self.assertEqual(results(game)[0].outcome, "bust")
        self.assertEqual(game.seats[1].bankroll, -1.0)
        self.assertEqual(game.seats[1].busts, 1)

    def test_dealer_busts_player_wins(self):
        game = rigged(
            [C(10, "Hearts"), C(6, "Diamonds"), C(8, "Hearts"), C(10, "Clubs"), C(10, "Diamonds")]
        )
        game.play_round()
        self.assertEqual(results(game)[0].outcome, "win")
        self.assertEqual(results(game)[0].dealer_total, 26)
        self.assertEqual(game.seats[1].bankroll, 1.0)

    def test_equal_totals_push(self):
        game = rigged([C(10, "Hearts"), C(10, "Diamonds"), C(8, "Hearts"), C(8, "Clubs")])
        game.play_round()
        self.assertEqual(results(game)[0].outcome, "push")

    def test_double_down_doubles_the_payout(self):
        # basic strategy: 11 vs dealer 6 -> double; dealer 16 draws to bust
        game = rigged(
            [C(6, "Hearts"), C(6, "Diamonds"), C(5, "Hearts"), C(10, "Clubs"),
             C(13), C(10, "Diamonds")]
        )
        game.play_round()
        actions = [e.action for e in game.events if isinstance(e, ev.SeatAction)]
        self.assertEqual(actions, [DOUBLE])
        self.assertEqual(game.seats[1].bankroll, 2.0)
        # doubled hand took exactly one card
        player_cards = [e for e in game.events
                        if isinstance(e, ev.CardDealt) and e.seat == 1]
        self.assertEqual(len(player_cards), 3)

    def test_session_ends_and_bankroll_is_sum_of_payouts(self):
        game = BlackjackGame(3, 2, num_rounds=50,
                             strategies=["basic", "hit-below-17"], seed=5)
        game.run()
        self.assertTrue(game.is_over)
        self.assertEqual(game.round, 50)
        for seat in game.seats.values():
            payouts = sum(e.payout for e in results(game) if e.seat == seat.id)
            self.assertAlmostEqual(seat.bankroll, payouts)
            self.assertEqual(seat.hands, 50)


class TestBasicStrategy(unittest.TestCase):
    def test_chart_spot_checks(self):
        s = BasicStrategy()
        hard = lambda a, b: [C(a, "Hearts"), C(b, "Clubs")]
        self.assertEqual(s.decide(hard(10, 6), 10, True), HIT)     # 16 v 10
        self.assertEqual(s.decide(hard(10, 6), 6, True), STAND)    # 16 v 6
        self.assertEqual(s.decide(hard(10, 2), 2, True), HIT)      # 12 v 2
        self.assertEqual(s.decide(hard(10, 2), 4, True), STAND)    # 12 v 4
        self.assertEqual(s.decide(hard(6, 5), 6, True), DOUBLE)    # 11 v 6
        self.assertEqual(s.decide(hard(6, 5), 6, False), HIT)      # 11 v 6, no double
        self.assertEqual(s.decide(hard(5, 4), 3, True), DOUBLE)    # 9 v 3
        self.assertEqual(s.decide(hard(5, 5), 10, True), HIT)      # 10 v 10
        soft = lambda b: [C(14, "Hearts"), C(b, "Clubs")]
        self.assertEqual(s.decide(soft(7), 9, True), HIT)          # A7 v 9
        self.assertEqual(s.decide(soft(7), 3, True), DOUBLE)       # A7 v 3
        self.assertEqual(s.decide(soft(7), 2, True), STAND)        # A7 v 2
        self.assertEqual(s.decide(soft(8), 6, True), STAND)        # A8


class TestSessions(unittest.TestCase):
    def test_determinism(self):
        a = BlackjackGame(4, 6, 200, strategies=["basic", "hit-below-16"], seed=42)
        b = BlackjackGame(4, 6, 200, strategies=["basic", "hit-below-16"], seed=42)
        a.run()
        b.run()
        self.assertEqual(a.summary(), b.summary())
        self.assertEqual([e.to_dict() for e in a.events], [e.to_dict() for e in b.events])

    def test_record_events_off_same_game(self):
        a = BlackjackGame(3, 6, 100, seed=9)
        b = BlackjackGame(3, 6, 100, seed=9, record_events=False)
        a.run()
        b.run()
        self.assertEqual(b.events, [])
        self.assertEqual(a.summary(), b.summary())

    def test_round_robin_strategy_assignment(self):
        game = BlackjackGame(4, 6, 10, strategies=["basic", "hit-below-17"], seed=1)
        game.run()
        per = game.per_strategy()
        self.assertEqual(game.seats[1].strategy_name, "basic")
        self.assertEqual(game.seats[2].strategy_name, "hit-below-17")
        self.assertEqual(game.seats[3].strategy_name, "basic")
        self.assertEqual(per["basic"]["hands"], 20)
        self.assertEqual(per["hit-below-17"]["hands"], 20)

    def test_house_edge_sanity(self):
        # 5,000 basic-strategy hands: EV should be small and negative-ish,
        # never wildly positive or a double-digit loss.
        game = BlackjackGame(10, 6, 500, strategies=["basic"], seed=1)
        game.run()
        ev_per_hand = game.per_strategy()["basic"]["ev"]
        self.assertGreater(ev_per_hand, -0.08)
        self.assertLess(ev_per_hand, 0.04)

    def test_validation(self):
        with self.assertRaises(ValueError):
            BlackjackGame(0, 6, 10)
        with self.assertRaises(ValueError):
            BlackjackGame(2, 6, 10, strategies=["card-counting"])
        with self.assertRaises(ValueError):
            BlackjackGame(30, 1, 10)  # not enough shoe


if __name__ == "__main__":
    unittest.main()
