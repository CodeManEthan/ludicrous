"""Game events.

The engine emits these as it simulates. The full event list is a complete
recording of a game: any frontend can replay it at any speed without
re-running the simulation. All events are JSON-serializable via `to_dict()`
(note: JSON object keys become strings, and cards become [rank, suit] pairs).
"""
from dataclasses import dataclass, asdict

from .cards import Card


@dataclass
class Event:
    round: int  # round number the event belongs to (0 = pre-game)

    @property
    def type(self) -> str:
        return type(self).__name__

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type
        return d


@dataclass
class GameStarted(Event):
    num_players: int
    num_decks: int
    player_names: dict[int, str]
    seed: int | None


@dataclass
class CardsDealt(Event):
    card_counts: dict[int, int]


@dataclass
class RoundStarted(Event):
    players: list[int]


@dataclass
class CardPlayed(Event):
    player: int
    card: Card
    face_up: bool


@dataclass
class WarDeclared(Event):
    players: list[int]  # players tied at the highest rank
    rank: int
    depth: int  # 1 = first war of the round, 2 = war within a war, ...
    tiebreaker: str  # Default | Forfeit | Modified | Modified Forfeit | Draw


@dataclass
class PlayerEliminated(Event):
    player: int
    reason: str  # "out_of_cards" | "insufficient_for_war"


@dataclass
class RoundWon(Event):
    winner: int
    cards_won: int
    via: str  # "high_card" | "war" | "forfeit"


@dataclass
class RoundDrawn(Event):
    players: list[int]
    cards_returned: dict[int, int]


@dataclass
class RoundEnded(Event):
    card_counts: dict[int, int]  # in-game players only, after eliminations


@dataclass
class GameOver(Event):
    winner: int | None
    total_rounds: int


# --------------------------------------------------------------- blackjack
# Seat 0 is the dealer in CardDealt events.

@dataclass
class StrategiesAssigned(Event):
    strategies: dict[int, str]  # seat -> strategy name


@dataclass
class ShoeShuffled(Event):
    cards: int  # shoe size after shuffling


@dataclass
class CardDealt(Event):
    seat: int  # 0 = dealer
    card: Card
    face_up: bool


@dataclass
class SeatAction(Event):
    seat: int
    action: str  # "hit" | "stand" | "double"
    total: int   # hand total after the action resolves


@dataclass
class DealerRevealed(Event):
    card: Card
    total: int


@dataclass
class HandResult(Event):
    seat: int
    outcome: str  # "win" | "lose" | "push" | "blackjack" | "bust"
    payout: float  # in bet units: +1 win, -1 lose, +1.5 blackjack, ±2 doubled
    player_total: int
    dealer_total: int


@dataclass
class RoundSettled(Event):
    bankrolls: dict[int, float]  # seat -> cumulative units won/lost
