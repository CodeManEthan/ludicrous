#!/usr/bin/env python3
"""Ludicrous CLI — simulate games (War, Blackjack) from the command line.

Examples:
    python3 simulate.py                          # 4 players, 1 deck of War
    python3 simulate.py -p 100 -d 50 --seed 42   # big reproducible game
    python3 simulate.py -p 6 -d 3 --json game.json   # save a recording
    python3 simulate.py --game blackjack -p 4 --strategies basic,never-bust
"""
import argparse
import json
import random
import time

from engine import (
    STRATEGIES,
    BlackjackGame,
    WarGame,
    run_batch,
    run_blackjack_batch,
    summarize_batch,
    summarize_blackjack_batch,
)
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
    parser.add_argument("--game", choices=["war", "blackjack"], default="war")
    parser.add_argument("-p", "--players", type=int, default=4, help="players / blackjack seats (default 4)")
    parser.add_argument("-d", "--decks", type=int, default=None, help="52-card decks (default: war 1, blackjack 6)")
    parser.add_argument("--rounds", type=int, default=100, help="blackjack: rounds per session (default 100)")
    parser.add_argument("--strategies", default="basic",
                        help=f"blackjack: comma-separated, assigned round-robin ({', '.join(STRATEGIES)})")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for a reproducible game")
    parser.add_argument("--max-rounds", type=int, default=1_000_000, help="safety cap on rounds")
    parser.add_argument("--random-names", action="store_true", help="use random player names")
    parser.add_argument("--verbose", action="store_true", help="print every round")
    parser.add_argument("--json", metavar="PATH", help="write the full game recording (events) as JSON")
    parser.add_argument("--batch", type=int, metavar="N", help="simulate N games in parallel and print statistics")
    args = parser.parse_args()

    seed = args.seed if args.seed is not None else random.randrange(1_000_000_000)
    if args.decks is None:
        args.decks = 6 if args.game == "blackjack" else 1

    if args.game == "blackjack":
        if args.batch:
            run_blackjack_batch_cli(args, seed)
        else:
            run_blackjack_cli(args, seed)
        return

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


def run_blackjack_cli(args, seed):
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    game = BlackjackGame(args.players, args.decks, args.rounds,
                         strategies=strategies, seed=seed)
    print(f"Blackjack — {args.players} seat(s), {args.decks} deck(s), "
          f"{args.rounds} rounds, seed {seed}")
    start_time = time.perf_counter()
    summary = game.run()
    elapsed = time.perf_counter() - start_time
    for seat in summary["seats"].values():
        print(f"  {seat['name']:<8} {seat['strategy']:<14} "
              f"{seat['bankroll']:>+8.1f} units  "
              f"({seat['wins']}W {seat['losses']}L {seat['pushes']}P, "
              f"{seat['blackjacks']} BJ)")
    print("Per strategy:")
    for name, entry in sorted(summary["per_strategy"].items(), key=lambda kv: -kv[1]["ev"]):
        print(f"  {name:<14} {entry['net']:>+8.1f} units over {entry['hands']:,} hands "
              f"(EV {entry['ev']:+.2%})")
    print(f"Winner: {summary['winner_name']}  ({elapsed:.2f}s)")
    if args.json:
        with open(args.json, "w") as f:
            json.dump({"summary": summary,
                       "events": [e.to_dict() for e in game.events]}, f)
        print(f"Recording written to {args.json} ({len(game.events):,} events)")


def run_blackjack_batch_cli(args, base_seed):
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    print(f"Blackjack batch — {args.batch:,} sessions of {args.players} seat(s) x "
          f"{args.rounds} rounds, {args.decks} deck(s), "
          f"seeds {base_seed}..{base_seed + args.batch - 1}")
    start_time = time.perf_counter()
    rows = run_blackjack_batch(args.players, args.decks, args.rounds, args.batch,
                               strategies, base_seed=base_seed)
    elapsed = time.perf_counter() - start_time
    agg = summarize_blackjack_batch(rows)
    print(f"{agg['hands']:,} hands in {elapsed:.2f}s "
          f"({agg['hands'] / elapsed:,.0f} hands/s)  |  "
          f"overall EV {agg['ev']:+.2%}")
    print(f"{'strategy':<14} {'hands':>10} {'net units':>10} {'EV/hand':>9}")
    for name, entry in sorted(agg["per_strategy"].items(), key=lambda kv: -kv[1]["ev"]):
        print(f"{name:<14} {entry['hands']:>10,} {entry['net']:>10,.0f} {entry['ev']:>8.2%}")
    s = agg["session_net"]
    print(f"Session net: mean {s['mean']:+.1f} ±{s['stdev']:.1f}  "
          f"range {s['min']:+.1f}..{s['max']:+.1f}")
    print("Best sessions:  " + "  ".join(f"{g['net']:+.1f} (seed {g['seed']})" for g in agg["best"][:3]))
    print("Worst sessions: " + "  ".join(f"{g['net']:+.1f} (seed {g['seed']})" for g in agg["worst"][:3]))
    if args.json:
        with open(args.json, "w") as f:
            json.dump({"aggregate": agg, "games": rows}, f)
        print(f"Batch results written to {args.json}")


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
    if agg["unfinished"]:
        print(f"WARNING: {agg['unfinished']:,} game(s) hit the {args.max_rounds:,}-round cap "
              f"and were stopped unfinished — excluded from the statistics below. "
              f"Raise --max-rounds to let them finish.")
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
