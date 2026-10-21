"""Java LCG chunk seeding for mineshaft layouts."""

MASK = (1 << 48) - 1
A = 0x5DEECE66D
B = 11


def mineshaft_seed(seed, cx, cz):
    s = (seed ^ A) & MASK

    def bits(n):
        nonlocal s
        s = (s * A + B) & MASK
        return s >> (48 - n)

    def long():
        hi = bits(32)
        lo = bits(32)
        if lo >= 1 << 31:
            lo -= 1 << 32
        return (hi << 32) + lo

    a = long()
    b = long()
    return (seed ^ (cx * a) ^ (cz * b)) & MASK
