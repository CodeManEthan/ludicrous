//! The browser playback API: one prepare pass, then random-access rounds.
//!
//! The shape here is the whole point of v2. A game is `(config, seed)`, and
//! playback state is *checkpoints plus resimulation* -- never an event log.
//! `prepare()` runs the game once and keeps three small things:
//!
//! * a downsampled chart series built by halving the sample interval
//!   whenever the buffer fills (<= `SAMPLE_CAP` uniform points per player),
//!   so one pass produces a uniform series without knowing the round count
//!   up front -- plus a dense opening (every round up to `DENSE_ROUNDS`,
//!   then a 2% geometric bridge) so a chart zoomed to the first seconds of
//!   a million-round game still has something to draw;
//! * the same halving trick over checkpoint blobs, sized so the whole set
//!   stays inside `CK_BYTE_BUDGET`;
//! * summary, standings and the elimination timeline.
//!
//! `roundView(R)` then restores the nearest checkpoint at or before `R-1`,
//! resims to `R-1` with the sink muted, and plays exactly one round with it
//! live. Stepping to `R+1` skips the restore entirely, so playback costs one
//! round per frame no matter how far into a 1.3M-round game it is.

use ludicrous_core::cards::{rank, suit_name};
use ludicrous_core::events::{Event, EventSink, NullSink};
use ludicrous_core::war::WarGame;
use ludicrous_core::Xoshiro256ss;
use wasm_bindgen::prelude::*;

use crate::{config, summary_json};

/// Uniform chart points handed to JS. The UI downsamples nothing further.
const SAMPLE_CAP: usize = 1200;
/// Every round up to here is a chart sample: the opening of a big game is a
/// few hundred rounds that playback spends real seconds on, and the uniform
/// series would put them all in one pixel. Mirrored in `web/app.js`
/// (`chartSampleRounds`) and `server.py` (`chart_sample_rounds`).
const DENSE_ROUNDS: u32 = 200;
/// Past the dense opening, sample every `r / GEO_DIVISOR` rounds (a 2%
/// geometric bridge) until the uniform series is at least that fine.
const GEO_DIVISOR: u32 = 50;
/// Ceiling on the whole checkpoint set. A 100p/50d blob is ~3.8 KB, so this
/// buys ~1000 checkpoints there and fewer for a fatter shoe.
const CK_BYTE_BUDGET: usize = 4 << 20;
const CK_MIN: usize = 32;
const CK_MAX: usize = 1024;

// ------------------------------------------------------------- round sink

