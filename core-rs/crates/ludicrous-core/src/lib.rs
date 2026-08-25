//! Ludicrous game engine core.
//!
//! Native and wasm32 share this crate verbatim: no I/O, no threads, no
//! platform assumptions. The two things a caller picks are the random
//! source (a `GameRng`) and the event sink (an `EventSink`), both as type
//! parameters, so an events-off batch run compiles down to the same code a
//! hand-written simulator would.

pub mod cards;
pub mod checkpoint;
pub mod events;
pub mod rng;
pub mod war;

#[cfg(feature = "cpython-rng")]
pub mod mt19937;

pub use rng::{GameRng, SplitMix64, Xoshiro256ss};
pub use war::{simulate, Config, Summary, WarGame};
