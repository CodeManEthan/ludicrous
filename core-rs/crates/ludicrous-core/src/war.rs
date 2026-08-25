//! War, ported rule-for-rule from `engine/war.py`.
//!
//! Layout notes, because they are the whole reason this is fast:
//!
//! * Every player's cards live in one shared `Vec<u8>` split into equal
//!   `cap = num_decks * 52` regions. Within a region, `head` starts the
//!   ring; `[head, head+dcount)` is the face-down deck and the `rcount`
//!   slots after it are the reserve. A won card is written straight to the
//!   tail; a reserve reshuffle is an in-place shuffle of a region that is
//!   already sitting where the deck needs it, so it costs no copying.
//! * The event sink is a type parameter with a `const ENABLED`. In
//!   benchmark mode the emission blocks are not branches that predict well,
//!   they are code that never gets generated.

use crate::cards::build_shoe;
use crate::events::{Event, EventSink, NullSink};
use crate::rng::{shuffle_slice, GameRng, Xoshiro256ss};

const fn make_ranks() -> [u8; 64] {
    let mut t = [0u8; 64];
    let mut i = 0;
    while i < 52 {
        t[i] = (i % 13) as u8 + 2;
        i += 1;
    }
    t
}
static RANKS: [u8; 64] = make_ranks();

/// Rank of a card byte. Table lookup, masked to 6 bits so the bounds check
/// folds away; card bytes are always 0..=51 by construction.
#[inline(always)]
fn rank_of(card: u8) -> u8 {
    RANKS[(card & 63) as usize]
}

// Tiebreaker kinds, ordered so `tb <= TB_FORFEIT` means "play 4 cards".
const TB_DEFAULT: u8 = 0;
const TB_FORFEIT: u8 = 1;
const TB_MODIFIED: u8 = 2;
const TB_MOD_FORFEIT: u8 = 3;
const TB_DRAW: u8 = 4;

