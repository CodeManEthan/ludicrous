"""Headless engine for the game of War.

No GUI imports are allowed in this package — it must stay runnable anywhere:
CLI, tests, a web backend, or multiprocessing workers running thousands of
simulations.

Rules are ported from the original tkinter app's war_game_logic.py (retired,
preserved in git history), including its five tiebreaker types:
  Default          - at least two tied players have 4+ cards: each plays
                     3 face down + 1 face up; tied players with fewer than
                     4 cards forfeit their cards and are eliminated
  Forfeit          - only one tied player has 4+ cards: everyone else is
                     eliminated and that player wins the round
  Modified         - nobody has 4 cards but at least two have 1+: each plays
                     everything, last card face up
  Modified Forfeit - only one tied player has any cards left: they win
  Draw             - all tied players are out of cards: the table is split
                     evenly between them and the round has no winner

Unlike the click-driven GUI, `play_round()` resolves all wars to completion
within the round; the emitted events preserve every stage for playback.
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field

from . import events as ev
from .cards import Card, build_shoe


@dataclass
class PlayerState:
    id: int
    name: str
    deck: deque = field(default_factory=deque)  # face-down pile cards are drawn from
    reserve: list = field(default_factory=list)  # won cards, reshuffled into deck when it empties
    wins: int = 0
    in_game: bool = True
    round_out: int | None = None  # round the player was eliminated in

    @property
    def card_count(self) -> int:
        return len(self.deck) + len(self.reserve)


class WarGame:
    def __init__(
        self,
        num_players: int,
        num_decks: int = 1,
        player_names: list[str] | None = None,
        seed: int | None = None,
        record_events: bool = True,
    ):
        if num_players < 2:
            raise ValueError("War needs at least 2 players")
        if num_decks < 1:
            raise ValueError("War needs at least 1 deck")
        if num_decks * 52 < num_players:
            raise ValueError(
                f"{num_decks} deck(s) = {num_decks * 52} cards is not enough "
                f"for {num_players} players"
            )
        if player_names is not None and len(player_names) != num_players:
            raise ValueError("player_names must have one name per player")

        self.num_players = num_players
        self.num_decks = num_decks
        self.seed = seed
        self.rng = random.Random(seed)
        names = player_names or [f"Player {i}" for i in range(1, num_players + 1)]
        self.players = {
            i: PlayerState(i, names[i - 1]) for i in range(1, num_players + 1)
        }
        self.table: list[Card] = []
        self.events: list[ev.Event] = []
        self.record_events = record_events  # False: skip the event log (fast batch mode)
        self.round = 0
        self.war_count = 0
        self.deepest_war = 0
        self.biggest_pot = 0
        self.winner: int | None = None
        self.is_over = False
        self._started = False

    # ------------------------------------------------------------------ setup

    def start(self) -> None:
        """Shuffle and deal. Called automatically by the first play_round()."""
        if self._started:
            raise RuntimeError("game already started")
        self._started = True
        self._emit(
            ev.GameStarted(
                round=0,
                num_players=self.num_players,
                num_decks=self.num_decks,
                player_names={p.id: p.name for p in self.players.values()},
                seed=self.seed,
            )
        )
        shoe = build_shoe(self.num_decks)
        self.rng.shuffle(shoe)
        # Deal round-robin so every card is in play even when the count
        # doesn't divide evenly (the original GUI silently dropped leftovers).
        for i, card in enumerate(shoe):
            self.players[(i % self.num_players) + 1].deck.append(card)
        self._emit(ev.CardsDealt(round=0, card_counts=self.card_counts()))

    # ------------------------------------------------------------------- play

    def play_round(self) -> list[ev.Event]:
        """Play one full round, resolving any wars. Returns the round's events."""
        if not self._started:
            self.start()
        if self.is_over:
            raise RuntimeError("game is already over")
        mark = len(self.events)
        self.round += 1

        active = [p.id for p in self.players.values() if p.in_game]
        self._emit(ev.RoundStarted(round=self.round, players=active))

        in_round: dict[int, Card] = {}
        for pid in active:
            card = self._draw(pid)
            self.table.append(card)
            in_round[pid] = card
            self._emit(
                ev.CardPlayed(round=self.round, player=pid, card=card, face_up=True)
            )

        winner, via = self._resolve(in_round)

        if winner is not None:
            pot = len(self.table)
            self.biggest_pot = max(self.biggest_pot, pot)
            winning_player = self.players[winner]
            winning_player.reserve.extend(self.table)
            self.table.clear()
            winning_player.wins += 1
            self._emit(
                ev.RoundWon(round=self.round, winner=winner, cards_won=pot, via=via)
            )

        for pid in active:
            player = self.players[pid]
            if player.in_game and player.card_count == 0:
                self._eliminate(pid, "out_of_cards")

        self._emit(ev.RoundEnded(round=self.round, card_counts=self.card_counts()))

        remaining = [p for p in self.players.values() if p.in_game]
        if len(remaining) <= 1:
            self.is_over = True
            self.winner = remaining[0].id if remaining else None
            self._emit(
                ev.GameOver(round=self.round, winner=self.winner, total_rounds=self.round)
            )
        return self.events[mark:]

    def run(self, max_rounds: int | None = None) -> dict:
        """Play rounds until the game ends (or `max_rounds` is reached)."""
        if not self._started:
            self.start()
        while not self.is_over and (max_rounds is None or self.round < max_rounds):
            self.play_round()
        return self.summary()

    # ------------------------------------------------------------- inspection

    def card_counts(self) -> dict[int, int]:
        return {p.id: p.card_count for p in self.players.values() if p.in_game}

    def standings(self) -> list[int]:
        """Player ids ordered best finish first."""
        alive = sorted(
            (p for p in self.players.values() if p.in_game),
            key=lambda p: -p.card_count,
        )
        out = sorted(
            (p for p in self.players.values() if not p.in_game),
            key=lambda p: (-p.round_out, p.id),
        )
        return [p.id for p in alive + out]

    def summary(self) -> dict:
        return {
            "game": "war",
            "num_players": self.num_players,
            "num_decks": self.num_decks,
            "seed": self.seed,
            "completed": self.is_over,
            "rounds": self.round,
            "wars": self.war_count,
            "deepest_war": self.deepest_war,
            "biggest_pot": self.biggest_pot,
            "winner": self.winner,
            "winner_name": self.players[self.winner].name if self.winner else None,
            "standings": self.standings(),
        }

    # -------------------------------------------------------------- internals

    def _emit(self, event: ev.Event) -> None:
        if self.record_events:
            self.events.append(event)

    def _draw(self, pid: int) -> Card:
        player = self.players[pid]
        if not player.deck:
            self.rng.shuffle(player.reserve)
            player.deck.extend(player.reserve)
            player.reserve.clear()
        if not player.deck:
            raise RuntimeError(f"player {pid} has no cards to draw")
        return player.deck.popleft()

    def _eliminate(self, pid: int, reason: str) -> None:
        player = self.players[pid]
        if not player.in_game:
            return
        player.in_game = False
        player.round_out = self.round
        self._emit(ev.PlayerEliminated(round=self.round, player=pid, reason=reason))

    def _tiebreaker_type(self, contenders: list[int]) -> str:
        with_4 = sum(1 for pid in contenders if self.players[pid].card_count >= 4)
        with_1 = sum(1 for pid in contenders if self.players[pid].card_count >= 1)
        if with_4 >= 2:
            return "Default"
        if with_4 == 1:
            return "Forfeit"
        if with_1 >= 2:
            return "Modified"
        if with_1 == 1:
            return "Modified Forfeit"
        return "Draw"

    def _resolve(self, in_round: dict[int, Card]) -> tuple[int | None, str]:
        """Compare played cards, fighting wars until a winner emerges.

        Returns (winning player id, how they won) — or (None, "draw") when
        the war ends with all contenders out of cards and the table split.
        """
        via = "high_card"
        depth = 0
        while True:
            highest = max(card.rank for card in in_round.values())
            contenders = sorted(
                pid for pid, card in in_round.items() if card.rank == highest
            )
            if len(contenders) == 1:
                return contenders[0], via

            depth += 1
            self.war_count += 1
            self.deepest_war = max(self.deepest_war, depth)
            tiebreaker = self._tiebreaker_type(contenders)
            self._emit(
                ev.WarDeclared(
                    round=self.round,
                    players=contenders,
                    rank=highest,
                    depth=depth,
                    tiebreaker=tiebreaker,
                )
            )

            if tiebreaker == "Draw":
                self._split_table(contenders)
                return None, "draw"

            via = "forfeit" if tiebreaker in ("Forfeit", "Modified Forfeit") else "war"
            in_round = {}
            for pid in contenders:
                count = self.players[pid].card_count
                if tiebreaker in ("Default", "Forfeit"):
                    survives = count >= 4
                    to_play = 4 if survives else count
                else:  # Modified, Modified Forfeit: play everything
                    survives = count >= 1
                    to_play = count
                last_card = None
                for i in range(to_play):
                    card = self._draw(pid)
                    self.table.append(card)
                    last_card = card
                    self._emit(
                        ev.CardPlayed(
                            round=self.round,
                            player=pid,
                            card=card,
                            face_up=survives and i == to_play - 1,
                        )
                    )
                if survives:
                    in_round[pid] = last_card
                else:
                    self._eliminate(pid, "insufficient_for_war")

            if len(in_round) == 1:
                return next(iter(in_round)), via
            # Two or more face-up cards remain: loop and compare them.

    def _split_table(self, players: list[int]) -> None:
        """Draw tiebreaker: split the table evenly between tied players."""
        per_player = len(self.table) // len(players)
        returned = {}
        index = 0
        for pid in players:
            self.players[pid].reserve.extend(self.table[index : index + per_player])
            returned[pid] = per_player
            index += per_player
        leftovers = self.table[index:]
        order = list(players)
        self.rng.shuffle(order)
        for pid, card in zip(order, leftovers):
            self.players[pid].reserve.append(card)
            returned[pid] += 1
        self.table.clear()
        self._emit(
            ev.RoundDrawn(round=self.round, players=players, cards_returned=returned)
        )