/// Captures one round's worth of events, and only when `on`.
///
/// The `on` flag is a runtime gate on top of the compile-time one: resim
/// between a checkpoint and the target round emits events nobody wants, and
/// an early return is far cheaper than building a second game.
///
/// The fields mirror what `web/app.js` `buildIndex()` keeps per round, down
/// to the display semantics: the *last* face-up card per player, and the
/// *last* `WarDeclared` of the round (the deepest stage).
struct RoundSink {
    on: bool,
    /// Last face-up card per player, `-1` for none. Index = player id - 1.
    faces: Vec<i16>,
    war: Option<(u32, &'static str)>,
    war_players: Vec<u32>,
    win: Option<(u32, u32, &'static str)>,
    drawn: Option<Vec<u32>>,
    elims: Vec<u32>,
    counts: Vec<(u32, u32)>,
}

impl RoundSink {
    fn new(num_players: usize) -> Self {
        RoundSink {
            on: false,
            faces: vec![-1; num_players],
            war: None,
            war_players: Vec::new(),
            win: None,
            drawn: None,
            elims: Vec::new(),
            counts: Vec::new(),
        }
    }

    fn reset(&mut self) {
        for f in self.faces.iter_mut() {
            *f = -1;
        }
        self.war = None;
        self.war_players.clear();
        self.win = None;
        self.drawn = None;
        self.elims.clear();
        self.counts.clear();
    }
}

impl EventSink for RoundSink {
    const ENABLED: bool = true;

    fn emit(&mut self, event: Event<'_>) {
        if !self.on {
            return;
        }
        match event {
            Event::RoundStarted { .. } => self.reset(),
            Event::CardPlayed {
                player,
                card,
                face_up,
                ..
            } => {
                if face_up {
                    self.faces[player as usize - 1] = card as i16;
                }
            }
            Event::WarDeclared {
                players,
                depth,
                tiebreaker,
                ..
            } => {
                self.war = Some((depth, tiebreaker));
                self.war_players.clear();
                self.war_players.extend_from_slice(players);
            }
            Event::PlayerEliminated { player, .. } => self.elims.push(player),
            Event::RoundWon {
                winner,
                cards_won,
                via,
                ..
            } => self.win = Some((winner, cards_won, via)),
            Event::RoundDrawn { players, .. } => self.drawn = Some(players.to_vec()),
            Event::RoundEnded { card_counts, .. } => {
                self.counts.clear();
                self.counts.extend_from_slice(card_counts);
            }
            _ => {}
        }
    }
}

// ------------------------------------------------------------- json bits

fn push_num(out: &mut String, n: u64) {
    use core::fmt::Write;
    let _ = write!(out, "{}", n);
}

fn push_id_list(out: &mut String, xs: &[u32]) {
    out.push('[');
    for (i, x) in xs.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        push_num(out, *x as u64);
    }
    out.push(']');
}

// ----------------------------------------------------------- the prepared

/// One prepared game: everything the UI needs up front, plus the machinery
/// to reconstruct any single round on demand.
#[wasm_bindgen]
pub struct WarPrepared {
    num_players: usize,
    rounds: u32,
    summary: String,
    standings: Vec<u32>,
    sample_rounds: Vec<u32>,
    /// Player-major, `num_players * sample_rounds.len()`. `-1` means the
    /// player was already out at that sample, which the chart reads as a
    /// line that has ended.
    series: Vec<i32>,
    initial_counts: Vec<u32>,
    elim_rounds: Vec<u32>,
    elim_players: Vec<u32>,

    /// All checkpoint blobs end to end, with `ck_off[i]..ck_off[i + 1]`
    /// bounding blob `i` and `ck_rounds[i]` naming the round it sits at.
    ck_data: Vec<u8>,
    ck_off: Vec<u32>,
    ck_rounds: Vec<u32>,
    ck_interval: u32,

    view: WarGame<Xoshiro256ss, RoundSink>,
}

/// Drop every other sample and double the interval. The kept rounds are the
/// even indices, so a series that was `0, I, 2I, ...` becomes `0, 2I, 4I,
/// ...` -- still uniform, still starting at the deal.
fn halve_rows<T: Copy>(rounds: &mut Vec<u32>, rows: &mut Vec<T>, stride: usize) {
    let keep = rounds.len().div_ceil(2);
    for i in 0..keep {
        rounds[i] = rounds[i * 2];
        let (src, dst) = (i * 2 * stride, i * stride);
        if src != dst {
            rows.copy_within(src..src + stride, dst);
        }
    }
    rounds.truncate(keep);
    rows.truncate(keep * stride);
}

/// Same halving for the checkpoint set, which is variable-stride in
/// principle (blob sizes are constant in practice, since the table is always
/// empty at a round boundary) so it rebuilds the offset table.
fn halve_checkpoints(rounds: &mut Vec<u32>, data: &mut Vec<u8>, off: &mut Vec<u32>) {
    let keep = rounds.len().div_ceil(2);
    let mut write = 0usize;
    let mut new_off = Vec::with_capacity(keep + 1);
    new_off.push(0u32);
    for i in 0..keep {
        rounds[i] = rounds[i * 2];
        let (a, b) = (off[i * 2] as usize, off[i * 2 + 1] as usize);
        data.copy_within(a..b, write);
        write += b - a;
        new_off.push(write as u32);
    }
    rounds.truncate(keep);
    data.truncate(write);
    *off = new_off;
}

#[wasm_bindgen]
impl WarPrepared {
    #[wasm_bindgen(getter)]
    pub fn rounds(&self) -> u32 {
        self.rounds
    }

