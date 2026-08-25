//! Golden vectors for both random sources.
//!
//! The v2 numbers were produced by `oracle/v2_rng_reference.py`, an
//! independent Python implementation written from the algorithm rather than
//! transcribed from this crate -- two implementations agreeing is evidence,
//! one implementation agreeing with itself is not. The CPython numbers come
//! straight out of `random.Random` on the machine.
//!
//! If a change here ever needs these updated, the v2 seed namespace has
//! moved and every stored seed in the product just changed meaning.

use ludicrous_core::cards::build_shoe;
use ludicrous_core::rng::{shuffle_slice, GameRng, Xoshiro256ss};

const RAW_0: [u64; 8] = [
    11091344671253066420,
    13793997310169335082,
    1900383378846508768,
    7684712102626143532,
    13521403990117723737,
    18442103541295991498,
    7788427924976520344,
    9881088229871127103,
];
const RAW_1: [u64; 8] = [
    12966619160104079557,
    9600361134598540522,
    10590380919521690900,
    7218738570589545383,
    12860671823995680371,
    2648436617965840162,
    1310552918490157286,
    7031611932980406429,
];
const RAW_42: [u64; 8] = [
    1546998764402558742,
    6990951692964543102,
    12544586762248559009,
    17057574109182124193,
    18295552978065317476,
    14199186830065750584,
    13267978908934200754,
    15679888225317814407,
];

const DECK_0: [u8; 52] = [
    31, 39, 7, 23, 1, 51, 25, 0, 45, 48, 14, 13, 16, 38, 32, 6, 41, 3, 36, 20, 29, 18, 2, 12, 5,
    33, 42, 49, 24, 27, 15, 37, 47, 21, 28, 34, 50, 4, 17, 44, 9, 30, 26, 22, 11, 43, 10, 35, 46,
    40, 19, 8,
];
const DECK_1: [u8; 52] = [
    36, 27, 30, 22, 37, 11, 9, 24, 46, 32, 49, 50, 10, 39, 0, 47, 18, 34, 19, 21, 17, 14, 40, 33,
    35, 2, 16, 48, 8, 51, 25, 12, 3, 6, 45, 13, 7, 31, 43, 20, 41, 23, 28, 1, 42, 38, 4, 44, 29, 5,
    15, 26,
];
const DECK_42: [u8; 52] = [
    4, 20, 36, 48, 51, 41, 39, 45, 5, 34, 38, 22, 44, 25, 8, 47, 10, 46, 42, 18, 11, 26, 35, 40,
    32, 16, 2, 17, 43, 9, 6, 12, 49, 50, 3, 15, 29, 37, 31, 0, 27, 21, 33, 19, 30, 7, 24, 23, 13,
    14, 1, 28,
];

#[test]
fn v2_raw_outputs() {
    for (seed, want) in [(0u64, RAW_0), (1, RAW_1), (42, RAW_42)] {
        let mut r = Xoshiro256ss::from_seed(seed);
        let got: Vec<u64> = (0..8).map(|_| r.next_u64()).collect();
        assert_eq!(got, want.to_vec(), "xoshiro256** raw stream, seed {}", seed);
    }
}

#[test]
fn v2_shuffled_deck() {
    for (seed, want) in [(0u64, DECK_0), (1, DECK_1), (42, DECK_42)] {
        let mut r = Xoshiro256ss::from_seed(seed);
        let mut deck = build_shoe(1);
        assert_eq!(deck, (0..52u8).collect::<Vec<u8>>(), "unshuffled 0..51");
        shuffle_slice(&mut r, &mut deck);
        assert_eq!(deck, want.to_vec(), "v2 shuffle of 0..51, seed {}", seed);
    }
}

#[test]
fn v2_state_roundtrips() {
    let mut r = Xoshiro256ss::from_seed(1234);
    for _ in 0..100 {
        r.next_u64();
    }
    let bytes = r.to_bytes();
    assert_eq!(bytes.len(), 32);
    let mut r2 = Xoshiro256ss::from_bytes(&bytes);
    assert_eq!(r, r2);
    let a: Vec<u64> = (0..16).map(|_| r.next_u64()).collect();
    let b: Vec<u64> = (0..16).map(|_| r2.next_u64()).collect();
    assert_eq!(a, b);
}

#[test]
fn v2_bounded_is_in_range_and_uses_the_whole_range() {
    let mut r = Xoshiro256ss::from_seed(9);
    let mut seen = [0u32; 7];
    for _ in 0..70_000 {
        let v = r.bounded(7);
        assert!(v < 7);
        seen[v as usize] += 1;
    }
    // 10k expected per bucket; a wide band is enough to catch a broken bound.
    for (i, &c) in seen.iter().enumerate() {
        assert!(c > 9_000 && c < 11_000, "bucket {} had {}", i, c);
    }
}

// ------------------------------------------------------- CPython oracle

#[cfg(feature = "cpython-rng")]
mod cpython {
    use ludicrous_core::mt19937::CPythonRng;
    use ludicrous_core::rng::shuffle_slice;

    #[test]
    fn first_getrandbits_32_match_random_random() {
        let cases: [(u64, [u32; 4]); 3] = [
            (0, [3626764237, 1654615998, 3255389356, 3823568514]),
            (1, [577090037, 2444712010, 3639700191, 3445702192]),
            // The anchor quoted in the port brief.
            (42, [2746317213, 478163327, 107420369, 3184935163]),
        ];
        for (seed, want) in cases {
            let mut r = CPythonRng::seeded(seed);
            let got: Vec<u32> = (0..4).map(|_| r.getrandbits(32)).collect();
            assert_eq!(got, want.to_vec(), "random.Random({}).getrandbits(32)", seed);
        }
    }

    #[test]
    fn shuffle_matches_random_shuffle() {
        let cases: [(u64, [u8; 52]); 3] = [
            (
                0,
                [
                    28, 12, 45, 41, 38, 7, 5, 36, 1, 49, 33, 0, 4, 35, 20, 14, 51, 29, 34, 44, 39,
                    11, 42, 17, 15, 10, 21, 27, 50, 23, 3, 43, 9, 47, 6, 40, 18, 8, 46, 13, 37, 22,
                    30, 19, 25, 31, 32, 16, 2, 26, 48, 24,
                ],
            ),
            (
                1,
                [
                    49, 9, 37, 22, 2, 38, 19, 11, 35, 5, 29, 51, 43, 15, 23, 46, 47, 21, 40, 39,
                    12, 50, 32, 20, 25, 26, 34, 10, 33, 3, 18, 14, 17, 44, 0, 27, 42, 1, 45, 6, 13,
                    24, 41, 30, 28, 31, 7, 16, 4, 48, 36, 8,
                ],
            ),
            (
                42,
                [
                    9, 23, 25, 3, 21, 38, 16, 39, 19, 11, 46, 24, 33, 29, 31, 43, 4, 28, 10, 26,
                    36, 0, 44, 18, 42, 50, 35, 48, 30, 20, 22, 12, 51, 32, 45, 13, 41, 49, 2, 27,
                    37, 5, 34, 6, 8, 14, 15, 17, 47, 1, 7, 40,
                ],
            ),
        ];
        for (seed, want) in cases {
            let mut r = CPythonRng::seeded(seed);
            let mut deck: Vec<u8> = (0..52).collect();
            shuffle_slice(&mut r, &mut deck);
            assert_eq!(deck, want.to_vec(), "random.Random({}).shuffle", seed);
        }
    }
}
