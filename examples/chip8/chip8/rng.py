"""Deterministic RNG for the CXNN opcode.

CHIP-8 lacks a hardware RNG; the CXNN instruction sets Vx = random & NN. We use a
seeded PRNG (Python's random with a fixed seed, or injectable source) so ROM
runs are reproducible — a requirement for replayable proofs.
"""

import random


class RNG:
    def __init__(self, seed=None, source=None):
        self._source = source if source is not None else \
            random.Random(seed)

    def next_byte(self) -> int:
        """Return a random byte in [0, 255]."""
        return self._source.randrange(256)