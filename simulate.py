#!/usr/bin/env python3
"""Simulate a full game of War from the command line — no GUI required.

Examples:
    python3 simulate.py                          # 4 players, 1 deck
    python3 simulate.py -p 100 -d 50 --seed 42   # big reproducible game
    python3 simulate.py -p 6 -d 3 --json game.json   # save a recording
"""
import argparse
import json
import random
import time

from engine import WarGame, run_batch, summarize_batch
from engine import events as ev
from random_names import random_300_first_names


def build_names(num_players: int, seed: int) -> list[str]:
    pool = random_300_first_names()
    rng = random.Random(seed)
    rng.shuffle(pool)
    return [
        pool[i % len(pool)] if i < len(pool) else f"{pool[i % len(pool)]} {i // len(pool) + 1}"
        for i in range(num_players)
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-p", "--players", type=int, default=4, help="number of players (default 4)")
    parser.add_argument("-d", "--decks", type=int, default=1, help="number of 52-card decks (default 1)")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for a reproducible game")
    parser.add_argument("--max-rounds", type=int, default=1_000_000, help="safety cap on rounds")
    parser.add_argument("--random-names", action="store_true", help="use random player names")
    parser.add_argument("--verbose", action="store_true", help="print every round")
    parser.add_argument("--json", metavar="PATH", help="write the full game recording (events) as JSON")
    parser.add_argument("--batch", type=int, metavar="N", help="simulate N games in parallel and print statistics")
    args = parser.parse_args()

    seed = args.seed if args.seed is not None else random.randrange(1_000_000_000)

    if args.batch:
        run_batch_cli(args, seed)
        return
    names = build_names(args.players, seed) if args.random_names else None

    game = WarGame(args.players, args.decks, player_names=names, seed=seed)
    total_cards = args.decks * 52
    print(f"War — {args.players} players, {args.decks} deck(s) ({total_cards:,} cards), seed {seed}")

    start_time = time.perf_counter()
    game.start()
    while not game.is_over and game.round < args.max_rounds:
        round_events = game.play_round()
        if args.verbose:
            for event in round_events:
                if isinstance(event, ev.RoundWon):
                    name = game.players[event.winner].name
                    war = " (war)" if event.via == "war" else " (forfeit)" if event.via == "forfeit" else ""
                    print(f"  Round {event.round:>6}: {name} wins {event.cards_won} cards{war}")
                elif isinstance(event, ev.RoundDrawn):
                    print(f"  Round {event.round:>6}: draw — table split")
                elif isinstance(event, ev.PlayerEliminated):
                    print(f"  Round {event.round:>6}: {game.players[event.player].name} is out")
    elapsed = time.perf_counter() - start_time

    if not game.is_over:
        print(f"Stopped after {game.round:,} rounds (max-rounds cap) — no winner yet.")
    else:
        winner = game.players[game.winner]
        rate = game.round / elapsed if elapsed > 0 else 0
        print(f"Winner: {winner.name} after {game.round:,} rounds  ({elapsed:.2f}s, {rate:,.0f} rounds/s)")

    biggest_pot = max((e.cards_won for e in game.events if isinstance(e, ev.RoundWon)), default=0)
    deepest_war = max((e.depth for e in game.events if isinstance(e, ev.WarDeclared)), default=0)
    print(f"Wars: {game.war_count:,}  |  deepest war: {deepest_war}  |  biggest pot: {biggest_pot} cards")

    print("Top finishers:")
    for place, pid in enumerate(game.standings()[:5], start=1):
        player = game.players[pid]
        note = "winner" if pid == game.winner else f"out round {player.round_out:,}"
        print(f"  {place}. {player.name}  ({note})")

    if args.json:
        recording = {
            "summary": game.summary(),
            "events": [event.to_dict() for event in game.events],
        }
        with open(args.json, "w") as f:
            json.dump(recording, f)
        print(f"Recording written to {args.json} ({len(game.events):,} events)")


def run_batch_cli(args, base_seed):
    print(f"War batch — {args.batch:,} games of {args.players} players, "
          f"{args.decks} deck(s), seeds {base_seed}..{base_seed + args.batch - 1}")
    start_time = time.perf_counter()
    rows = run_batch(args.players, args.decks, args.batch,
                     base_seed=base_seed, max_rounds=args.max_rounds)
    elapsed = time.perf_counter() - start_time
    agg = summarize_batch(rows)
    r = agg["rounds"]
    print(f"Completed {agg['completed']:,}/{agg['games']:,} games in {elapsed:.2f}s "
          f"({agg['games'] / elapsed:,.0f} games/s)")
    print(f"Rounds: mean {r['mean']:,.0f}  median {r['median']:,.0f}  "
          f"stdev {r['stdev']:,.0f}  range {r['min']:,}-{r['max']:,}")
    print(f"Wars/game: {agg['mean_wars']:,.1f}  |  deepest war: {agg['deepest_war']}  "
          f"|  biggest pot: {agg['biggest_pot']} cards")
    print("Wins by seat: " + "  ".join(
        f"{seat}:{wins}" for seat, wins in sorted(agg["wins_by_seat"].items())))
    print("Shortest games: " + "  ".join(
        f"{g['rounds']:,} (seed {g['seed']})" for g in agg["shortest"][:3]))
    print("Longest games:  " + "  ".join(
        f"{g['rounds']:,} (seed {g['seed']})" for g in agg["longest"][:3]))
    if args.json:
        with open(args.json, "w") as f:
            json.dump({"config": vars(args), "aggregate": agg, "games": rows}, f)
        print(f"Batch results written to {args.json}")


if __name__ == "__main__":
    main()
