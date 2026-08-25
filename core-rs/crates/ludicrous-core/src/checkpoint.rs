//! Compact game-state snapshots.
//!
//! Layout (little-endian throughout):
//!
//! ```text
//! offset  size  field
//!      0     4  magic "LUDW"
//!      4     1  format version (1)
//!      5     1  game id (0 = War)
//!      6     2  num_players
//!      8     2  num_decks
//!     10     8  max_rounds
//!     18     8  seed
//!     26    32  RNG state (xoshiro256**: four u64 words)
//!     58     4  round
//!     62     8  war_count
//!     70     4  deepest_war
//!     74     4  biggest_pot
//!     78     4  winner (0 = none)
//!     82     1  flags: bit0 is_over, bit1 started
//!     83     2  table length
//!     85     n  table cards, one byte each
//!  then per player, in id order, 11 bytes of metadata:
//!            1  in_game
//!            2  round_out + 1 (0 = still in)
//!            4  wins
//!            2  deck length
//!            2  reserve length
//!  then, per player in id order, deck cards then reserve cards, one byte
//!  each, in draw order.
//! ```
//!
//! The ring buffer is flattened on save and re-laid-out from `head = 0` on
//! restore, which is why a restored game is byte-identical to the original
//! but not necessarily bit-identical in its internal offsets. Play is
//! unaffected: only the order of the deck and reserve matters.

use crate::rng::Xoshiro256ss;
use crate::war::{Config, Player, WarGame};
use crate::events::EventSink;

pub const MAGIC: [u8; 4] = *b"LUDW";
pub const VERSION: u8 = 1;
pub const GAME_WAR: u8 = 0;
pub const HEADER_LEN: usize = 85;
pub const PLAYER_META_LEN: usize = 11;

#[derive(Debug)]
pub enum CheckpointError {
    BadMagic,
    BadVersion,
    Truncated,
    Inconsistent,
}

fn put_u16(v: &mut Vec<u8>, x: u16) {
    v.extend_from_slice(&x.to_le_bytes());
}
fn put_u32(v: &mut Vec<u8>, x: u32) {
    v.extend_from_slice(&x.to_le_bytes());
}
fn put_u64(v: &mut Vec<u8>, x: u64) {
    v.extend_from_slice(&x.to_le_bytes());
}

struct Reader<'a> {
    b: &'a [u8],
    at: usize,
}

impl<'a> Reader<'a> {
    fn take(&mut self, n: usize) -> Result<&'a [u8], CheckpointError> {
        if self.at + n > self.b.len() {
            return Err(CheckpointError::Truncated);
        }
        let s = &self.b[self.at..self.at + n];
        self.at += n;
        Ok(s)
    }
    fn u8(&mut self) -> Result<u8, CheckpointError> {
        Ok(self.take(1)?[0])
    }
    fn u16(&mut self) -> Result<u16, CheckpointError> {
        let s = self.take(2)?;
        Ok(u16::from_le_bytes([s[0], s[1]]))
    }
    fn u32(&mut self) -> Result<u32, CheckpointError> {
        let s = self.take(4)?;
        Ok(u32::from_le_bytes([s[0], s[1], s[2], s[3]]))
    }
    fn u64(&mut self) -> Result<u64, CheckpointError> {
        let s = self.take(8)?;
        let mut a = [0u8; 8];
        a.copy_from_slice(s);
        Ok(u64::from_le_bytes(a))
    }
}