    #[wasm_bindgen(getter, js_name = numPlayers)]
    pub fn num_players(&self) -> u32 {
        self.num_players as u32
    }

    #[wasm_bindgen(js_name = summaryJson)]
    pub fn summary_json(&self) -> String {
        self.summary.clone()
    }

    /// Sample rounds for the chart, ascending, first is 0 (the deal).
    #[wasm_bindgen(js_name = chartRounds)]
    pub fn chart_rounds(&self) -> Vec<u32> {
        self.sample_rounds.clone()
    }

    /// Card counts at those rounds, player-major, `-1` once a player is out.
    #[wasm_bindgen(js_name = chartSeries)]
    pub fn chart_series(&self) -> Vec<i32> {
        self.series.clone()
    }

    #[wasm_bindgen(js_name = initialCounts)]
    pub fn initial_counts(&self) -> Vec<u32> {
        self.initial_counts.clone()
    }

    #[wasm_bindgen(js_name = elimRounds)]
    pub fn elim_rounds(&self) -> Vec<u32> {
        self.elim_rounds.clone()
    }

    #[wasm_bindgen(js_name = elimPlayers)]
    pub fn elim_players(&self) -> Vec<u32> {
        self.elim_players.clone()
    }

    #[wasm_bindgen(js_name = standings)]
    pub fn standings(&self) -> Vec<u32> {
        self.standings.clone()
    }

    #[wasm_bindgen(getter, js_name = checkpointCount)]
    pub fn checkpoint_count(&self) -> u32 {
        self.ck_rounds.len() as u32
    }

    #[wasm_bindgen(getter, js_name = checkpointBytes)]
    pub fn checkpoint_bytes(&self) -> u32 {
        self.ck_data.len() as u32
    }

    #[wasm_bindgen(getter, js_name = checkpointInterval)]
    pub fn checkpoint_interval(&self) -> u32 {
        self.ck_interval
    }

    /// Where the resim cursor currently sits. Exposed for tests that want to
    /// prove a sequential step did not restore anything.
    #[wasm_bindgen(getter, js_name = cursorRound)]
    pub fn cursor_round(&self) -> u32 {
        self.view.round()
    }

    /// One round, as the JSON the UI renders. Round 0 (the deal) has no
    /// round data by construction and returns `null`.
    #[wasm_bindgen(js_name = roundView)]
    pub fn round_view(&mut self, round: u32) -> Result<String, JsError> {
        if round == 0 || self.rounds == 0 {
            return Ok("null".to_string());
        }
        let round = round.min(self.rounds);
        self.position(round - 1)?;

        self.view.sink.on = true;
        self.view.play_round();
        self.view.sink.on = false;

        let mut wins = Vec::with_capacity(self.num_players);
        self.view.wins_into(&mut wins);
        Ok(self.render(round, &wins))
    }

    /// Put the resim cursor exactly on `target`, restoring a checkpoint only
    /// when walking forward from where it already is would be wrong or slow.
    fn position(&mut self, target: u32) -> Result<(), JsError> {
        let cur = self.view.round();
        // Largest checkpoint at or before the target.
        let idx = match self.ck_rounds.binary_search(&target) {
            Ok(i) => i,
            Err(i) => i.saturating_sub(1),
        };
        let ck_round = self.ck_rounds[idx];
        if cur > target || cur < ck_round {
            let bytes = &self.ck_data[self.ck_off[idx] as usize..self.ck_off[idx + 1] as usize];
            let sink = RoundSink::new(self.num_players);
            self.view = WarGame::restore(bytes, sink)
                .map_err(|e| JsError::new(&format!("bad checkpoint: {:?}", e)))?;
        }
        let gap = target - self.view.round();
        if gap > 0 {
            self.view.advance(gap);
        }
        Ok(())
    }