const TB_NAMES: [&str; 5] = [
    "Default",
    "Forfeit",
    "Modified",
    "Modified Forfeit",
    "Draw",
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Config {
    pub num_players: u32,
    pub num_decks: u32,
    /// `u64::MAX` means "no cap", matching Python's `max_rounds=None`.
    pub max_rounds: u64,
}

impl Config {
    pub fn new(num_players: u32, num_decks: u32) -> Self {
        Config {
            num_players,
            num_decks,
            max_rounds: u64::MAX,
        }
    }

    pub fn validate(&self) -> Result<(), &'static str> {
        if self.num_players < 2 {
            return Err("War needs at least 2 players");
        }
        if self.num_decks < 1 {
            return Err("War needs at least 1 deck");
        }
        if self.num_decks * 52 < self.num_players {
            return Err("not enough cards for that many players");
        }
        // The checkpoint format stores card counts as u16, so a shoe has to
        // fit in 65,535 cards. Catch it here rather than at save() time.
        if self.num_decks > 1260 {
            return Err("at most 1260 decks (65,520 cards)");
        }
        if self.num_players > 65535 {
            return Err("at most 65535 players");
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug)]
pub(crate) struct Player {
    pub(crate) head: u32,
    pub(crate) dcount: u32,
    pub(crate) rcount: u32,
    pub(crate) wins: u32,
    /// Round the player went out, or -1 while still in.
    pub(crate) round_out: i32,
    pub(crate) in_game: bool,
}

impl Player {
    #[inline(always)]
    fn card_count(&self) -> u32 {
        self.dcount + self.rcount
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Summary {
    pub num_players: u32,
    pub num_decks: u32,
    pub seed: u64,
    pub completed: bool,
    pub rounds: u32,
    pub wars: u64,
    pub deepest_war: u32,
    pub biggest_pot: u32,
    pub winner: Option<u32>,
    pub standings: Vec<u32>,
    pub eliminations: u32,
    /// Final card count per player, in id order.
    pub card_counts: Vec<u32>,
    /// Round each player went out, -1 if still in. Id order.
    pub round_out: Vec<i32>,
}

pub struct WarGame<R: GameRng = Xoshiro256ss, S: EventSink = NullSink> {
    pub(crate) cfg: Config,
    pub(crate) seed: u64,
    pub(crate) rng: R,
    pub sink: S,

    pub(crate) cap: usize,
    pub(crate) buf: Vec<u8>,
    pub(crate) players: Vec<Player>,
    pub(crate) table: Vec<u8>,

    pub(crate) round: u32,
    pub(crate) war_count: u64,
    pub(crate) deepest_war: u32,
    pub(crate) biggest_pot: u32,
    pub(crate) winner: Option<u32>,
    pub(crate) is_over: bool,
    pub(crate) started: bool,
    pub(crate) alive: u32,

    // Scratch, reused every round so the hot loop never allocates.
    pub(crate) active: Vec<u32>,
    active_dirty: bool,
    ir_p: Vec<u32>,
    ir_r: Vec<u8>,
    cont: Vec<u32>,
    order: Vec<u32>,
    ev_ids: Vec<u32>,
    ev_pairs: Vec<(u32, u32)>,
}

impl<R: GameRng> WarGame<R, NullSink> {
    pub fn new(cfg: Config, rng: R, seed: u64) -> Self {
        Self::with_sink(cfg, rng, seed, NullSink)
    }
}

impl<R: GameRng, S: EventSink> WarGame<R, S> {
    pub fn with_sink(cfg: Config, rng: R, seed: u64, sink: S) -> Self {
        cfg.validate().expect("invalid War config");
        let np = cfg.num_players as usize;
        let cap = cfg.num_decks as usize * 52;
        WarGame {
            cfg,
            seed,
            rng,
            sink,
            cap,
            buf: vec![0u8; np * cap],
            players: vec![
                Player {
                    head: 0,
                    dcount: 0,
                    rcount: 0,
                    wins: 0,
                    round_out: -1,
                    in_game: true,
                };
                np
            ],
            table: Vec::with_capacity(cap),
            round: 0,
            war_count: 0,
            deepest_war: 0,
            biggest_pot: 0,
            winner: None,
            is_over: false,
            started: false,
            alive: cfg.num_players,
            active: (0..cfg.num_players).collect(),
            active_dirty: false,
            ir_p: Vec::with_capacity(np),
            ir_r: Vec::with_capacity(np),
            cont: Vec::with_capacity(np),
            order: Vec::with_capacity(np),
            ev_ids: Vec::with_capacity(np),
            ev_pairs: Vec::with_capacity(np),
        }
    }

    pub fn round(&self) -> u32 {
        self.round
    }
    pub fn is_over(&self) -> bool {
        self.is_over
    }
    pub fn config(&self) -> Config {
        self.cfg
    }

    // ------------------------------------------------------------- setup

    pub fn start(&mut self) {
        debug_assert!(!self.started);
        self.started = true;
        if S::ENABLED {
            self.sink.emit(Event::GameStarted {
                round: 0,
                num_players: self.cfg.num_players,
                num_decks: self.cfg.num_decks,
                seed: self.seed,
            });
        }
        let mut shoe = build_shoe(self.cfg.num_decks);
        shuffle_slice(&mut self.rng, &mut shoe);
        let np = self.cfg.num_players as usize;
        let cap = self.cap;
        {
            let (buf, players) = (&mut self.buf, &mut self.players);
            for (i, &card) in shoe.iter().enumerate() {
                let pi = i % np;
                let p = &mut players[pi];
                buf[pi * cap + p.dcount as usize] = card;
                p.dcount += 1;
            }
        }
        if S::ENABLED {
            self.fill_card_counts();
            let pairs = core::mem::take(&mut self.ev_pairs);
            self.sink.emit(Event::CardsDealt {
                round: 0,
                card_counts: &pairs,
            });
            self.ev_pairs = pairs;
        }
    }

    // ------------------------------------------------------ card motion

    #[inline(always)]
    fn reshuffle(
        players: &mut [Player],
        buf: &mut [u8],
        rng: &mut R,
        cap: usize,
        pi: usize,
    ) {
        let (head, n) = {
            let p = &players[pi];
            (p.head as usize, p.rcount as usize)
        };
        if n > 1 {
            let base = pi * cap;
            if head + n <= cap {
                // Contiguous: shuffle the slice directly.
                let ptr = unsafe { buf.as_mut_ptr().add(base + head) };
                rng.shuffle_with(n, |i, j| {
                    if i != j {
                        unsafe { core::ptr::swap(ptr.add(i), ptr.add(j)) }
                    }
                });
            } else {
                // Wraps the ring: same swap sequence, indices folded.
                let ptr = unsafe { buf.as_mut_ptr().add(base) };
                rng.shuffle_with(n, |i, j| {
                    if i != j {
                        let mut a = head + i;
                        if a >= cap {
                            a -= cap;
                        }
                        let mut b = head + j;
                        if b >= cap {
                            b -= cap;
                        }
                        unsafe { core::ptr::swap(ptr.add(a), ptr.add(b)) }
                    }
                });
            }
        }
        let p = &mut players[pi];
        p.dcount = p.rcount;
        p.rcount = 0;
    }

    #[inline(always)]
    fn draw_from(
        players: &mut [Player],
        buf: &mut [u8],
        rng: &mut R,
        cap: usize,
        pi: usize,
    ) -> u8 {
        if players[pi].dcount == 0 {
            Self::reshuffle(players, buf, rng, cap, pi);
        }
        let p = &mut players[pi];
        debug_assert!(p.dcount > 0, "player {} has no cards to draw", pi + 1);
        let card = unsafe { *buf.get_unchecked(pi * cap + p.head as usize) };
        p.head += 1;
        if p.head as usize == cap {
            p.head = 0;
        }
        p.dcount -= 1;
        card
    }

    #[inline(always)]
    fn draw(&mut self, pi: usize) -> u8 {
        Self::draw_from(
            &mut self.players,
            &mut self.buf,
            &mut self.rng,
            self.cap,
            pi,
        )
    }

    /// Put one card at the back of a player's reserve.
    #[inline(always)]
    fn give(&mut self, pi: usize, card: u8) {
        let cap = self.cap;
        let (buf, players) = (&mut self.buf, &mut self.players);
        let p = &mut players[pi];
        let mut k = p.head as usize + p.dcount as usize + p.rcount as usize;
        if k >= cap {
            k -= cap;
        }
        unsafe { *buf.get_unchecked_mut(pi * cap + k) = card };
        p.rcount += 1;
    }

    // ---------------------------------------------------------- helpers

    fn fill_card_counts(&mut self) {
        self.ev_pairs.clear();
        for (i, p) in self.players.iter().enumerate() {
            if p.in_game {
                self.ev_pairs.push((i as u32 + 1, p.card_count()));
            }
        }
    }

    #[inline]
    fn eliminate(&mut self, pi: usize, reason: &'static str) {
        if !self.players[pi].in_game {
            return;
        }
        self.players[pi].in_game = false;
        self.players[pi].round_out = self.round as i32;
        self.alive -= 1;
        self.active_dirty = true;
        if S::ENABLED {
            self.sink.emit(Event::PlayerEliminated {
                round: self.round,
                player: pi as u32 + 1,
                reason,
            });
        }
    }

    // ------------------------------------------------------------- play

    pub fn play_round(&mut self) {
        if !self.started {
            self.start();
        }
        debug_assert!(!self.is_over);
        self.round += 1;
        let rnd = self.round;

        if S::ENABLED {
            self.ev_ids.clear();
            for k in 0..self.active.len() {
                self.ev_ids.push(self.active[k] + 1);
            }
            let ids = core::mem::take(&mut self.ev_ids);
            self.sink.emit(Event::RoundStarted {
                round: rnd,
                players: &ids,
            });
            self.ev_ids = ids;
        }

        self.ir_p.clear();
        self.ir_r.clear();
        for k in 0..self.active.len() {
            let pi = self.active[k] as usize;
            let card = self.draw(pi);
            self.table.push(card);
            self.ir_p.push(pi as u32);
            self.ir_r.push(rank_of(card));
            if S::ENABLED {
                self.sink.emit(Event::CardPlayed {
                    round: rnd,
                    player: pi as u32 + 1,
                    card,
                    face_up: true,
                });
            }
        }

        // ---- resolve, fighting wars until somebody is alone at the top
        let mut via: &'static str = "high_card";
        let mut depth: u32 = 0;
        let win_pi: usize;

        loop {
            let mut highest = 0u8;
            for &r in self.ir_r.iter() {
                if r > highest {
                    highest = r;
                }
            }
            self.cont.clear();
            for k in 0..self.ir_p.len() {
                if self.ir_r[k] == highest {
                    self.cont.push(self.ir_p[k]);
                }
            }
            if self.cont.len() == 1 {
                win_pi = self.cont[0] as usize;
                break;
            }

            depth += 1;
            self.war_count += 1;
            if depth > self.deepest_war {
                self.deepest_war = depth;
            }

            let mut with4 = 0u32;
            let mut with1 = 0u32;
            for k in 0..self.cont.len() {
                let c = self.players[self.cont[k] as usize].card_count();
                if c >= 4 {
                    with4 += 1;
                }
                if c >= 1 {
                    with1 += 1;
                }
            }
            let tb = if with4 >= 2 {
                TB_DEFAULT
            } else if with4 == 1 {
                TB_FORFEIT
            } else if with1 >= 2 {
                TB_MODIFIED
            } else if with1 == 1 {
                TB_MOD_FORFEIT
            } else {
                TB_DRAW
            };

            if S::ENABLED {
                self.ev_ids.clear();
                for k in 0..self.cont.len() {
                    self.ev_ids.push(self.cont[k] + 1);
                }
                let ids = core::mem::take(&mut self.ev_ids);
                self.sink.emit(Event::WarDeclared {
                    round: rnd,
                    players: &ids,
                    rank: highest,
                    depth,
                    tiebreaker: TB_NAMES[tb as usize],
                });
                self.ev_ids = ids;
            }

            if tb == TB_DRAW {
                self.split_table();
                return self.finish_round(rnd, None, via);
            }

            via = if tb == TB_FORFEIT || tb == TB_MOD_FORFEIT {
                "forfeit"
            } else {
                "war"
            };

            self.ir_p.clear();
            self.ir_r.clear();
            for ci in 0..self.cont.len() {
                let pi = self.cont[ci] as usize;
                let count = self.players[pi].card_count();
                let (survives, to_play) = if tb <= TB_FORFEIT {
                    (count >= 4, if count >= 4 { 4 } else { count })
                } else {
                    (count >= 1, count)
                };
                let mut last = 0u8;
                for i in 0..to_play {
                    let card = self.draw(pi);
                    self.table.push(card);
                    last = card;
                    if S::ENABLED {
                        self.sink.emit(Event::CardPlayed {
                            round: rnd,
                            player: pi as u32 + 1,
                            card,
                            face_up: survives && i == to_play - 1,
                        });
                    }
                }
                if survives {
                    self.ir_p.push(pi as u32);
                    self.ir_r.push(rank_of(last));
                } else {
                    self.eliminate(pi, "insufficient_for_war");
                }
            }
            if self.ir_p.len() == 1 {
                win_pi = self.ir_p[0] as usize;
                break;
            }
        }

        self.finish_round(rnd, Some(win_pi), via)
    }

    fn finish_round(&mut self, rnd: u32, win_pi: Option<usize>, via: &'static str) {
        if let Some(w) = win_pi {
            let pot = self.table.len() as u32;
            if pot > self.biggest_pot {
                self.biggest_pot = pot;
            }
            for k in 0..self.table.len() {
                let card = self.table[k];
                self.give(w, card);
            }
            self.table.clear();
            self.players[w].wins += 1;
            if S::ENABLED {
                self.sink.emit(Event::RoundWon {
                    round: rnd,
                    winner: w as u32 + 1,
                    cards_won: pot,
                    via,
                });
            }
        }

        // Anyone who ended the round holding nothing is out. Iterates the
        // round's original active list, exactly like the Python.
        for k in 0..self.active.len() {
            let pi = self.active[k] as usize;
            let p = &self.players[pi];
            if p.in_game && p.card_count() == 0 {
                self.eliminate(pi, "out_of_cards");
            }
        }

        if S::ENABLED {
            self.fill_card_counts();
            let pairs = core::mem::take(&mut self.ev_pairs);
            self.sink.emit(Event::RoundEnded {
                round: rnd,
                card_counts: &pairs,
            });
            self.ev_pairs = pairs;
        }

        if self.active_dirty {
            let (active, players) = (&mut self.active, &self.players);
            active.retain(|&pi| players[pi as usize].in_game);
            self.active_dirty = false;
        }

        if self.alive <= 1 {
            self.is_over = true;
            self.winner = if self.alive == 1 {
                Some(self.active[0] + 1)
            } else {
                None
            };
            if S::ENABLED {
                self.sink.emit(Event::GameOver {
                    round: rnd,
                    winner: self.winner,
                    total_rounds: rnd,
                });
            }
        }
    }

    /// Drawn war: split the table evenly between the tied players, then hand
    /// the remainder out in a shuffled order, at most one card each.
    fn split_table(&mut self) {
        let n = self.cont.len();
        let total = self.table.len();
        let per = total / n;
        let mut index = 0usize;
        for ci in 0..n {
            let pi = self.cont[ci] as usize;
            for k in 0..per {
                let card = self.table[index + k];
                self.give(pi, card);
            }
            index += per;
        }
        let leftovers = total - index;

        self.order.clear();
        for k in 0..n {
            self.order.push(self.cont[k]);
        }
        let mut order = core::mem::take(&mut self.order);
        shuffle_slice(&mut self.rng, &mut order);

        let handed = leftovers.min(n);
        for k in 0..handed {
            let pi = order[k] as usize;
            let card = self.table[index + k];
            self.give(pi, card);
        }
        self.table.clear();

        if S::ENABLED {
            self.ev_ids.clear();
            self.ev_pairs.clear();
            for k in 0..n {
                self.ev_ids.push(self.cont[k] + 1);
                self.ev_pairs.push((self.cont[k] + 1, per as u32));
            }
            for k in 0..handed {
                let pid = order[k] + 1;
                for e in self.ev_pairs.iter_mut() {
                    if e.0 == pid {
                        e.1 += 1;
                    }
                }
            }
            let ids = core::mem::take(&mut self.ev_ids);
            let pairs = core::mem::take(&mut self.ev_pairs);
            self.sink.emit(Event::RoundDrawn {
                round: self.round,
                players: &ids,
                cards_returned: &pairs,
            });
            self.ev_ids = ids;
            self.ev_pairs = pairs;
        }
        self.order = order;
    }

    /// Play to the end, or until the round cap. Returns rounds played here.
    pub fn run(&mut self) -> u32 {
        if !self.started {
            self.start();
        }
        let before = self.round;
        while !self.is_over && (self.round as u64) < self.cfg.max_rounds {
            self.play_round();
        }
        self.round - before
    }

    /// Advance at most `k` rounds. Used by the seek API.
    pub fn advance(&mut self, k: u32) -> u32 {
        if !self.started {
            self.start();
        }
        let before = self.round;
        while !self.is_over
            && (self.round - before) < k
            && (self.round as u64) < self.cfg.max_rounds
        {
            self.play_round();
        }
        self.round - before
    }

    // ------------------------------------------------------- inspection

    pub fn standings(&self) -> Vec<u32> {
        let mut alive: Vec<usize> = (0..self.players.len())
            .filter(|&i| self.players[i].in_game)
            .collect();
        // Stable sort, so equal card counts stay in id order -- Python's
        // sorted() has the same guarantee and the parity tests rely on it.
        alive.sort_by(|&a, &b| {
            self.players[b]
                .card_count()
                .cmp(&self.players[a].card_count())
        });
        let mut out: Vec<usize> = (0..self.players.len())
            .filter(|&i| !self.players[i].in_game)
            .collect();
        out.sort_by(|&a, &b| {
            self.players[b]
                .round_out
                .cmp(&self.players[a].round_out)
                .then(a.cmp(&b))
        });
        alive
            .into_iter()
            .chain(out)
            .map(|i| i as u32 + 1)
            .collect()
    }

    pub fn summary(&self) -> Summary {
        Summary {
            num_players: self.cfg.num_players,
            num_decks: self.cfg.num_decks,
            seed: self.seed,
            completed: self.is_over,
            rounds: self.round,
            wars: self.war_count,
            deepest_war: self.deepest_war,
            biggest_pot: self.biggest_pot,
            winner: self.winner,
            standings: self.standings(),
            eliminations: self.players.iter().filter(|p| !p.in_game).count() as u32,
            card_counts: self.players.iter().map(|p| p.card_count()).collect(),
            round_out: self.players.iter().map(|p| p.round_out).collect(),
        }
    }
}

/// One-shot: run a game to completion with the v2 RNG and no events.
pub fn simulate(cfg: Config, seed: u64) -> Summary {
    let mut g = WarGame::new(cfg, Xoshiro256ss::from_seed(seed), seed);
    g.run();
    g.summary()
}
