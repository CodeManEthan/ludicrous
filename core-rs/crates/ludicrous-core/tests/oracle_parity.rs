//! Rule parity with `engine/war.py`.
//!
//! The shipping engine will use a different RNG than Python did, so the
//! rules can't be checked by "same seed, same game" once v2 lands. Instead
//! the port carries a test-only CPython `random.Random` (see
//! `src/mt19937.rs`); with that plugged in, the Rust engine and the Python
//! engine must agree on every game, field for field.
//!
//! Fixtures come from `oracle/gen_oracle.py`. Regenerate them if the Python
//! rules ever change:
//!
//! ```text
//! python3 core-rs/oracle/gen_oracle.py
//! ```

#![cfg(feature = "cpython-rng")]

use std::collections::BTreeMap;

use ludicrous_core::events::{Event, EventSink};
use ludicrous_core::mt19937::CPythonRng;
use ludicrous_core::war::{Config, WarGame};

/// The oracle rows are flat JSON: integers, booleans, null, and integer
/// arrays. A 40-line reader beats pulling serde into the core crate.
struct Row {
    ints: BTreeMap<String, i64>,
    lists: BTreeMap<String, Vec<i64>>,
    nulls: Vec<String>,
    bools: BTreeMap<String, bool>,
}

impl Row {
    fn i(&self, k: &str) -> i64 {
        *self
            .ints
            .get(k)
            .unwrap_or_else(|| panic!("oracle row missing int {}", k))
    }
    fn l(&self, k: &str) -> &[i64] {
        self.lists
            .get(k)
            .unwrap_or_else(|| panic!("oracle row missing list {}", k))
    }
    fn b(&self, k: &str) -> bool {
        *self
            .bools
            .get(k)
            .unwrap_or_else(|| panic!("oracle row missing bool {}", k))
    }
    fn is_null(&self, k: &str) -> bool {
        self.nulls.iter().any(|n| n == k)
    }
}

fn parse_row(line: &str) -> Row {
    let mut row = Row {
        ints: BTreeMap::new(),
        lists: BTreeMap::new(),
        nulls: Vec::new(),
        bools: BTreeMap::new(),
    };
    let body = line.trim().trim_start_matches('{').trim_end_matches('}');
    let bytes = body.as_bytes();
    let mut i = 0usize;
    while i < bytes.len() {
        while i < bytes.len() && bytes[i] != b'"' {
            i += 1;
        }
        if i >= bytes.len() {
            break;
        }
        i += 1;
        let ks = i;
        while bytes[i] != b'"' {
            i += 1;
        }
        let key = body[ks..i].to_string();
        i += 1;
        while bytes[i] != b':' {
            i += 1;
        }
        i += 1;
        while bytes[i] == b' ' {
            i += 1;
        }
        if bytes[i] == b'[' {
            i += 1;
            let vs = i;
            while bytes[i] != b']' {
                i += 1;
            }
            let inner = &body[vs..i];
            i += 1;
            let vals: Vec<i64> = if inner.trim().is_empty() {
                Vec::new()
            } else {
                inner
                    .split(',')
                    .map(|t| t.trim().parse::<i64>().unwrap())
                    .collect()
            };
            row.lists.insert(key, vals);
        } else {
            let vs = i;
            while i < bytes.len() && bytes[i] != b',' {
                i += 1;
            }
            let tok = body[vs..i].trim();
            match tok {
                "null" => row.nulls.push(key),
                "true" => {
                    row.bools.insert(key, true);
                }
                "false" => {
                    row.bools.insert(key, false);
                }
                _ => {
                    row.ints.insert(key, tok.parse::<i64>().unwrap());
                }
            }
        }
    }
    row
}

/// Counts which of the five tiebreakers each run actually exercised, so the
/// suite can prove it covered the exotic ones rather than assuming it did.
#[derive(Default)]
struct TiebreakerCensus {
    counts: BTreeMap<&'static str, u64>,
}

