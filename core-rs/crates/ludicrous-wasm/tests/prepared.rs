//! Cross-checks for the browser playback API.
//!
//! The property that matters: a round reconstructed by seeking (restore the
//! nearest checkpoint, resim the remainder) must be byte-identical to the
//! same round reached by stepping there one round at a time. If that ever
//! stops holding, scrubbing the UI shows a different game than playing it.

use ludicrous_wasm::{prepare, WarPrepared};

fn seq_views(p: &mut WarPrepared, rounds: u32) -> Vec<String> {
    (1..=rounds).map(|r| p.round_view(r).unwrap()).collect()
}

fn field<'a>(json: &'a str, key: &str) -> &'a str {
    let at = json.find(key).unwrap_or_else(|| panic!("no {key} in {json}"));
    &json[at + key.len()..]
}

#[test]
fn seek_matches_sequential_playback() {
    for &(players, decks, seed) in &[
        (2u32, 1u32, 0f64),
        (4, 1, 3.0),
        (6, 3, 1.0),
        (5, 1, 11.0),
        (13, 2, 7.0),
        (40, 20, 2.0),
    ] {
        let mut walk = prepare(players, decks, seed, 3_000.0, 0.0).unwrap();
        let rounds = walk.rounds();
        let sequential = seq_views(&mut walk, rounds);

        // A fresh prepared game, asked for the same rounds out of order.
        let mut jump = prepare(players, decks, seed, 3_000.0, 0.0).unwrap();
        let probes: Vec<u32> = [rounds, 1, rounds / 2, rounds / 3, 2, rounds - 1, rounds / 7]
            .into_iter()
            .filter(|&r| r >= 1 && r <= rounds)
            .collect();
        for r in probes {
            let got = jump.round_view(r).unwrap();
            assert_eq!(
                got,
                sequential[r as usize - 1],
                "{players}p/{decks}d seed {seed}: seek({r}) != sequential"
            );
        }
        assert_eq!(walk.round_view(0).unwrap(), "null");
    }
}

#[test]
fn views_agree_with_the_summary() {
    let mut p = prepare(6, 3, 1.0, 3_000.0, 0.0).unwrap();
    let rounds = p.rounds();
    let summary = p.summary_json();
    let views = seq_views(&mut p, rounds);

    let mut wars = 0u64;
    let mut deepest = 0u32;
    let mut biggest = 0u32;
    let mut elims: Vec<(u32, u32)> = Vec::new();
    for (i, v) in views.iter().enumerate() {
        let round = i as u32 + 1;
        if !v.contains("\"war\":null") {
            // Only the deepest stage of the round is kept, and every stage
            // below it happened too.
            let depth: u32 = field(v, "\"war\":{\"depth\":")
                .split(',')
                .next()
                .unwrap()
                .parse()
                .unwrap();
            wars += depth as u64;
            deepest = deepest.max(depth);
        }
        if !v.contains("\"win\":null") {
            let cards: u32 = field(v, "\"cards\":").split(',').next().unwrap().parse().unwrap();
            biggest = biggest.max(cards);
        }
        let list = field(v, "\"elims\":[").split(']').next().unwrap();
        for id in list.split(',').filter(|s| !s.is_empty()) {
            elims.push((round, id.parse().unwrap()));
        }
    }

    let want = |key: &str| -> u64 {
        field(&summary, key)
            .split(|c: char| c == ',' || c == '}')
            .next()
            .unwrap()
            .trim()
            .parse()
            .unwrap()
    };
    assert_eq!(wars, want("\"wars\": "));
    assert_eq!(deepest as u64, want("\"deepest_war\": "));
    assert_eq!(biggest as u64, want("\"biggest_pot\": "));
    assert_eq!(rounds as u64, want("\"rounds\": "));

    let listed: Vec<(u32, u32)> = p
        .elim_rounds()
        .into_iter()
        .zip(p.elim_players())
        .collect();
    assert_eq!(elims, listed);

    // Cumulative wins in the last view have to add up to the rounds that
    // were actually won by somebody (a drawn war has no winner).
    let drawn = views.iter().filter(|v| !v.contains("\"drawn\":null")).count();
    let wins_blob = field(views.last().unwrap(), "\"wins\":{").split('}').next().unwrap();
    let total: u64 = wins_blob
        .split(',')
        .map(|kv| kv.split(':').nth(1).unwrap().parse::<u64>().unwrap())
        .sum();
    assert_eq!(total, rounds as u64 - drawn as u64);
}

