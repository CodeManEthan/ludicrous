//! Card encoding.
//!
//! A card is one byte, 0..=51, laid out exactly the way `engine/cards.py`
//! builds a deck: suit-major, rank ascending inside a suit.
//!
//!   byte = suit_index * 13 + (rank - 2)
//!   suit_index: 0 Hearts, 1 Diamonds, 2 Clubs, 3 Spades
//!   rank:       2..=14 (Ace high)
//!
//! Multi-deck shoes repeat the same 52 bytes, which is fine -- War never
//! needs to tell two aces of spades apart.

pub const SUITS: [&str; 4] = ["Hearts", "Diamonds", "Clubs", "Spades"];

#[inline(always)]
pub fn rank(card: u8) -> u8 {
    (card % 13) + 2
}

#[inline(always)]
pub fn suit_index(card: u8) -> usize {
    (card / 13) as usize
}

#[inline(always)]
pub fn suit_name(card: u8) -> &'static str {
    SUITS[suit_index(card)]
}

/// The shoe in `build_shoe` order, before any shuffle.
pub fn build_shoe(num_decks: u32) -> Vec<u8> {
    let mut shoe = Vec::with_capacity(num_decks as usize * 52);
    for _ in 0..num_decks {
        for s in 0..4u8 {
            for r in 0..13u8 {
                shoe.push(s * 13 + r);
            }
        }
    }
    shoe
}