    fn render(&self, round: u32, wins: &[u32]) -> String {
        let s = &self.view.sink;
        let mut out = String::with_capacity(128 + self.num_players * 24);
        out.push_str("{\"round\":");
        push_num(&mut out, round as u64);

        out.push_str(",\"faces\":{");
        let mut first = true;
        for (i, &f) in s.faces.iter().enumerate() {
            if f < 0 {
                continue;
            }
            if !first {
                out.push(',');
            }
            first = false;
            let card = f as u8;
            out.push('"');
            push_num(&mut out, i as u64 + 1);
            out.push_str("\":[");
            push_num(&mut out, rank(card) as u64);
            out.push_str(",\"");
            out.push_str(suit_name(card));
            out.push_str("\"]");
        }

        out.push_str("},\"counts\":{");
        for (i, (pid, count)) in s.counts.iter().enumerate() {
            if i > 0 {
                out.push(',');
            }
            out.push('"');
            push_num(&mut out, *pid as u64);
            out.push_str("\":");
            push_num(&mut out, *count as u64);
        }

        out.push_str("},\"wins\":{");
        for (i, w) in wins.iter().enumerate() {
            if i > 0 {
                out.push(',');
            }
            out.push('"');
            push_num(&mut out, i as u64 + 1);
            out.push_str("\":");
            push_num(&mut out, *w as u64);
        }
        out.push('}');

        out.push_str(",\"war\":");
        match s.war {
            Some((depth, tiebreaker)) => {
                out.push_str("{\"depth\":");
                push_num(&mut out, depth as u64);
                out.push_str(",\"tiebreaker\":\"");
                out.push_str(tiebreaker);
                out.push_str("\",\"players\":");
                push_id_list(&mut out, &s.war_players);
                out.push('}');
            }
            None => out.push_str("null"),
        }

        out.push_str(",\"win\":");
        match s.win {
            Some((winner, cards, via)) => {
                out.push_str("{\"winner\":");
                push_num(&mut out, winner as u64);
                out.push_str(",\"cards\":");
                push_num(&mut out, cards as u64);
                out.push_str(",\"via\":\"");
                out.push_str(via);
                out.push_str("\"}");
            }
            None => out.push_str("null"),
        }

        out.push_str(",\"drawn\":");
        match &s.drawn {
            Some(players) => {
                out.push_str("{\"players\":");
                push_id_list(&mut out, players);
                out.push('}');
            }
            None => out.push_str("null"),
        }

        out.push_str(",\"elims\":");
        push_id_list(&mut out, &s.elims);
        out.push('}');
        out
    }
}

/// The prepare pass as a resumable job, so a worker can report progress and
/// honor a cancel between steps. `prepare()` below is the one-call form.
///
/// The loop body in `step` is the whole algorithm; `new` is the setup that
/// used to precede it and `finish` is what used to follow. Splitting it
/// changes nothing about the output -- `tests/prepared.rs` proves the two
/// paths byte-identical.
#[wasm_bindgen]
pub struct WarPrepareJob {
    g: WarGame<Xoshiro256ss, NullSink>,
    max_rounds: u64,
    np: usize,

    sample_rounds: Vec<u32>,
    rows: Vec<i32>,
    sample_interval: u32,
    /// The dense opening + geometric bridge, kept apart from the uniform
    /// series because halving must never thin them. Merged in `finish`.
    open_rounds: Vec<u32>,
    open_rows: Vec<i32>,
    next_open: u32,
    counts: Vec<u32>,
    round_out: Vec<i32>,
    initial_counts: Vec<u32>,

    ck_budget: usize,
    ck_interval: u32,
    ck_off: Vec<u32>,
    ck_data: Vec<u8>,
    ck_rounds: Vec<u32>,