impl EventSink for TiebreakerCensus {
    const ENABLED: bool = true;
    fn emit(&mut self, e: Event<'_>) {
        if let Event::WarDeclared { tiebreaker, .. } = e {
            *self.counts.entry(tiebreaker).or_insert(0) += 1;
        }
    }
}

fn compare_fixture(label: &str, data: &str, min_games: usize) -> BTreeMap<&'static str, u64> {
    let mut checked = 0usize;
    let mut census: BTreeMap<&'static str, u64> = BTreeMap::new();
    let mut draws = 0u64;

    for line in data.lines().filter(|l| !l.trim().is_empty()) {
        let row = parse_row(line);
        let np = row.i("num_players") as u32;
        let nd = row.i("num_decks") as u32;
        let seed = row.i("seed") as u64;
        let cfg = Config {
            num_players: np,
            num_decks: nd,
            max_rounds: row.i("max_rounds") as u64,
        };
        let mut g = WarGame::with_sink(
            cfg,
            CPythonRng::seeded(seed),
            seed,
            TiebreakerCensus::default(),
        );
        g.run();
        let s = g.summary();
        let where_ = format!(
            "[{}] {}p/{}d seed {} cap {}",
            label,
            np,
            nd,
            seed,
            row.i("max_rounds")
        );

        assert_eq!(s.rounds as i64, row.i("rounds"), "rounds, {}", where_);
        assert_eq!(s.completed, row.b("completed"), "completed, {}", where_);
        assert_eq!(s.wars as i64, row.i("wars"), "wars, {}", where_);
        assert_eq!(
            s.deepest_war as i64,
            row.i("deepest_war"),
            "deepest_war, {}",
            where_
        );
        assert_eq!(
            s.biggest_pot as i64,
            row.i("biggest_pot"),
            "biggest_pot, {}",
            where_
        );
        if row.is_null("winner") {
            assert_eq!(s.winner, None, "winner should be null, {}", where_);
        } else {
            assert_eq!(
                s.winner.map(|w| w as i64),
                Some(row.i("winner")),
                "winner, {}",
                where_
            );
        }
        assert_eq!(
            s.eliminations as i64,
            row.i("eliminations"),
            "eliminations, {}",
            where_
        );
        let want: Vec<i64> = s.standings.iter().map(|&x| x as i64).collect();
        assert_eq!(want, row.l("standings"), "standings, {}", where_);
        let counts: Vec<i64> = s.card_counts.iter().map(|&x| x as i64).collect();
        assert_eq!(counts, row.l("card_counts"), "card_counts, {}", where_);
        let outs: Vec<i64> = s.round_out.iter().map(|&x| x as i64).collect();
        assert_eq!(outs, row.l("round_out"), "round_out, {}", where_);

        for (k, v) in g.sink.counts.iter() {
            *census.entry(k).or_insert(0) += v;
        }
        if s.winner.is_none() && s.completed {
            draws += 1;
        }
        checked += 1;
    }

    println!("[{}] oracle games matched: {}", label, checked);
    println!("[{}] tiebreakers exercised: {:?}", label, census);
    println!("[{}] games ending with no winner: {}", label, draws);
    assert!(
        checked >= min_games,
        "only {} games in the {} fixture",
        checked,
        label
    );
    census
}

#[test]
fn matches_the_python_engine_game_for_game() {
    let census = compare_fixture("complete", include_str!("data/oracle_war.jsonl"), 300);
    for kind in [
        "Default",
        "Forfeit",
        "Modified",
        "Modified Forfeit",
        "Draw",
    ] {
        assert!(
            census.get(kind).copied().unwrap_or(0) > 0,
            "no {} tiebreaker was exercised -- coverage gap",
            kind
        );
    }
}

/// The same grid stopped at 7 / 40 / 250 / 1500 rounds. Most of these games
/// are still in progress, so this compares live card counts, elimination
/// rounds and survivor standings -- and it is the only check on the
/// `max_rounds` cap, which no finished game reaches.
#[test]
fn matches_the_python_engine_mid_game_under_the_round_cap() {
    compare_fixture(
        "capped",
        include_str!("data/oracle_war_capped.jsonl"),
        300,
    );
}