#[test]
fn chart_and_checkpoints_stay_bounded() {
    // 40p/20d runs long enough to trigger both halving paths.
    let p = prepare(40, 20, 2.0, 1_000_000.0, 0.0).unwrap();
    let xs = p.chart_rounds();
    assert!(xs.len() <= 1200, "{} chart points", xs.len());
    assert_eq!(xs[0], 0);
    assert_eq!(*xs.last().unwrap(), p.rounds());
    assert!(xs.windows(2).all(|w| w[0] < w[1]), "chart rounds not sorted");
    assert_eq!(p.chart_series().len(), xs.len() * 40);
    assert!(
        p.checkpoint_bytes() <= 4 << 20,
        "{} checkpoint bytes",
        p.checkpoint_bytes()
    );

    // The chart line ends exactly at each player's elimination round.
    let series = p.chart_series();
    let ns = xs.len();
    let elim: std::collections::HashMap<u32, u32> =
        p.elim_players().into_iter().zip(p.elim_rounds()).collect();
    for pi in 0..40usize {
        for (s, &r) in xs.iter().enumerate() {
            let v = series[pi * ns + s];
            let out = elim.get(&(pi as u32 + 1)).is_some_and(|&e| r > e);
            assert_eq!(v < 0, out, "player {} at round {r}", pi + 1);
        }
    }
}

#[test]
fn stepping_forward_never_restores() {
    let mut p = prepare(6, 3, 1.0, 3_000.0, 0.0).unwrap();
    p.round_view(1).unwrap();
    for r in 2..=p.rounds().min(500) {
        assert_eq!(p.cursor_round(), r - 1, "cursor drifted before round {r}");
        p.round_view(r).unwrap();
    }
}

#[test]
fn a_capped_game_is_still_seekable() {
    let mut p = prepare(6, 3, 1.0, 50.0, 0.0).unwrap();
    assert_eq!(p.rounds(), 50);
    let last = p.round_view(50).unwrap();
    let mut walk = prepare(6, 3, 1.0, 50.0, 0.0).unwrap();
    for r in 1..=50 {
        let v = walk.round_view(r).unwrap();
        if r == 50 {
            assert_eq!(v, last);
        }
    }
    // Past the end clamps rather than panicking.
    assert_eq!(p.round_view(999).unwrap(), last);
}

/// The progress-reporting stepper must produce exactly what the one-call
/// `prepare` produces, whatever the step size: same chart, same checkpoints,
/// same eliminations, same views. Otherwise a game simulated with a progress
/// bar would differ from the same seed simulated without one.
#[test]
fn stepped_prepare_is_byte_identical_to_one_call() {
    use ludicrous_wasm::WarPrepareJob;
    let cases: &[(u32, u32, f64, f64)] = &[
        (2, 1, 1.0, 0.0),
        (6, 3, 7.0, 0.0),
        (6, 3, 7.0, 50.0),
        (26, 13, 3.0, 0.0),
        (40, 20, 2.0, 1_000_000.0),
        (100, 50, 5.0, 300_000.0),
    ];
    for &(players, decks, seed, cap) in cases {
        for &budget in &[1u32, 7, 1_000, 65_536] {
            let mut one = prepare(players, decks, seed, cap, 0.0).unwrap();
            let mut job = WarPrepareJob::new(players, decks, seed, cap, 0.0).unwrap();
            let mut steps = 0;
            while !job.step(budget) {
                steps += 1;
                assert!(job.round() <= one.rounds());
            }
            assert!(job.done());
            let mut two = job.finish().unwrap();
            let tag = format!("{players}p{decks}d seed {seed} cap {cap} budget {budget} ({steps} steps)");
            assert_eq!(one.rounds(), two.rounds(), "{tag}");
            assert_eq!(one.summary_json(), two.summary_json(), "{tag}");
            assert_eq!(one.chart_rounds(), two.chart_rounds(), "{tag}");
            assert_eq!(one.chart_series(), two.chart_series(), "{tag}");
            assert_eq!(one.initial_counts(), two.initial_counts(), "{tag}");
            assert_eq!(one.elim_rounds(), two.elim_rounds(), "{tag}");
            assert_eq!(one.elim_players(), two.elim_players(), "{tag}");
            assert_eq!(one.standings(), two.standings(), "{tag}");
            assert_eq!(one.checkpoint_count(), two.checkpoint_count(), "{tag}");
            assert_eq!(one.checkpoint_bytes(), two.checkpoint_bytes(), "{tag}");
            assert_eq!(one.checkpoint_interval(), two.checkpoint_interval(), "{tag}");
            let last = one.rounds();
            for r in [1, last / 3, last / 2, last] {
                if r >= 1 {
                    assert_eq!(one.round_view(r).unwrap(), two.round_view(r).unwrap(), "{tag} round {r}");
                }
            }
        }
    }
}
