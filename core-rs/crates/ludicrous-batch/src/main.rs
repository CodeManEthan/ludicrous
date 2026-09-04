//! `lud-batch`: the native War batch runner behind `server.py`.
//!
//!     lud-batch --players P --decks D --games N --seed S [--max-rounds M] [--threads T]
//!
//! Writes newline-delimited JSON to stdout: throttled
//! `{"progress": {"done", "total"}}` lines while the games run, then exactly
//! one `{"result": ...}` line in the shape `engine/batch.py::summarize_batch`
//! plus the per-game rows -- so `run_batch_api` returns the same JSON whether
//! the batch ran here or in the Python pool. Errors are one `{"error": ...}`
//! line and a non-zero exit.
//!
//! Seeds are the v2 namespace (xoshiro256**), the same as the browser engine,
//! so a row's seed replays as the same game in the single-game view.
//! `--max-rounds 0` means no cap.
use std::io::Write;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use ludicrous_core::war::{Config, WarGame};
use ludicrous_core::Xoshiro256ss;

#[derive(Clone, Copy)]
struct Row {
    seed: u64,
    completed: bool,
    rounds: u32,
    winner: Option<u32>,
    wars: u64,
    deepest_war: u32,
    biggest_pot: u32,
}

fn row_json(r: &Row) -> String {
    format!(
        "{{\"seed\": {}, \"completed\": {}, \"rounds\": {}, \"winner\": {}, \"wars\": {}, \
         \"deepest_war\": {}, \"biggest_pot\": {}}}",
        r.seed,
        r.completed,
        r.rounds,
        r.winner.map(|w| w.to_string()).unwrap_or_else(|| "null".into()),
        r.wars,
        r.deepest_war,
        r.biggest_pot
    )
}

fn arg(args: &[String], name: &str) -> Option<String> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1).cloned())
}

fn fail(msg: &str) -> ! {
    println!("{{\"error\": {}}}", json_str(msg));
    std::process::exit(2);
}

