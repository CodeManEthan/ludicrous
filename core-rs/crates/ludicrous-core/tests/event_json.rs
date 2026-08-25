//! The JSON sink has to produce exactly what `engine/events.py` +
//! `json.dumps` produce -- same keys, same order, same spacing, `Card` as
//! `[rank, "SuitWord"]` -- or every existing replay client breaks.
//!
//! Fixtures from `oracle/gen_event_fixture.py`. Runs in cpython-rng mode so
//! the two engines are playing the same game.

#![cfg(feature = "cpython-rng")]

use ludicrous_core::events::JsonSink;
use ludicrous_core::mt19937::CPythonRng;
use ludicrous_core::war::{Config, WarGame};

fn names(n: u32) -> Vec<String> {
    (1..=n).map(|i| format!("Player {}", i)).collect()
}

fn check(players: u32, decks: u32, seed: u64, want: &str) {
    let cfg = Config {
        num_players: players,
        num_decks: decks,
        max_rounds: 2_000_000,
    };
    let mut g = WarGame::with_sink(
        cfg,
        CPythonRng::seeded(seed),
        seed,
        JsonSink::new(names(players)),
    );
    g.run();

    let got: Vec<&str> = g.sink.out.lines().collect();
    let want: Vec<&str> = want.lines().collect();
    assert_eq!(
        got.len(),
        want.len(),
        "{}p/{}d seed {}: event count",
        players,
        decks,
        seed
    );
    for (i, (a, b)) in got.iter().zip(want.iter()).enumerate() {
        assert_eq!(a, b, "{}p/{}d seed {}: event {}", players, decks, seed, i);
    }
}

#[test]
fn json_matches_the_python_recording() {
    check(
        4,
        1,
        3,
        include_str!("data/events_4p1d_seed3.ndjson"),
    );
    check(
        2,
        1,
        0,
        include_str!("data/events_2p1d_seed0.ndjson"),
    );
    check(
        5,
        1,
        11,
        include_str!("data/events_5p1d_seed11.ndjson"),
    );
}
