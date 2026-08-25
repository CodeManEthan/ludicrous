"""Independent Python re-implementation of the v2 RNG.

Written from the algorithm description, not translated from the Rust, so
that agreeing on the golden vectors actually proves something. This is also
the file to copy from when the same seed namespace is needed in JS.

    python3 v2_rng_reference.py            # print the golden vectors
"""
M64 = (1 << 64) - 1


def splitmix64(state):
    """Generator of the SplitMix64 stream starting from `state`."""
    while True:
        state = (state + 0x9E3779B97F4A7C15) & M64
        z = state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M64
        yield z ^ (z >> 31)


def rotl(x, k):
    return ((x << k) | (x >> (64 - k))) & M64


class Xoshiro256ss:
    def __init__(self, seed):
        sm = splitmix64(seed)
        self.s = [next(sm) for _ in range(4)]

    def next_u64(self):
        s = self.s
        result = (rotl((s[1] * 5) & M64, 7) * 9) & M64
        t = (s[1] << 17) & M64
        s[2] ^= s[0]
        s[3] ^= s[1]
        s[1] ^= s[2]
        s[0] ^= s[3]
        s[2] ^= t
        s[3] = rotl(s[3], 45)
        return result

    def bounded(self, n):
        """Lemire: multiply into 128 bits, take the high half, reject on the
        low half falling inside the biased zone."""
        x = self.next_u64()
        m = x * n
        low = m & M64
        if low < n:
            threshold = (-n) % n
            while low < threshold:
                x = self.next_u64()
                m = x * n
                low = m & M64
        return m >> 64

    def shuffle(self, xs):
        """Forward Fisher-Yates."""
        n = len(xs)
        for i in range(n - 1):
            j = i + self.bounded(n - i)
            xs[i], xs[j] = xs[j], xs[i]


if __name__ == "__main__":
    for seed in (0, 1, 42):
        r = Xoshiro256ss(seed)
        print(f"raw[{seed}] = {[r.next_u64() for _ in range(8)]}")
    for seed in (0, 1, 42):
        r = Xoshiro256ss(seed)
        deck = list(range(52))
        r.shuffle(deck)
        print(f"deck[{seed}] = {deck}")
