"""Headless card game engine — no GUI dependencies."""
from . import events
from .batch import run_batch, summarize_batch
from .cards import Card, RANK_NAMES, SUITS, build_shoe
from .war import PlayerState, WarGame

__all__ = [
    "Card",
    "RANK_NAMES",
    "SUITS",
    "build_shoe",
    "PlayerState",
    "WarGame",
    "events",
    "run_batch",
    "summarize_batch",
]
