//! wasm-bindgen surface for the browser.
//!
//! Deliberately narrow. Everything crossing the JS boundary is a number, a
//! `Uint8Array`, or a JSON string -- no serde, no `JsValue` object graphs.
//! That keeps the bundle small and, more importantly, keeps the boundary out
//! of the hot loop: JS asks for a whole game or a whole seek, not a round.
//!
//! Default allocator on purpose. wee_alloc saves a few KB and costs real
//! throughput on the allocation pattern here, and it is unmaintained.

use ludicrous_core::events::{JsonSink, NullSink};
use ludicrous_core::war::{Config, Summary, WarGame};
use ludicrous_core::Xoshiro256ss;
use wasm_bindgen::prelude::*;

pub mod prepared;

pub use prepared::{prepare, WarPrepared};

type Game = WarGame<Xoshiro256ss, NullSink>;

pub(crate) fn config(num_players: u32, num_decks: u32, max_rounds: f64) -> Config {
    Config {
        num_players,
        num_decks,
        max_rounds: if max_rounds <= 0.0 {
            u64::MAX
        } else {
            max_rounds as u64
        },
    }
}

pub(crate) fn summary_json(s: &Summary) -> String {
    let mut out = String::with_capacity(256);
    out.push_str("{\"game\": \"war\"");
    out.push_str(&format!(
        ", \"num_players\": {}, \"num_decks\": {}, \"seed\": {}",
        s.num_players, s.num_decks, s.seed
    ));
    out.push_str(&format!(
        ", \"completed\": {}, \"rounds\": {}, \"wars\": {}, \"deepest_war\": {}, \
         \"biggest_pot\": {}",
        s.completed, s.rounds, s.wars, s.deepest_war, s.biggest_pot
    ));
    match s.winner {
        Some(w) => out.push_str(&format!(", \"winner\": {}", w)),
        None => out.push_str(", \"winner\": null"),
    }
    out.push_str(", \"standings\": [");
    for (i, p) in s.standings.iter().enumerate() {
        if i > 0 {
            out.push_str(", ");
        }
        out.push_str(&p.to_string());
    }
    out.push_str("]}");
    out
}

/// Play one game to completion and hand back its summary as JSON.
#[wasm_bindgen]
pub fn simulate(num_players: u32, num_decks: u32, max_rounds: f64, seed: f64) -> String {
    let seed = seed as u64;
    let mut g = Game::new(
        config(num_players, num_decks, max_rounds),
        Xoshiro256ss::from_seed(seed),
        seed,
    );
    g.run();
    summary_json(&g.summary())
}

/// Play one game with the event log on, returning NDJSON.
#[wasm_bindgen]
pub fn simulate_with_events(
    num_players: u32,
    num_decks: u32,
    max_rounds: f64,
    seed: f64,
) -> String {
    let seed = seed as u64;
    let mut g = WarGame::with_sink(
        config(num_players, num_decks, max_rounds),
        Xoshiro256ss::from_seed(seed),
        seed,
        JsonSink::new(Vec::new()),
    );
    g.run();
    g.sink.out
}

/// Batch throughput probe: run `games` games from `seed0` and return the
/// total round count. Exists so a benchmark measures the engine, not the
/// JS/wasm call overhead.
#[wasm_bindgen]
pub fn bench_rounds(num_players: u32, num_decks: u32, seed0: f64, games: u32) -> f64 {
    let c = config(num_players, num_decks, 0.0);
    let mut total = 0u64;
    for i in 0..games as u64 {
        let seed = seed0 as u64 + i;
        let mut g = Game::new(c, Xoshiro256ss::from_seed(seed), seed);
        g.run();
        total += g.round() as u64;
    }
    total as f64
}

/// A live game that can be checkpointed and rewound. This is the seek API:
/// keep a sparse array of `save()` blobs, then `restore` the nearest one
/// and `advance` the remainder.
#[wasm_bindgen]
pub struct WarSession {
    inner: Game,
}

#[wasm_bindgen]
impl WarSession {
    #[wasm_bindgen(constructor)]
    pub fn new(num_players: u32, num_decks: u32, max_rounds: f64, seed: f64) -> WarSession {
        let seed = seed as u64;
        WarSession {
            inner: Game::new(
                config(num_players, num_decks, max_rounds),
                Xoshiro256ss::from_seed(seed),
                seed,
            ),
        }
    }

    /// Rebuild from a checkpoint blob.
    pub fn restore(bytes: &[u8]) -> Result<WarSession, JsError> {
        match Game::restore(bytes, NullSink) {
            Ok(inner) => Ok(WarSession { inner }),
            Err(e) => Err(JsError::new(&format!("bad checkpoint: {:?}", e))),
        }
    }

    /// Play up to `k` more rounds. Returns how many actually happened.
    pub fn advance(&mut self, k: u32) -> u32 {
        self.inner.advance(k)
    }

    /// Play to the end.
    pub fn run(&mut self) -> u32 {
        self.inner.run()
    }

    pub fn save(&self) -> Vec<u8> {
        self.inner.save()
    }

    #[wasm_bindgen(getter)]
    pub fn round(&self) -> u32 {
        self.inner.round()
    }

    #[wasm_bindgen(getter, js_name = isOver)]
    pub fn is_over(&self) -> bool {
        self.inner.is_over()
    }

    #[wasm_bindgen(js_name = summaryJson)]
    pub fn summary_json(&self) -> String {
        summary_json(&self.inner.summary())
    }
}