    elim_rounds: Vec<u32>,
    elim_players: Vec<u32>,
    alive: u32,
}

#[wasm_bindgen]
impl WarPrepareJob {
    /// `checkpoint_interval` is a hint: pass 0 (or a negative) to let the pass
    /// pick one, which is almost always what you want -- the round count is
    /// not known until the game is over.
    #[wasm_bindgen(constructor)]
    pub fn new(
        num_players: u32,
        num_decks: u32,
        seed: f64,
        max_rounds: f64,
        checkpoint_interval: f64,
    ) -> Result<WarPrepareJob, JsError> {
        let cfg = config(num_players, num_decks, max_rounds);
        cfg.validate().map_err(JsError::new)?;
        let seed = seed as u64;
        let np = num_players as usize;

        let mut g: WarGame<Xoshiro256ss, NullSink> =
            WarGame::new(cfg, Xoshiro256ss::from_seed(seed), seed);
        g.start();

        let mut job = WarPrepareJob {
            g,
            max_rounds: cfg.max_rounds,
            np,
            sample_rounds: Vec::with_capacity(SAMPLE_CAP + 1),
            rows: Vec::with_capacity((SAMPLE_CAP + 1) * np),
            sample_interval: 1,
            open_rounds: Vec::new(),
            open_rows: Vec::new(),
            next_open: 1,
            counts: Vec::with_capacity(np),
            round_out: Vec::with_capacity(np),
            initial_counts: Vec::new(),
            ck_budget: 0,
            ck_interval: if checkpoint_interval >= 1.0 {
                checkpoint_interval as u32
            } else {
                1
            },
            ck_off: Vec::new(),
            ck_data: Vec::new(),
            ck_rounds: vec![0],
            elim_rounds: Vec::new(),
            elim_players: Vec::new(),
            alive: 0,
        };

        job.sample(0);
        job.initial_counts = job.counts.clone();

        let first = job.g.save();
        job.ck_budget = (CK_BYTE_BUDGET / first.len().max(1)).clamp(CK_MIN, CK_MAX);
        job.ck_off = vec![0, first.len() as u32];
        job.ck_data = first;
        job.alive = job.g.alive();
        Ok(job)
    }

    /// Play up to `budget` more rounds. Returns true once the game is over or
    /// the cap is reached, after which `finish` is the only useful call.
    pub fn step(&mut self, budget: u32) -> bool {
        let mut left = budget;
        while left > 0 && !self.g.is_over() && (self.g.round() as u64) < self.max_rounds {
            self.g.play_round();
            left -= 1;
            let r = self.g.round();

            if self.g.alive() != self.alive {
                self.alive = self.g.alive();
                self.g.round_out_into(&mut self.round_out);
                for p in 0..self.np {
                    if self.round_out[p] == r as i32 {
                        self.elim_rounds.push(r);
                        self.elim_players.push(p as u32 + 1);
                    }
                }
            }

            if r % self.sample_interval == 0 {
                self.sample(r);
                if self.sample_rounds.len() > SAMPLE_CAP - 1 {
                    halve_rows(&mut self.sample_rounds, &mut self.rows, self.np);
                    self.sample_interval *= 2;
                }
            }
            if r == self.next_open {
                self.sample_open(r);
                self.next_open = next_open_round(r);
            }

            if r % self.ck_interval == 0 {
                let blob = self.g.save();
                self.ck_data.extend_from_slice(&blob);
                self.ck_off.push(self.ck_data.len() as u32);
                self.ck_rounds.push(r);
                if self.ck_rounds.len() > self.ck_budget {
                    halve_checkpoints(&mut self.ck_rounds, &mut self.ck_data, &mut self.ck_off);
                    self.ck_interval = self.ck_interval.saturating_mul(2);
                }
            }
        }
        self.done()
    }

    pub fn done(&self) -> bool {
        self.g.is_over() || (self.g.round() as u64) >= self.max_rounds
    }

    pub fn round(&self) -> u32 {
        self.g.round()
    }

    pub fn alive(&self) -> u32 {
        self.g.alive()
    }

