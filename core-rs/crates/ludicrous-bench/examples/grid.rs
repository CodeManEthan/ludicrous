//! Rounds-calculator grid. `cargo run --release -p ludicrous-bench --example grid > ../web/rounds-grid.json`
//!
//! For every (players, decks) cell runs SEEDS games natively and records the
//! median, 10th and 90th percentile round counts and the native rounds/s.
//! The page interpolates between cells (see estimateRounds in web/app.js).
//!
//! Each players row is also measured at its edge, the fewest decks that deal
//! every player a card (ceil(players / 52)), when that is not already a
//! lattice deck count: below the lattice a row has no other measured point,
//! and the page reads a row there from its edge, never from other rows.
//! `-- edges` measures and prints only the "edges" object, for adding the
//! edges to an existing grid without re-measuring the lattice.
use std::sync::Mutex;
use std::time::Instant;

use ludicrous_core::war::{Config, WarGame};
use ludicrous_core::Xoshiro256ss;

const PLAYERS: &[u32] = &[2, 4, 8, 16, 32, 64, 128, 256, 512, 1000];
const DECKS: &[u32] = &[1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1000];
const SEEDS: u64 = 50;

fn cell(p: u32, d: u32) -> Option<(u64, u64, u64, f64)> {
    let cfg = Config::new(p, d);
    cfg.validate().ok()?;
    let mut rounds: Vec<u64> = Vec::with_capacity(SEEDS as usize);
    let t0 = Instant::now();
    for seed in 1..=SEEDS {
        let mut g = WarGame::new(cfg, Xoshiro256ss::from_seed(seed), seed);
        g.run();
        rounds.push(g.round() as u64);
    }
    let secs = t0.elapsed().as_secs_f64();
    rounds.sort_unstable();
    let pct = |q: f64| rounds[((rounds.len() - 1) as f64 * q).round() as usize];
    let total: u64 = rounds.iter().sum();
    Some((pct(0.5), pct(0.1), pct(0.9), total as f64 / secs))
}

/// The fewest decks that deal every player a card.
fn edge(p: u32) -> u32 {
    p.div_ceil(52)
}

/// Rows whose edge is not a lattice deck count, with that edge.
fn edge_jobs() -> Vec<(u32, u32)> {
    PLAYERS
        .iter()
        .map(|&p| (p, edge(p)))
        .filter(|(_, d)| !DECKS.contains(d))
        .collect()
}

fn main() {
    let edges_only = std::env::args().any(|a| a == "edges");
    let mut jobs: Vec<(u32, u32)> = Vec::new();
    if !edges_only {
        for &p in PLAYERS {
            for &d in DECKS {
                jobs.push((p, d));
            }
        }
    }
    jobs.extend(edge_jobs());
    // Biggest cells first so the tail of the run is short ones.
    jobs.sort_by_key(|&(p, d)| std::cmp::Reverse((d as u64) * (d as u64) + p as u64));
    let next = Mutex::new(0usize);
    let out: Mutex<Vec<(u32, u32, (u64, u64, u64, f64))>> = Mutex::new(Vec::new());
    let threads = std::thread::available_parallelism().map(|n| n.get()).unwrap_or(4);
    std::thread::scope(|s| {
        for _ in 0..threads {
            s.spawn(|| loop {
                let i = {
                    let mut n = next.lock().unwrap();
                    let i = *n;
                    *n += 1;
                    i
                };
                if i >= jobs.len() {
                    break;
                }
                let (p, d) = jobs[i];
                if let Some(c) = cell(p, d) {
                    eprintln!("{}p{}d median={} p10={} p90={} rps={:.0}", p, d, c.0, c.1, c.2, c.3);
                    out.lock().unwrap().push((p, d, c));
                }
            });
        }
    });
    let mut cells = out.into_inner().unwrap();
    cells.sort_by_key(|c| (c.0, c.1));
    let edge_set = edge_jobs();
    let (edges, cells): (Vec<_>, Vec<_>) =
        cells.into_iter().partition(|c| edge_set.contains(&(c.0, c.1)));
    let edges_json = edges
        .iter()
        .map(|(p, d, c)| format!("    \"{}\": [{}, {}, {}, {}, {}]", p, d, c.0, c.1, c.2, c.3.round() as u64))
        .collect::<Vec<_>>()
        .join(",\n");
    if edges_only {
        println!("  \"edges\": {{\n{}\n  }}", edges_json);
        return;
    }
    let list = |v: &[u32]| v.iter().map(|x| x.to_string()).collect::<Vec<_>>().join(",");
    println!("{{");
    println!("  \"players\": [{}],", list(PLAYERS));
    println!("  \"decks\": [{}],", list(DECKS));
    println!("  \"seeds\": {},", SEEDS);
    println!("  \"generated\": \"{}\",", "2026-09-04");
    println!("  \"wasm_speed_factor\": 0.5,");
    println!("  \"edges\": {{\n{}\n  }},", edges_json);
    println!("  \"cells\": {{");
    for (i, (p, d, c)) in cells.iter().enumerate() {
        println!(
            "    \"{}:{}\": [{}, {}, {}, {}]{}",
            p, d, c.0, c.1, c.2, c.3.round() as u64,
            if i + 1 < cells.len() { "," } else { "" }
        );
    }
    println!("  }}");
    println!("}}");
}
