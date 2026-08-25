//! Native benchmark harness. `cargo run --release -p ludicrous-bench`.
//!
//! Every number the prototype report quotes comes out of here, printed as
//! `key<TAB>value` lines so a script can scrape it.

use std::hint::black_box;
use std::time::Instant;

use ludicrous_core::events::{CountingSink, JsonSink, NullSink};
use ludicrous_core::war::{Config, WarGame};
use ludicrous_core::Xoshiro256ss;

fn cfg(p: u32, d: u32) -> Config {
    Config::new(p, d)
}

/// Run games from `seed0` until at least `min_secs` have passed. Returns
/// (games, rounds, elapsed seconds).
fn throughput(c: Config, seed0: u64, min_secs: f64, min_games: u64) -> (u64, u64, f64) {
    let t0 = Instant::now();
    let mut games = 0u64;
    let mut rounds = 0u64;
    loop {
        let seed = seed0 + games;
        let mut g = WarGame::new(c, Xoshiro256ss::from_seed(seed), seed);
        g.run();
        rounds += g.round() as u64;
        black_box(g.summary().winner);
        games += 1;
        let el = t0.elapsed().as_secs_f64();
        if el >= min_secs && games >= min_games {
            return (games, rounds, el);
        }
    }
}

fn bench_single() {
    println!("## native single-thread, events off");
    for &(p, d) in &[(6u32, 3u32), (26, 13), (100, 50)] {
        let (games, rounds, el) = throughput(cfg(p, d), 1, 2.0, 3);
        println!(
            "native.rounds_per_sec.{}p{}d\t{:.0}\tgames={} rounds={} secs={:.3} mean_rounds={:.0}",
            p,
            d,
            rounds as f64 / el,
            games,
            rounds,
            el,
            rounds as f64 / games as f64
        );
        println!("native.games_per_sec.{}p{}d\t{:.1}", p, d, games as f64 / el);
    }
}

fn bench_one_big_game() {
    println!("## one full 100p/50d game");
    let mut best = f64::MAX;
    let mut worst: f64 = 0.0;
    let mut total = 0.0;
    let mut rounds_seen = 0u64;
    let n = 20;
    for seed in 1..=n {
        let t0 = Instant::now();
        let mut g = WarGame::new(cfg(100, 50), Xoshiro256ss::from_seed(seed), seed);
        g.run();
        let el = t0.elapsed().as_secs_f64();
        rounds_seen += g.round() as u64;
        black_box(g.summary().winner);
        total += el;
        if el < best {
            best = el;
        }
        if el > worst {
            worst = el;
        }
    }
    println!(
        "native.one_game_100p50d_ms.mean\t{:.2}\tmin={:.2} max={:.2} mean_rounds={:.0}",
        total / n as f64 * 1e3,
        best * 1e3,
        worst * 1e3,
        rounds_seen as f64 / n as f64
    );
}

fn bench_events() {
    println!("## with events");
    // A 100p/50d game runs ~700k rounds emitting >100 events each; the full
    // recording is gigabytes. Cap the big config so the two rows compare.
    for &(p, d, cap) in &[(6u32, 3u32, u64::MAX), (100, 50, 2_000)] {
        let c = Config {
            num_players: p,
            num_decks: d,
            max_rounds: cap,
        };
        // Counting sink: the cost of constructing and dispatching events,
        // without any formatting.
        let t0 = Instant::now();
        let mut games = 0u64;
        let mut rounds = 0u64;
        let mut evs = 0u64;
        while t0.elapsed().as_secs_f64() < 2.0 || games < 1 {
            let seed = 1 + games;
            let mut g = WarGame::with_sink(
                c,
                Xoshiro256ss::from_seed(seed),
                seed,
                CountingSink::default(),
            );
            g.run();
            rounds += g.round() as u64;
            evs += g.sink.count;
            games += 1;
        }
        let el = t0.elapsed().as_secs_f64();
        println!(
            "native.rounds_per_sec.{}p{}d.events_counted\t{:.0}\tevents_per_round={:.1}",
            p,
            d,
            rounds as f64 / el,
            evs as f64 / rounds as f64
        );

        // JSON sink: full NDJSON recording written to a String.
        let t0 = Instant::now();
        let mut games = 0u64;
        let mut rounds = 0u64;
        let mut bytes = 0u64;
        while t0.elapsed().as_secs_f64() < 2.0 || games < 1 {
            let seed = 1 + games;
            let mut g = WarGame::with_sink(
                c,
                Xoshiro256ss::from_seed(seed),
                seed,
                JsonSink::new(Vec::new()),
            );
            g.run();
            rounds += g.round() as u64;
            bytes += g.sink.out.len() as u64;
            games += 1;
        }
        let el = t0.elapsed().as_secs_f64();
        println!(
            "native.rounds_per_sec.{}p{}d.events_json\t{:.0}\tjson_bytes_per_round={:.0}{}",
            p,
            d,
            rounds as f64 / el,
            bytes as f64 / rounds as f64,
            if cap == u64::MAX {
                String::new()
            } else {
                format!(" (capped at {} rounds/game)", cap)
            }
        );
    }
}

