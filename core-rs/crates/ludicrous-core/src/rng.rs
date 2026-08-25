//! The v2 seed namespace: xoshiro256** seeded through SplitMix64, Lemire
//! bounded ints, forward Fisher-Yates.
//!
//! Written out by hand on purpose. Every line here has to be portable to JS,
//! Go, or whatever the engine is rewritten in next, without dragging a crate
//! along for the ride. ~60 lines of arithmetic, no dependencies.

/// What the game engine needs from a random source.
///
/// Generic, not a trait object: the shuffle order differs between the v2
/// generator (forward Fisher-Yates) and the CPython oracle (reversed), and
/// both need to inline into the hot loop.
pub trait GameRng: Clone {
    fn next_u64(&mut self) -> u64;

    /// Uniform in `[0, n)`. Panics on `n == 0`.
    fn bounded(&mut self, n: u64) -> u64;

    /// Emit the swap sequence for shuffling `n` items, calling
    /// `swap(i, j)` for each. The callback must tolerate `i == j`.
    fn shuffle_with<F: FnMut(usize, usize)>(&mut self, n: usize, swap: F);
}

/// SplitMix64 — the standard seeding companion for xoshiro. A 64-bit seed
/// goes in, four well-mixed words come out, so seed 0 and seed 1 give
/// unrelated streams.
#[derive(Clone, Copy)]
pub struct SplitMix64(pub u64);

impl SplitMix64 {
    #[inline]
    pub fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }
}

/// xoshiro256** — 256 bits of state, four words, no multiply-heavy step.
/// Small enough that the whole state fits in a checkpoint header.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Xoshiro256ss {
    s: [u64; 4],
}

impl Xoshiro256ss {
    pub fn from_seed(seed: u64) -> Self {
        let mut sm = SplitMix64(seed);
        Xoshiro256ss {
            s: [sm.next(), sm.next(), sm.next(), sm.next()],
        }
    }

    /// The 32 raw state bytes, little-endian per word. This is what goes
    /// into a checkpoint.
    pub fn to_bytes(&self) -> [u8; 32] {
        let mut out = [0u8; 32];
        for (i, w) in self.s.iter().enumerate() {
            out[i * 8..i * 8 + 8].copy_from_slice(&w.to_le_bytes());
        }
        out
    }

    pub fn from_bytes(b: &[u8; 32]) -> Self {
        let mut s = [0u64; 4];
        for (i, w) in s.iter_mut().enumerate() {
            let mut buf = [0u8; 8];
            buf.copy_from_slice(&b[i * 8..i * 8 + 8]);
            *w = u64::from_le_bytes(buf);
        }
        Xoshiro256ss { s }
    }
}

impl GameRng for Xoshiro256ss {
    #[inline]
    fn next_u64(&mut self) -> u64 {
        let result = self.s[1].wrapping_mul(5).rotate_left(7).wrapping_mul(9);
        let t = self.s[1] << 17;
        self.s[2] ^= self.s[0];
        self.s[3] ^= self.s[1];
        self.s[1] ^= self.s[2];
        self.s[0] ^= self.s[3];
        self.s[2] ^= t;
        self.s[3] = self.s[3].rotate_left(45);
        result
    }

    /// Lemire's multiply-shift with rejection. One multiply in the common
    /// case; the rejection branch almost never runs for the small bounds a
    /// card game asks for.
    #[inline]
    fn bounded(&mut self, n: u64) -> u64 {
        debug_assert!(n > 0);
        let mut x = self.next_u64();
        let mut m = (x as u128) * (n as u128);
        let mut l = m as u64;
        if l < n {
            let t = n.wrapping_neg() % n;
            while l < t {
                x = self.next_u64();
                m = (x as u128) * (n as u128);
                l = m as u64;
            }
        }
        let _ = x;
        (m >> 64) as u64
    }

    /// Forward Fisher-Yates: walk `i` up from 0, swap with a uniform pick
    /// from the untouched tail. The forward direction is the one that
    /// streams cleanly and ports without off-by-one arguments.
    #[inline]
    fn shuffle_with<F: FnMut(usize, usize)>(&mut self, n: usize, mut swap: F) {
        if n < 2 {
            return;
        }
        for i in 0..n - 1 {
            let j = i + self.bounded((n - i) as u64) as usize;
            swap(i, j);
        }
    }
}

/// Convenience: shuffle a slice in place with the v2 algorithm.
pub fn shuffle_slice<T, R: GameRng>(rng: &mut R, xs: &mut [T]) {
    let n = xs.len();
    let p = xs.as_mut_ptr();
    rng.shuffle_with(n, |i, j| {
        if i != j {
            // SAFETY: i and j are both < n and distinct.
            unsafe { core::ptr::swap(p.add(i), p.add(j)) }
        }
    });
}