fn json_str(s: &str) -> String {
    let mut out = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let num = |name: &str, default: Option<u64>| -> u64 {
        match arg(&args, name) {
            Some(v) => v.parse().unwrap_or_else(|_| fail(&format!("{name} must be an integer"))),
            None => default.unwrap_or_else(|| fail(&format!("{name} is required"))),
        }
    };
    let players = num("--players", None) as u32;
    let decks = num("--decks", None) as u32;
    let games = num("--games", None);
    let base_seed = num("--seed", Some(0));
    let max_rounds = num("--max-rounds", Some(0));
    let threads = num(
        "--threads",
        Some(std::thread::available_parallelism().map(|n| n.get() as u64).unwrap_or(4)),
    )
    .max(1) as usize;
    if games < 1 {
        fail("--games must be at least 1");
    }

    let cfg = Config {
        num_players: players,
        num_decks: decks,
        max_rounds: if max_rounds == 0 { u64::MAX } else { max_rounds },
    };
    if let Err(e) = cfg.validate() {
        fail(e);
    }

    let started = Instant::now();
    let next = AtomicU64::new(0);
    let done = AtomicU64::new(0);
    let rows: Mutex<Vec<Row>> = Mutex::new(Vec::with_capacity(games as usize));
    let stdout = Mutex::new(std::io::stdout());

    std::thread::scope(|s| {
        for _ in 0..threads {
            s.spawn(|| loop {
                let i = next.fetch_add(1, Ordering::Relaxed);
                if i >= games {
                    break;
                }
                let seed = base_seed + i;
                let mut g = WarGame::new(cfg, Xoshiro256ss::from_seed(seed), seed);
                g.run();
                let sm = g.summary();
                rows.lock().unwrap().push(Row {
                    seed,
                    completed: sm.completed,
                    rounds: sm.rounds,
                    winner: sm.winner,
                    wars: sm.wars,
                    deepest_war: sm.deepest_war,
                    biggest_pot: sm.biggest_pot,
                });
                done.fetch_add(1, Ordering::Relaxed);
            });
        }
        // Progress reporter: one line per ~100 ms while work is in flight. If
        // the reader has gone away the write fails and we stop the batch --
        // nobody is waiting for the result.
        let mut last = 0;
        loop {
            std::thread::sleep(Duration::from_millis(100));
            let d = done.load(Ordering::Relaxed);
            if d != last {
                last = d;
                let mut out = stdout.lock().unwrap();
                if writeln!(out, "{{\"progress\": {{\"done\": {d}, \"total\": {games}}}}}")
                    .and_then(|_| out.flush())
                    .is_err()
                {
                    std::process::exit(3);
                }
            }
            if d >= games {
                break;
            }
        }
    });

    let mut rows = rows.into_inner().unwrap();
    rows.sort_by_key(|r| r.seed);
    let elapsed = started.elapsed().as_secs_f64();

    // ---- summarize_batch, faithfully
    let finished: Vec<&Row> = rows.iter().filter(|r| r.completed).collect();
    let source: Vec<&Row> = if finished.is_empty() { rows.iter().collect() } else { finished.clone() };
    let mut rs: Vec<f64> = source.iter().map(|r| r.rounds as f64).collect();
    rs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = rs.len() as f64;
    let mean = rs.iter().sum::<f64>() / n;
    let median = if rs.len() % 2 == 1 {
        rs[rs.len() / 2]
    } else {
        (rs[rs.len() / 2 - 1] + rs[rs.len() / 2]) / 2.0
    };
    let stdev = if rs.len() > 1 {
        (rs.iter().map(|x| (x - mean) * (x - mean)).sum::<f64>() / (n - 1.0)).sqrt()
    } else {
        0.0
    };
    let mean_wars = source.iter().map(|r| r.wars as f64).sum::<f64>() / n;
    let deepest = rows.iter().map(|r| r.deepest_war).max().unwrap_or(0);
    let biggest = rows.iter().map(|r| r.biggest_pot).max().unwrap_or(0);
    let mut wins: Vec<(u32, u64)> = Vec::new();
    for r in &rows {
        if let Some(w) = r.winner {
            match wins.iter_mut().find(|(seat, _)| *seat == w) {
                Some(e) => e.1 += 1,
                None => wins.push((w, 1)),
            }
        }
    }
    let mut by_rounds: Vec<&Row> = rows.iter().collect();
    by_rounds.sort_by_key(|r| (r.rounds, r.seed));
    let shortest: Vec<String> = by_rounds.iter().take(5).map(|r| row_json(r)).collect();
    let longest: Vec<String> = by_rounds.iter().rev().take(5).map(|r| row_json(r)).collect();
    let wins_json = wins
        .iter()
        .map(|(seat, c)| format!("\"{seat}\": {c}"))
        .collect::<Vec<_>>()
        .join(", ");

    let result = format!(
        "{{\"result\": {{\"game\": \"war\", \"engine\": \"v2\", \"config\": {{\"players\": {players}, \
         \"decks\": {decks}, \"games\": {games}, \"base_seed\": {base_seed}, \"total_cards\": {}, \
         \"max_rounds\": {max_rounds}}}, \"elapsed\": {elapsed:.6}, \"threads\": {threads}, \
         \"aggregate\": {{\"games\": {}, \"completed\": {}, \"unfinished\": {}, \
         \"rounds\": {{\"min\": {}, \"max\": {}, \"mean\": {mean:.3}, \"median\": {median:.1}, \"stdev\": {stdev:.3}}}, \
         \"mean_wars\": {mean_wars:.3}, \"deepest_war\": {deepest}, \"biggest_pot\": {biggest}, \
         \"wins_by_seat\": {{{wins_json}}}, \"shortest\": [{}], \"longest\": [{}]}}, \
         \"games\": [{}]}}}}",
        decks * 52,
        rows.len(),
        finished.len(),
        rows.len() - finished.len(),
        rs.first().map(|x| *x as u64).unwrap_or(0),
        rs.last().map(|x| *x as u64).unwrap_or(0),
        shortest.join(", "),
        longest.join(", "),
        rows.iter().map(row_json).collect::<Vec<_>>().join(", "),
    );
    let mut out = stdout.lock().unwrap();
    let _ = writeln!(out, "{result}");
    let _ = out.flush();
}