fn bench_checkpoint() {
    println!("## checkpoint");
    for &(p, d) in &[(6u32, 3u32), (26, 13), (100, 50)] {
        let c = cfg(p, d);
        let mut g: WarGame<Xoshiro256ss, NullSink> =
            WarGame::new(c, Xoshiro256ss::from_seed(7), 7);
        g.advance(500);
        let snap = g.save();
        println!(
            "checkpoint.bytes.{}p{}d\t{}\tcards={} players={}",
            p,
            d,
            snap.len(),
            d * 52,
            p
        );

        let iters = 200_000u32.min(20_000_000 / (snap.len() as u32).max(1));
        let t0 = Instant::now();
        for _ in 0..iters {
            black_box(g.save().len());
        }
        let save_ns = t0.elapsed().as_secs_f64() / iters as f64 * 1e9;

        let t0 = Instant::now();
        for _ in 0..iters {
            let g2 = WarGame::<Xoshiro256ss, NullSink>::restore(&snap, NullSink).unwrap();
            black_box(g2.round());
        }
        let restore_ns = t0.elapsed().as_secs_f64() / iters as f64 * 1e9;
        println!(
            "checkpoint.save_us.{}p{}d\t{:.3}\trestore_us={:.3}",
            p,
            d,
            save_ns / 1e3,
            restore_ns / 1e3
        );
    }
}

fn bench_seek() {
    println!("## seek (restore + resim K rounds), native");
    // 6p/3d games average ~2,100 rounds, so a K=5000 seek there runs to the
    // end of the game rather than 5,000 rounds -- 26p/13d (~38k rounds) and
    // 100p/50d (~680k) are the honest worst cases.
    for &(p, d, iters) in &[(6u32, 3u32, 2000u32), (26, 13, 500), (100, 50, 100)] {
        let c = cfg(p, d);
        let mut g: WarGame<Xoshiro256ss, NullSink> =
            WarGame::new(c, Xoshiro256ss::from_seed(11), 11);
        g.advance(50);
        let snap = g.save();
        for &k in &[1000u32, 5000] {
            let t0 = Instant::now();
            let mut actual = 0u64;
            for _ in 0..iters {
                let mut g2 = WarGame::<Xoshiro256ss, NullSink>::restore(&snap, NullSink).unwrap();
                actual += g2.advance(k) as u64;
                black_box(g2.round());
            }
            let el = t0.elapsed().as_secs_f64() / iters as f64;
            println!(
                "native.seek_ms.{}p{}d.k{}\t{:.4}\trounds_actually_played={}",
                p,
                d,
                k,
                el * 1e3,
                actual / iters as u64
            );
        }
    }
}

fn bench_batch() {
    println!("## parallel batch, 5000 games of 6p/3d");
    let total_games = 5000u64;
    let c = cfg(6, 3);

    // Single thread first, as the honest baseline for the speedup number.
    let t0 = Instant::now();
    let mut rounds = 0u64;
    for s in 0..total_games {
        let mut g = WarGame::new(c, Xoshiro256ss::from_seed(s), s);
        g.run();
        rounds += g.round() as u64;
    }
    let el1 = t0.elapsed().as_secs_f64();
    println!(
        "batch.1thread.games_per_sec\t{:.0}\tsecs={:.4} rounds={}",
        total_games as f64 / el1,
        el1,
        rounds
    );

    let cores = std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(4);
    for &threads in &[cores / 2, cores] {
        if threads == 0 {
            continue;
        }
        let t0 = Instant::now();
        let per = total_games.div_ceil(threads as u64);
        let mut handles = Vec::new();
        for t in 0..threads as u64 {
            let lo = t * per;
            let hi = ((t + 1) * per).min(total_games);
            handles.push(std::thread::spawn(move || {
                let mut r = 0u64;
                let mut w = 0u64;
                for s in lo..hi {
                    let mut g = WarGame::new(c, Xoshiro256ss::from_seed(s), s);
                    g.run();
                    r += g.round() as u64;
                    w += g.summary().winner.unwrap_or(0) as u64;
                }
                (r, w)
            }));
        }
        let mut r = 0u64;
        for h in handles {
            let (rr, ww) = h.join().unwrap();
            r += rr;
            black_box(ww);
        }
        let el = t0.elapsed().as_secs_f64();
        println!(
            "batch.{}threads.games_per_sec\t{:.0}\tsecs={:.4} rounds={} speedup_vs_1t={:.2}x",
            threads,
            total_games as f64 / el,
            el,
            r,
            el1 / el
        );
    }
}

/// Print one canonical line per game for a fixed grid, so the wasm build can
/// be checked against native on identical seeds.
fn dump() {
    for &(p, d) in &[
        (2u32, 1u32),
        (4, 1),
        (6, 3),
        (13, 2),
        (26, 13),
        (60, 2),
        (100, 50),
    ] {
        for seed in 0..8u64 {
            let mut g = WarGame::new(cfg(p, d), Xoshiro256ss::from_seed(seed), seed);
            g.run();
            let s = g.summary();
            let standings: Vec<String> = s.standings.iter().map(|x| x.to_string()).collect();
            println!(
                "{} {} {} {} {} {} {} {} {} {}",
                p,
                d,
                seed,
                s.rounds,
                s.wars,
                s.deepest_war,
                s.biggest_pot,
                s.winner.unwrap_or(0),
                s.completed,
                standings.join(",")
            );
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let only = args.get(1).map(|s| s.as_str()).unwrap_or("all");
    if only == "dump" {
        dump();
        return;
    }
    println!("cores\t{}", std::thread::available_parallelism().map(|n| n.get()).unwrap_or(0));
    if only == "all" || only == "single" {
        bench_single();
    }
    if only == "all" || only == "onegame" {
        bench_one_big_game();
    }
    if only == "all" || only == "events" {
        bench_events();
    }
    if only == "all" || only == "checkpoint" {
        bench_checkpoint();
    }
    if only == "all" || only == "seek" {
        bench_seek();
    }
    if only == "all" || only == "batch" {
        bench_batch();
    }
}
