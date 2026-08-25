//! Event emission.
//!
//! The sink is a compile-time choice, not a runtime flag. `NullSink` has
//! `ENABLED = false`, so every `if S::ENABLED { ... }` in the engine folds
//! away and the benchmark path carries no branch at all -- not even the
//! argument construction.

use crate::cards::{rank, suit_name};

/// Borrowed view of one event. Nothing here allocates; the slices point at
/// scratch buffers the engine reuses round to round.
#[derive(Debug)]
pub enum Event<'a> {
    GameStarted {
        round: u32,
        num_players: u32,
        num_decks: u32,
        seed: u64,
    },
    CardsDealt {
        round: u32,
        card_counts: &'a [(u32, u32)],
    },
    RoundStarted {
        round: u32,
        players: &'a [u32],
    },
    CardPlayed {
        round: u32,
        player: u32,
        card: u8,
        face_up: bool,
    },
    WarDeclared {
        round: u32,
        players: &'a [u32],
        rank: u8,
        depth: u32,
        tiebreaker: &'static str,
    },
    PlayerEliminated {
        round: u32,
        player: u32,
        reason: &'static str,
    },
    RoundWon {
        round: u32,
        winner: u32,
        cards_won: u32,
        via: &'static str,
    },
    RoundDrawn {
        round: u32,
        players: &'a [u32],
        cards_returned: &'a [(u32, u32)],
    },
    RoundEnded {
        round: u32,
        card_counts: &'a [(u32, u32)],
    },
    GameOver {
        round: u32,
        winner: Option<u32>,
        total_rounds: u32,
    },
}

pub trait EventSink {
    /// Const so the engine can drop the whole emission path at compile time.
    const ENABLED: bool;
    fn emit(&mut self, event: Event<'_>);
}

/// Benchmark mode: events cost nothing because they do not exist.
#[derive(Default, Clone, Copy)]
pub struct NullSink;

impl EventSink for NullSink {
    const ENABLED: bool = false;
    #[inline(always)]
    fn emit(&mut self, _event: Event<'_>) {}
}

/// Counts events without building any. Useful for measuring the emission
/// overhead separately from JSON formatting.
#[derive(Default)]
pub struct CountingSink {
    pub count: u64,
}

impl EventSink for CountingSink {
    const ENABLED: bool = true;
    #[inline]
    fn emit(&mut self, _event: Event<'_>) {
        self.count += 1;
    }
}

/// Writes NDJSON matching the shapes `engine/events.py` produces through
/// `to_dict()` + `json.dumps`: `{"type": ..., "round": ..., <fields>}`, dict
/// keys stringified, `Card` as `[rank, "SuitWord"]`.
///
/// Hand-rolled rather than serde -- the payloads are this simple, and a wasm
/// bundle that does not link a derive-based serializer is a good deal
/// smaller.
#[derive(Default)]
pub struct JsonSink {
    pub out: String,
    pub count: u64,
    /// Player names, index 0 = player 1. Only used by `GameStarted`.
    pub names: Vec<String>,
}

impl JsonSink {
    pub fn new(names: Vec<String>) -> Self {
        JsonSink {
            out: String::new(),
            count: 0,
            names,
        }
    }

    fn int_map(&mut self, key: &str, pairs: &[(u32, u32)]) {
        self.out.push('"');
        self.out.push_str(key);
        self.out.push_str("\": {");
        for (i, (k, v)) in pairs.iter().enumerate() {
            if i > 0 {
                self.out.push_str(", ");
            }
            push_fmt(&mut self.out, format_args!("\"{}\": {}", k, v));
        }
        self.out.push('}');
    }

    fn int_list(&mut self, key: &str, xs: &[u32]) {
        self.out.push('"');
        self.out.push_str(key);
        self.out.push_str("\": [");
        for (i, x) in xs.iter().enumerate() {
            if i > 0 {
                self.out.push_str(", ");
            }
            push_fmt(&mut self.out, format_args!("{}", x));
        }
        self.out.push(']');
    }
}

fn push_fmt(s: &mut String, args: core::fmt::Arguments<'_>) {
    use core::fmt::Write;
    let _ = s.write_fmt(args);
}

impl EventSink for JsonSink {
    const ENABLED: bool = true;