    /// Close the pass: final sample, transpose the chart, build the summary
    /// and the playback view. Consumes the job.
    pub fn finish(mut self) -> Result<WarPrepared, JsError> {
        let rounds = self.g.round();
        if self.sample_rounds.last() != Some(&rounds) {
            self.sample(rounds);
        }
        let np = self.np;

        // ---- merge the dense opening into the uniform series (sorted, no
        // duplicate rounds; both buffers hold the same numbers for a round)
        let (sample_rounds, rows) = merge_samples(
            &self.sample_rounds, &self.rows, &self.open_rounds, &self.open_rows, np,
        );

        // ---- transpose to player-major so JS can slice one player's line
        let ns = sample_rounds.len();
        let mut series = vec![0i32; np * ns];
        for s in 0..ns {
            for p in 0..np {
                series[p * ns + s] = rows[s * np + p];
            }
        }

        let summary = self.g.summary();
        let view = WarGame::restore(&self.ck_data[..self.ck_off[1] as usize], RoundSink::new(np))
            .map_err(|e| JsError::new(&format!("bad checkpoint: {:?}", e)))?;

        Ok(WarPrepared {
            num_players: np,
            rounds,
            summary: summary_json(&summary),
            standings: summary.standings.clone(),
            sample_rounds,
            series,
            initial_counts: self.initial_counts,
            elim_rounds: self.elim_rounds,
            elim_players: self.elim_players,
            ck_data: self.ck_data,
            ck_off: self.ck_off,
            ck_rounds: self.ck_rounds,
            ck_interval: self.ck_interval,
            view,
        })
    }
}

impl WarPrepareJob {
    fn sample(&mut self, r: u32) {
        self.g.card_counts_into(&mut self.counts);
        self.g.round_out_into(&mut self.round_out);
        self.sample_rounds.push(r);
        push_row(&mut self.rows, &self.counts, &self.round_out, r);
    }

    fn sample_open(&mut self, r: u32) {
        self.g.card_counts_into(&mut self.counts);
        self.g.round_out_into(&mut self.round_out);
        self.open_rounds.push(r);
        push_row(&mut self.open_rows, &self.counts, &self.round_out, r);
    }
}

fn push_row(rows: &mut Vec<i32>, counts: &[u32], round_out: &[i32], r: u32) {
    for (p, &c) in counts.iter().enumerate() {
        let out = round_out[p];
        rows.push(if out >= 0 && (out as u32) < r { -1 } else { c as i32 });
    }
}

/// The opening schedule: every round through `DENSE_ROUNDS`, then 2% steps.
/// Integer arithmetic on purpose, so wasm and native agree to the round.
fn next_open_round(r: u32) -> u32 {
    if r < DENSE_ROUNDS {
        r + 1
    } else {
        r + (r / GEO_DIVISOR).max(1)
    }
}

/// Merge two round-major sample sets into one sorted, de-duplicated set.
fn merge_samples(
    a_rounds: &[u32], a_rows: &[i32], b_rounds: &[u32], b_rows: &[i32], np: usize,
) -> (Vec<u32>, Vec<i32>) {
    let mut rounds = Vec::with_capacity(a_rounds.len() + b_rounds.len());
    let mut rows = Vec::with_capacity((a_rounds.len() + b_rounds.len()) * np);
    let (mut i, mut j) = (0, 0);
    while i < a_rounds.len() || j < b_rounds.len() {
        let take_a = j >= b_rounds.len() || (i < a_rounds.len() && a_rounds[i] <= b_rounds[j]);
        let (r, src) = if take_a {
            (a_rounds[i], &a_rows[i * np..(i + 1) * np])
        } else {
            (b_rounds[j], &b_rows[j * np..(j + 1) * np])
        };
        if take_a { i += 1 } else { j += 1 }
        if rounds.last() == Some(&r) {
            continue;
        }
        rounds.push(r);
        rows.extend_from_slice(src);
    }
    (rounds, rows)
}

/// Run a whole game once and keep what playback needs.
///
/// `checkpoint_interval` is a hint: pass 0 (or a negative) to let the pass
/// pick one, which is almost always what you want -- the round count is not
/// known until the game is over.
#[wasm_bindgen]
pub fn prepare(
    num_players: u32,
    num_decks: u32,
    seed: f64,
    max_rounds: f64,
    checkpoint_interval: f64,
) -> Result<WarPrepared, JsError> {
    let mut job = WarPrepareJob::new(num_players, num_decks, seed, max_rounds, checkpoint_interval)?;
    while !job.step(u32::MAX) {}
    job.finish()
}
