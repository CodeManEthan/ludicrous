"""Headless multi-seat Blackjack engine with pluggable strategies.

Rules (documented so measured edges are interpretable):
- Dealer stands on all 17s (S17), blackjack pays 3:2, dealer peeks for
  blackjack when showing an ace or ten-value card.
- Players may hit, stand, or double (double = double the bet, take exactly
  one card) on their first two cards. No splitting, insurance, or surrender
  yet — so measured house edges will be somewhat worse than the published
  ~0.5% full-basic-strategy figure until those rules are added.
- Flat 1-unit bet per seat per round; bankrolls track cumulative units.
- The shoe reshuffles between rounds when it runs low (and mid-round in the
  rare case it empties, by rebuilding a fresh shoe).

A game is a session of `num_rounds` rounds at a table of `num_seats` seats.
Each seat plays a Strategy: an object with
    decide(hand, dealer_up_value, can_double) -> "hit" | "stand" | "double"
where hand is the seat's list of Cards and dealer_up_value is 2-11 (ace=11).
Strategies are registered by name in STRATEGIES and assigned to seats
round-robin from the `strategies` list, so a table can mix strategies and a
batch can compare them under identical conditions.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import events as ev
from .cards import Card, build_shoe

HIT, STAND, DOUBLE = "hit", "stand", "double"
DEALER = 0  # seat id used for the dealer in CardDealt events


def card_value(card: Card) -> int:
    """Blackjack value of a card; aces count 11 here (softened in hand_value)."""
    if card.rank >= 11 and card.rank <= 13:
        return 10
    if card.rank == 14:
        return 11
    return card.rank


def hand_value(cards: list[Card]) -> tuple[int, bool]:
    """(best total, is_soft) — soft means an ace is currently counted as 11."""
    total = 0
    aces = 0
    for card in cards:
        value = card_value(card)
        if value == 11:
            aces += 1
        total += value
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total, aces > 0


def is_blackjack(cards: list[Card]) -> bool:
    return len(cards) == 2 and hand_value(cards)[0] == 21


# ------------------------------------------------------------- strategies

class HitBelow:
    """Hit until reaching the threshold, then stand. Ignores the dealer."""

    def __init__(self, threshold: int):
        self.threshold = threshold

    def decide(self, hand, dealer_up, can_double):
        return HIT if hand_value(hand)[0] < self.threshold else STAND


class NeverBust:
    """Hit only when busting is impossible: hard 11 or less, or soft 17 or less
    (one card can never bust a soft hand)."""

    def decide(self, hand, dealer_up, can_double):
        total, soft = hand_value(hand)
        if total <= 11 or (soft and total <= 17):
            return HIT
        return STAND


class BasicStrategy:
    """Total-dependent basic strategy for S17 hit/stand/double (no splits)."""

    def decide(self, hand, dealer_up, can_double):
        total, soft = hand_value(hand)
        if soft:
            if total >= 19:
                return STAND
            if total == 18:
                if 3 <= dealer_up <= 6:
                    return DOUBLE if can_double else STAND
                return STAND if dealer_up in (2, 7, 8) else HIT
            if can_double:
                if total in (13, 14) and dealer_up in (5, 6):
                    return DOUBLE
                if total in (15, 16) and 4 <= dealer_up <= 6:
                    return DOUBLE
                if total == 17 and 3 <= dealer_up <= 6:
                    return DOUBLE
            return HIT
        if total >= 17:
            return STAND
        if total >= 13:
            return STAND if dealer_up <= 6 else HIT
        if total == 12:
            return STAND if 4 <= dealer_up <= 6 else HIT
        if can_double:
            if total == 11 and dealer_up <= 10:
                return DOUBLE
            if total == 10 and dealer_up <= 9:
                return DOUBLE
            if total == 9 and 3 <= dealer_up <= 6:
                return DOUBLE
        return HIT


# name -> (factory, display label); assigned to seats round-robin
STRATEGIES = {
    "basic": (BasicStrategy, "Basic strategy"),
    "never-bust": (NeverBust, "Never bust"),
    "hit-below-15": (lambda: HitBelow(15), "Hit below 15"),
    "hit-below-16": (lambda: HitBelow(16), "Hit below 16"),
    "hit-below-17": (lambda: HitBelow(17), "Hit below 17"),
}


def make_strategy(name: str):
    if name not in STRATEGIES:
        raise ValueError(f"unknown strategy {name!r} (available: {', '.join(STRATEGIES)})")
    return STRATEGIES[name][0]()


# ------------------------------------------------------------------- game

@dataclass
class SeatState:
    id: int
    name: str
    strategy_name: str
    strategy: object
    bankroll: float = 0.0
    hands: int = 0
    wins: int = 0
    losses: int = 0
    pushes: int = 0
    blackjacks: int = 0
    busts: int = 0
    outcomes: dict = field(default_factory=dict)  # unused placeholder for future rules


class BlackjackGame:
    def __init__(
        self,
        num_seats: int,
        num_decks: int = 6,
        num_rounds: int = 100,
        strategies: list[str] | None = None,
        seed: int | None = None,
        record_events: bool = True,
    ):
        if num_seats < 1:
            raise ValueError("Blackjack needs at least 1 seat")
        if num_decks < 1:
            raise ValueError("Blackjack needs at least 1 deck")
        if num_rounds < 1:
            raise ValueError("Blackjack needs at least 1 round")
        if num_decks * 52 < (num_seats + 1) * 4:
            raise ValueError(
                f"{num_decks} deck(s) is not enough shoe for {num_seats} seats"
            )
        strategies = strategies or ["basic"]
        for name in strategies:
            if name not in STRATEGIES:
                raise ValueError(f"unknown strategy {name!r} (available: {', '.join(STRATEGIES)})")

        self.num_seats = num_seats
        self.num_decks = num_decks
        self.num_rounds = num_rounds
        self.strategy_names = strategies
        self.seed = seed
        self.rng = random.Random(seed)
        self.seats = {}
        for i in range(1, num_seats + 1):
            name = strategies[(i - 1) % len(strategies)]
            self.seats[i] = SeatState(
                id=i,
                name=f"Seat {i}",
                strategy_name=name,
                strategy=make_strategy(name),
            )
        self.shoe: list[Card] = []
        self.events: list[ev.Event] = []
        self.record_events = record_events
        self.round = 0
        self.is_over = False
        self.winner: int | None = None
        self._started = False
        # reshuffle between rounds once the shoe dips below this
        self._reshuffle_at = max(12, min(15 * (num_seats + 1), num_decks * 52 // 3))

    # ------------------------------------------------------------- helpers

    def _emit(self, event: ev.Event) -> None:
        if self.record_events:
            self.events.append(event)

    def _reshuffle(self) -> None:
        self.shoe = build_shoe(self.num_decks)
        self.rng.shuffle(self.shoe)
        self._emit(ev.ShoeShuffled(round=self.round, cards=len(self.shoe)))

    def _draw(self) -> Card:
        if not self.shoe:  # rare mid-round exhaustion: rebuild a fresh shoe
            self._reshuffle()
        return self.shoe.pop()

    def _deal(self, seat: int, hand: list[Card], face_up: bool = True) -> Card:
        card = self._draw()
        hand.append(card)
        self._emit(ev.CardDealt(round=self.round, seat=seat, card=card, face_up=face_up))
        return card

    # --------------------------------------------------------------- play

    def start(self) -> None:
        if self._started:
            raise RuntimeError("game already started")
        self._started = True
        self._emit(
            ev.GameStarted(
                round=0,
                num_players=self.num_seats,
                num_decks=self.num_decks,
                player_names={s.id: s.name for s in self.seats.values()},
                seed=self.seed,
            )
        )
        self._emit(
            ev.StrategiesAssigned(
                round=0,
                strategies={s.id: s.strategy_name for s in self.seats.values()},
            )
        )
        self._reshuffle()

    def play_round(self) -> list[ev.Event]:
        if not self._started:
            self.start()
        if self.is_over:
            raise RuntimeError("game is already over")
        mark = len(self.events)
        self.round += 1
        if len(self.shoe) < self._reshuffle_at:
            self._reshuffle()

        seat_ids = list(self.seats)
        self._emit(ev.RoundStarted(round=self.round, players=seat_ids))

        # initial deal: one card around, dealer up, second card around, hole
        hands: dict[int, list[Card]] = {sid: [] for sid in seat_ids}
        dealer: list[Card] = []
        bets = {sid: 1.0 for sid in seat_ids}
        for sid in seat_ids:
            self._deal(sid, hands[sid])
        self._deal(DEALER, dealer)
        for sid in seat_ids:
            self._deal(sid, hands[sid])
        self._deal(DEALER, dealer, face_up=False)

        dealer_up = card_value(dealer[0])
        dealer_bj = dealer_up in (10, 11) and is_blackjack(dealer)  # peek

        # player turns (skipped entirely if the dealer has blackjack)
        busted: set[int] = set()
        naturals = {sid for sid in seat_ids if is_blackjack(hands[sid])}
        if not dealer_bj:
            for sid in seat_ids:
                if sid in naturals:
                    continue
                hand = hands[sid]
                while True:
                    total, _ = hand_value(hand)
                    if total >= 21:
                        break
                    action = self.seats[sid].strategy.decide(hand, dealer_up, len(hand) == 2)
                    if action == DOUBLE and len(hand) != 2:
                        action = HIT  # illegal double downgraded
                    if action == HIT:
                        self._deal(sid, hand)
                        self._emit(ev.SeatAction(round=self.round, seat=sid,
                                                 action=HIT, total=hand_value(hand)[0]))
                    elif action == DOUBLE:
                        bets[sid] *= 2
                        self._deal(sid, hand)
                        self._emit(ev.SeatAction(round=self.round, seat=sid,
                                                 action=DOUBLE, total=hand_value(hand)[0]))
                        break
                    else:
                        self._emit(ev.SeatAction(round=self.round, seat=sid,
                                                 action=STAND, total=total))
                        break
                if hand_value(hand)[0] > 21:
                    busted.add(sid)

        # dealer plays only if someone still needs a dealer total
        live = [sid for sid in seat_ids if sid not in busted and sid not in naturals]
        if dealer_bj or live:
            self._emit(ev.DealerRevealed(round=self.round, card=dealer[1],
                                         total=hand_value(dealer)[0]))
        if live and not dealer_bj:
            while hand_value(dealer)[0] < 17:  # S17: stand on all 17s
                self._deal(DEALER, dealer)
        dealer_total = hand_value(dealer)[0]

        # settle
        for sid in seat_ids:
            seat = self.seats[sid]
            player_total = hand_value(hands[sid])[0]
            if dealer_bj:
                outcome, payout = ("push", 0.0) if sid in naturals else ("lose", -bets[sid])
            elif sid in naturals:
                outcome, payout = "blackjack", 1.5
            elif sid in busted:
                outcome, payout = "bust", -bets[sid]
            elif dealer_total > 21 or player_total > dealer_total:
                outcome, payout = "win", bets[sid]
            elif player_total < dealer_total:
                outcome, payout = "lose", -bets[sid]
            else:
                outcome, payout = "push", 0.0
            seat.bankroll += payout
            seat.hands += 1
            if outcome in ("win",):
                seat.wins += 1
            elif outcome in ("lose", "bust"):
                seat.losses += 1
                if outcome == "bust":
                    seat.busts += 1
            elif outcome == "push":
                seat.pushes += 1
            if outcome == "blackjack":
                seat.wins += 1
                seat.blackjacks += 1
            self._emit(ev.HandResult(round=self.round, seat=sid, outcome=outcome,
                                     payout=payout, player_total=player_total,
                                     dealer_total=dealer_total))

        self._emit(ev.RoundSettled(round=self.round,
                                   bankrolls={s.id: round(s.bankroll, 1)
                                              for s in self.seats.values()}))
        if self.round >= self.num_rounds:
            self.is_over = True
            self.winner = max(self.seats.values(), key=lambda s: (s.bankroll, -s.id)).id
            self._emit(ev.GameOver(round=self.round, winner=self.winner,
                                   total_rounds=self.round))
        return self.events[mark:]

    def run(self, max_rounds: int | None = None) -> dict:
        if not self._started:
            self.start()
        while not self.is_over and (max_rounds is None or self.round < max_rounds):
            self.play_round()
        return self.summary()

    # ---------------------------------------------------------- inspection

    def per_strategy(self) -> dict:
        totals: dict[str, dict] = {}
        for seat in self.seats.values():
            entry = totals.setdefault(seat.strategy_name,
                                      {"hands": 0, "net": 0.0, "seats": 0})
            entry["hands"] += seat.hands
            entry["net"] += seat.bankroll
            entry["seats"] += 1
        for entry in totals.values():
            entry["net"] = round(entry["net"], 1)
            entry["ev"] = entry["net"] / entry["hands"] if entry["hands"] else 0.0
        return totals

    def standings(self) -> list[int]:
        return [s.id for s in sorted(self.seats.values(),
                                     key=lambda s: (-s.bankroll, s.id))]

    def summary(self) -> dict:
        return {
            "game": "blackjack",
            "num_players": self.num_seats,
            "num_decks": self.num_decks,
            "num_rounds": self.num_rounds,
            "seed": self.seed,
            "completed": self.is_over,
            "rounds": self.round,
            "winner": self.winner,
            "winner_name": self.seats[self.winner].name if self.winner else None,
            "standings": self.standings(),
            "seats": {
                s.id: {
                    "name": s.name,
                    "strategy": s.strategy_name,
                    "bankroll": round(s.bankroll, 1),
                    "hands": s.hands,
                    "wins": s.wins,
                    "losses": s.losses,
                    "pushes": s.pushes,
                    "blackjacks": s.blackjacks,
                    "busts": s.busts,
                }
                for s in self.seats.values()
            },
            "per_strategy": self.per_strategy(),
        }