    fn emit(&mut self, event: Event<'_>) {
        self.count += 1;
        match event {
            Event::GameStarted {
                round,
                num_players,
                num_decks,
                seed,
            } => {
                push_fmt(
                    &mut self.out,
                    format_args!(
                        "{{\"round\": {}, \"num_players\": {}, \"num_decks\": {}, \
                         \"player_names\": {{",
                        round, num_players, num_decks
                    ),
                );
                for i in 0..num_players as usize {
                    if i > 0 {
                        self.out.push_str(", ");
                    }
                    let name = self
                        .names
                        .get(i)
                        .cloned()
                        .unwrap_or_else(|| format!("Player {}", i + 1));
                    push_fmt(&mut self.out, format_args!("\"{}\": \"{}\"", i + 1, name));
                }
                push_fmt(
                    &mut self.out,
                    format_args!("}}, \"seed\": {}, \"type\": \"GameStarted\"}}\n", seed),
                );
            }
            Event::CardsDealt { round, card_counts } => {
                push_fmt(&mut self.out, format_args!("{{\"round\": {}, ", round));
                self.int_map("card_counts", card_counts);
                self.out.push_str(", \"type\": \"CardsDealt\"}\n");
            }
            Event::RoundStarted { round, players } => {
                push_fmt(&mut self.out, format_args!("{{\"round\": {}, ", round));
                self.int_list("players", players);
                self.out.push_str(", \"type\": \"RoundStarted\"}\n");
            }
            Event::CardPlayed {
                round,
                player,
                card,
                face_up,
            } => {
                push_fmt(
                    &mut self.out,
                    format_args!(
                        "{{\"round\": {}, \"player\": {}, \"card\": [{}, \"{}\"], \
                         \"face_up\": {}, \"type\": \"CardPlayed\"}}\n",
                        round,
                        player,
                        rank(card),
                        suit_name(card),
                        if face_up { "true" } else { "false" }
                    ),
                );
            }
            Event::WarDeclared {
                round,
                players,
                rank: r,
                depth,
                tiebreaker,
            } => {
                push_fmt(&mut self.out, format_args!("{{\"round\": {}, ", round));
                self.int_list("players", players);
                push_fmt(
                    &mut self.out,
                    format_args!(
                        ", \"rank\": {}, \"depth\": {}, \"tiebreaker\": \"{}\", \
                         \"type\": \"WarDeclared\"}}\n",
                        r, depth, tiebreaker
                    ),
                );
            }
            Event::PlayerEliminated {
                round,
                player,
                reason,
            } => {
                push_fmt(
                    &mut self.out,
                    format_args!(
                        "{{\"round\": {}, \"player\": {}, \"reason\": \"{}\", \
                         \"type\": \"PlayerEliminated\"}}\n",
                        round, player, reason
                    ),
                );
            }
            Event::RoundWon {
                round,
                winner,
                cards_won,
                via,
            } => {
                push_fmt(
                    &mut self.out,
                    format_args!(
                        "{{\"round\": {}, \"winner\": {}, \"cards_won\": {}, \
                         \"via\": \"{}\", \"type\": \"RoundWon\"}}\n",
                        round, winner, cards_won, via
                    ),
                );
            }
            Event::RoundDrawn {
                round,
                players,
                cards_returned,
            } => {
                push_fmt(&mut self.out, format_args!("{{\"round\": {}, ", round));
                self.int_list("players", players);
                self.out.push_str(", ");
                self.int_map("cards_returned", cards_returned);
                self.out.push_str(", \"type\": \"RoundDrawn\"}\n");
            }
            Event::RoundEnded { round, card_counts } => {
                push_fmt(&mut self.out, format_args!("{{\"round\": {}, ", round));
                self.int_map("card_counts", card_counts);
                self.out.push_str(", \"type\": \"RoundEnded\"}\n");
            }
            Event::GameOver {
                round,
                winner,
                total_rounds,
            } => {
                push_fmt(&mut self.out, format_args!("{{\"round\": {}, ", round));
                match winner {
                    Some(w) => push_fmt(&mut self.out, format_args!("\"winner\": {}", w)),
                    None => self.out.push_str("\"winner\": null"),
                }
                push_fmt(
                    &mut self.out,
                    format_args!(
                        ", \"total_rounds\": {}, \"type\": \"GameOver\"}}\n",
                        total_rounds
                    ),
                );
            }
        }
    }
}
