//! Checkpoint round-trip and determinism.
//!
//! The point of the seek API is that restoring a snapshot and replaying is
//! indistinguishable from never having stopped. These tests assert exactly
//! that, on the summary *and* on the full event recording.

use ludicrous_core::checkpoint::{HEADER_LEN, PLAYER_META_LEN};
use ludicrous_core::events::{JsonSink, NullSink};
use ludicrous_core::war::{Config, WarGame};
use ludicrous_core::Xoshiro256ss;

type Game = WarGame<Xoshiro256ss, NullSink>;

fn fresh(p: u32, d: u32, seed: u64) -> Game {
    Game::new(Config::new(p, d), Xoshiro256ss::from_seed(seed), seed)
}

#[test]
fn restore_then_replay_matches_an_uninterrupted_run() {
    for &(p, d, seed) in &[
        (2u32, 1u32, 3u64),
        (6, 3, 42),
        (13, 1, 7),
        (26, 13, 99),
        (100, 50, 5),
    ] {
        // The reference: one run, start to finish.
        let mut whole = fresh(p, d, seed);
        whole.run();
        let want = whole.summary();

        // Same game, chopped at several points and rebuilt from bytes each
        // time. Cut points are deliberately not round numbers the engine
        // would treat specially.
        for &cut in &[1u32, 2, 37, 500, 4001] {
            if cut >= want.rounds {
                continue;
            }
            let mut g = fresh(p, d, seed);
            g.advance(cut);
            assert_eq!(g.round(), cut);
            let snap = g.save();

            let mut g2 = Game::restore(&snap, NullSink).unwrap();
            assert_eq!(g2.round(), cut, "round survived the round trip");
            // Re-saving a just-restored game must give back the same bytes.
            assert_eq!(g2.save(), snap, "checkpoint is canonical, {}p/{}d", p, d);

            g2.run();
            assert_eq!(
                g2.summary(),
                want,
                "restore at round {} diverged, {}p/{}d seed {}",
                cut,
                p,
                d,
                seed
            );
        }
    }
}

#[test]
fn restore_reproduces_the_event_recording_byte_for_byte() {
    let cfg = Config::new(6, 3);
    let seed = 2024u64;

    // Full recording, then the tail of it after round 200.
    let mut whole = WarGame::with_sink(
        cfg,
        Xoshiro256ss::from_seed(seed),
        seed,
        JsonSink::new(Vec::new()),
    );
    whole.advance(200);
    let prefix_len = whole.sink.out.len();
    whole.run();
    let tail_from_whole = whole.sink.out[prefix_len..].to_string();

    let mut g = fresh(6, 3, seed);
    g.advance(200);
    let snap = g.save();
    let mut g2 = WarGame::restore(&snap, JsonSink::new(Vec::new())).unwrap();
    g2.run();

    assert_eq!(g2.sink.out, tail_from_whole);
    assert!(!tail_from_whole.is_empty());
}

#[test]
fn checkpoint_size_is_what_the_layout_says() {
    let mut g = fresh(100, 50, 5);
    g.advance(1000);
    let snap = g.save();
    // Every card is somewhere: a player's deck, a player's reserve, or the
    // table. The snapshot carries all of them exactly once.
    let total_cards = 50 * 52;
    assert_eq!(snap.len(), HEADER_LEN + 100 * PLAYER_META_LEN + total_cards);
}

#[test]
fn a_rejected_checkpoint_is_an_error_not_a_panic() {
    let mut g = fresh(6, 3, 1);
    g.advance(10);
    let snap = g.save();

    assert!(Game::restore(&snap[..snap.len() - 1], NullSink).is_err());
    let mut bad = snap.clone();
    bad[0] = b'X';
    assert!(Game::restore(&bad, NullSink).is_err());
    let mut bad = snap.clone();
    bad[4] = 99;
    assert!(Game::restore(&bad, NullSink).is_err());
}

#[test]
fn seeking_from_a_sparse_checkpoint_index_lands_where_a_full_replay_would() {
    // What the UI scrubber will actually do: keep a snapshot every 250
    // rounds, then jump to an arbitrary round by restoring the nearest one
    // and replaying the remainder.
    let (p, d, seed) = (6u32, 3u32, 77u64);
    let mut g = fresh(p, d, seed);
    let mut index: Vec<(u32, Vec<u8>)> = vec![(0, g.save())];
    while !g.is_over() {
        g.advance(250);
        index.push((g.round(), g.save()));
    }
    let last = g.round();

    for target in [1u32, 249, 250, 251, 999, last / 2, last - 1] {
        if target >= last {
            continue;
        }
        let (at, snap) = index
            .iter()
            .rev()
            .find(|(r, _)| *r <= target)
            .expect("index always has round 0");
        let mut sought = Game::restore(snap, NullSink).unwrap();
        sought.advance(target - at);

        let mut direct = fresh(p, d, seed);
        direct.advance(target);

        assert_eq!(sought.save(), direct.save(), "seek to round {}", target);
    }
}
