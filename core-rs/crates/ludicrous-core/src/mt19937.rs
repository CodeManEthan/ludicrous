//! CPython's `random.Random`, for parity testing only.
//!
//! The shipping engine uses the v2 xoshiro namespace; this exists so the
//! Rust rules can be proved identical to `engine/war.py` on the *same*
//! games, seed for seed, before the seed namespace changes underneath the
//! product. Feature-gated (`cpython-rng`) and never compiled into the wasm
//! bundle or the batch runner.
//!
//! Reproduced pieces, from `_randommodule.c` and `Lib/random.py`:
//!   * MT19937 with `init_by_array` seeding (`random.seed(int)` turns the
//!     absolute value into 32-bit little-endian words; zero seeds one word)
//!   * `getrandbits(k)` for k <= 32 = one 32-bit draw shifted right 32-k
//!   * `_randbelow_with_getrandbits`: bit_length + reject-and-retry
//!   * `shuffle`: reversed Fisher-Yates, `for i in reversed(range(1, n))`
//!
//! Anchor: `random.Random(42)` yields 2746317213, 478163327, 107420369,
//! 3184935163 as its first four 32-bit draws (see the golden test).

use crate::rng::GameRng;

const N: usize = 624;
const M: usize = 397;
const MATRIX_A: u32 = 0x9908_b0df;
const UPPER_MASK: u32 = 0x8000_0000;
const LOWER_MASK: u32 = 0x7fff_ffff;

#[derive(Clone)]
pub struct CPythonRng {
    mt: [u32; N],
    mti: usize,
}

impl CPythonRng {
    fn init_genrand(&mut self, s: u32) {
        self.mt[0] = s;
        for i in 1..N {
            let prev = self.mt[i - 1];
            self.mt[i] = 1812433253u32
                .wrapping_mul(prev ^ (prev >> 30))
                .wrapping_add(i as u32);
        }
        self.mti = N;
    }

    fn init_by_array(&mut self, key: &[u32]) {
        self.init_genrand(19650218);
        let mut i = 1usize;
        let mut j = 0usize;
        let mut k = N.max(key.len());
        while k > 0 {
            let prev = self.mt[i - 1];
            self.mt[i] = (self.mt[i] ^ (prev ^ (prev >> 30)).wrapping_mul(1664525))
                .wrapping_add(key[j])
                .wrapping_add(j as u32);
            i += 1;
            j += 1;
            if i >= N {
                self.mt[0] = self.mt[N - 1];
                i = 1;
            }
            if j >= key.len() {
                j = 0;
            }
            k -= 1;
        }
        k = N - 1;
        while k > 0 {
            let prev = self.mt[i - 1];
            self.mt[i] = (self.mt[i] ^ (prev ^ (prev >> 30)).wrapping_mul(1566083941))
                .wrapping_sub(i as u32);
            i += 1;
            if i >= N {
                self.mt[0] = self.mt[N - 1];
                i = 1;
            }
            k -= 1;
        }
        self.mt[0] = 0x8000_0000;
    }

    /// `random.Random(seed)` for a non-negative integer seed.
    pub fn seeded(seed: u64) -> Self {
        let mut r = CPythonRng {
            mt: [0; N],
            mti: N,
        };
        let key: Vec<u32> = if seed == 0 {
            vec![0]
        } else if seed < 0x1_0000_0000 {
            vec![seed as u32]
        } else {
            vec![seed as u32, (seed >> 32) as u32]
        };
        r.init_by_array(&key);
        r
    }

    pub fn genrand_u32(&mut self) -> u32 {
        if self.mti >= N {
            for kk in 0..N - M {
                let y = (self.mt[kk] & UPPER_MASK) | (self.mt[kk + 1] & LOWER_MASK);
                self.mt[kk] = self.mt[kk + M] ^ (y >> 1) ^ if y & 1 != 0 { MATRIX_A } else { 0 };
            }
            for kk in N - M..N - 1 {
                let y = (self.mt[kk] & UPPER_MASK) | (self.mt[kk + 1] & LOWER_MASK);
                self.mt[kk] =
                    self.mt[kk + M - N] ^ (y >> 1) ^ if y & 1 != 0 { MATRIX_A } else { 0 };
            }
            let y = (self.mt[N - 1] & UPPER_MASK) | (self.mt[0] & LOWER_MASK);
            self.mt[N - 1] = self.mt[M - 1] ^ (y >> 1) ^ if y & 1 != 0 { MATRIX_A } else { 0 };
            self.mti = 0;
        }
        let mut y = self.mt[self.mti];
        self.mti += 1;
        y ^= y >> 11;
        y ^= (y << 7) & 0x9d2c_5680;
        y ^= (y << 15) & 0xefc6_0000;
        y ^= y >> 18;
        y
    }

    /// `getrandbits(k)` for 0 <= k <= 32.
    #[inline]
    pub fn getrandbits(&mut self, k: u32) -> u32 {
        if k == 0 {
            return 0;
        }
        self.genrand_u32() >> (32 - k)
    }

    /// `Random._randbelow_with_getrandbits(n)`.
    #[inline]
    pub fn randbelow(&mut self, n: u32) -> u32 {
        let k = 32 - n.leading_zeros(); // n.bit_length()
        let mut v = self.getrandbits(k);
        while v >= n {
            v = self.getrandbits(k);
        }
        v
    }
}

impl GameRng for CPythonRng {
    #[inline]
    fn next_u64(&mut self) -> u64 {
        // Python's random() combines two draws (high 27 | low 26); the game
        // never calls it, so this is here only to satisfy the trait.
        ((self.genrand_u32() as u64) << 32) | self.genrand_u32() as u64
    }

    #[inline]
    fn bounded(&mut self, n: u64) -> u64 {
        self.randbelow(n as u32) as u64
    }

    /// `random.shuffle`: walk i down from n-1, swap with `randbelow(i+1)`.
    #[inline]
    fn shuffle_with<F: FnMut(usize, usize)>(&mut self, n: usize, mut swap: F) {
        if n < 2 {
            return;
        }
        for i in (1..n).rev() {
            let j = self.randbelow(i as u32 + 1) as usize;
            swap(i, j);
        }
    }
}
