"""Headless card game engine — no GUI dependencies."""
from . import events
from .batch import (
    run_batch,
    run_blackjack_batch,
    summarize_batch,
    summarize_blackjack_batch,
)
from .blackjack import STRATEGIES, BlackjackGame
from .cards import Card, RANK_NAMES, SUITS, build_shoe
from .war import PlayerState, WarGame

__all__ = [
    "Card",
    "RANK_NAMES",
    "SUITS",
    "build_shoe",
    "PlayerState",
    "WarGame",
    "BlackjackGame",
    "STRATEGIES",
    "events",
    "run_batch",
    "summarize_batch",
    "run_blackjack_batch",
    "summarize_blackjack_batch",
]