impl<S: EventSink> WarGame<Xoshiro256ss, S> {
    /// Serialize the whole game. Cards are one byte each, so a 100-player
    /// 50-deck game snapshots in a few kilobytes.
    pub fn save(&self) -> Vec<u8> {
        let np = self.players.len();
        let mut out = Vec::with_capacity(HEADER_LEN + np * PLAYER_META_LEN + self.cap + 8);
        out.extend_from_slice(&MAGIC);
        out.push(VERSION);
        out.push(GAME_WAR);
        put_u16(&mut out, self.cfg.num_players as u16);
        put_u16(&mut out, self.cfg.num_decks as u16);
        put_u64(&mut out, self.cfg.max_rounds);
        put_u64(&mut out, self.seed);
        out.extend_from_slice(&self.rng.to_bytes());
        put_u32(&mut out, self.round);
        put_u64(&mut out, self.war_count);
        put_u32(&mut out, self.deepest_war);
        put_u32(&mut out, self.biggest_pot);
        put_u32(&mut out, self.winner.unwrap_or(0));
        let flags = (self.is_over as u8) | ((self.started as u8) << 1);
        out.push(flags);
        put_u16(&mut out, self.table.len() as u16);
        out.extend_from_slice(&self.table);
        debug_assert_eq!(out.len(), HEADER_LEN + self.table.len());

        for p in &self.players {
            out.push(p.in_game as u8);
            put_u16(&mut out, (p.round_out + 1) as u16);
            put_u32(&mut out, p.wins);
            put_u16(&mut out, p.dcount as u16);
            put_u16(&mut out, p.rcount as u16);
        }
        for (pi, p) in self.players.iter().enumerate() {
            let base = pi * self.cap;
            let n = (p.dcount + p.rcount) as usize;
            for k in 0..n {
                let mut idx = p.head as usize + k;
                if idx >= self.cap {
                    idx -= self.cap;
                }
                out.push(self.buf[base + idx]);
            }
        }
        out
    }

    /// Rebuild a game from a snapshot. The sink starts fresh -- a checkpoint
    /// carries state, not a recording.
    pub fn restore(bytes: &[u8], sink: S) -> Result<Self, CheckpointError> {
        let mut r = Reader { b: bytes, at: 0 };
        if r.take(4)? != MAGIC {
            return Err(CheckpointError::BadMagic);
        }
        if r.u8()? != VERSION {
            return Err(CheckpointError::BadVersion);
        }
        if r.u8()? != GAME_WAR {
            return Err(CheckpointError::BadVersion);
        }
        let num_players = r.u16()? as u32;
        let num_decks = r.u16()? as u32;
        let max_rounds = r.u64()?;
        let seed = r.u64()?;
        let mut rng_state = [0u8; 32];
        rng_state.copy_from_slice(r.take(32)?);
        let round = r.u32()?;
        let war_count = r.u64()?;
        let deepest_war = r.u32()?;
        let biggest_pot = r.u32()?;
        let winner_raw = r.u32()?;
        let flags = r.u8()?;
        let table_len = r.u16()? as usize;
        let table = r.take(table_len)?.to_vec();

        let cfg = Config {
            num_players,
            num_decks,
            max_rounds,
        };
        cfg.validate().map_err(|_| CheckpointError::Inconsistent)?;
        let mut g = WarGame::with_sink(cfg, Xoshiro256ss::from_bytes(&rng_state), seed, sink);
        g.round = round;
        g.war_count = war_count;
        g.deepest_war = deepest_war;
        g.biggest_pot = biggest_pot;
        g.winner = if winner_raw == 0 {
            None
        } else {
            Some(winner_raw)
        };
        g.is_over = flags & 1 != 0;
        g.started = flags & 2 != 0;
        g.table = table;

        let np = num_players as usize;
        let mut metas = Vec::with_capacity(np);
        for _ in 0..np {
            let in_game = r.u8()? != 0;
            let round_out = r.u16()? as i32 - 1;
            let wins = r.u32()?;
            let dcount = r.u16()? as u32;
            let rcount = r.u16()? as u32;
            metas.push(Player {
                head: 0,
                dcount,
                rcount,
                wins,
                round_out,
                in_game,
            });
        }
        let cap = g.cap;
        let mut alive = 0u32;
        g.active.clear();
        for (pi, m) in metas.iter().enumerate() {
            let n = (m.dcount + m.rcount) as usize;
            if n > cap {
                return Err(CheckpointError::Inconsistent);
            }
            let cards = r.take(n)?;
            g.buf[pi * cap..pi * cap + n].copy_from_slice(cards);
            g.players[pi] = *m;
            if m.in_game {
                alive += 1;
                g.active.push(pi as u32);
            }
        }
        g.alive = alive;
        Ok(g)
    }
}
