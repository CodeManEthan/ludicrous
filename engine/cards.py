"""Card primitives shared by all games."""
from typing import NamedTuple

SUITS = ("Hearts", "Diamonds", "Clubs", "Spades")

RANK_NAMES = {11: "Jack", 12: "Queen", 13: "King", 14: "Ace"}


class Card(NamedTuple):
    rank: int  # 2-14 (Ace high)
    suit: str

    def __str__(self):
        return f"{RANK_NAMES.get(self.rank, str(self.rank))} of {self.suit}"


def build_shoe(num_decks: int) -> list[Card]:
    """All cards in play: `num_decks` standard 52-card decks."""
    return [
        Card(rank, suit)
        for _ in range(num_decks)
        for suit in SUITS
        for rank in range(2, 15)
    ]
