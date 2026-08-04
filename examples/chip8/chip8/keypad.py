"""16-key hex keypad (0-F).

The original CHIP-8 used a 4x4 keypad. Key state is tracked here; the
EX9E/EXA1 skip tests and FX0A wait read from it.
"""

KEYS = tuple("0123456789ABCDEF")


class Keypad:
    def __init__(self):
        self._pressed = set()

    def press(self, key):
        """Record a press. Accepts a hex char '0'-'F' or int 0-15."""
        self._pressed.add(self._norm(key))

    def release(self, key):
        self._pressed.discard(self._norm(key))

    def is_pressed(self, key) -> bool:
        return self._norm(key) in self._pressed

    def any_pressed(self):
        """First pressed key (for FX0A storage), or None."""
        for k in range(16):
            if k in self._pressed:
                return k
        return None

    def clear(self):
        self._pressed.clear()

    @staticmethod
    def _norm(key):
        if isinstance(key, int):
            return key & 0xF
        if isinstance(key, str):
            return KEYS.index(key.upper())
        raise TypeError(f"key must be int or hex char, got {type(key)}")