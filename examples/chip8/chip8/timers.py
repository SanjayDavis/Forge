"""Delay and sound timers, decrementing at 60 Hz.

Both are 8-bit countdown timers. tick() is called ~60 times per second; it
decrements nonzero timers by 1 and stops at 0. The delay timer gates
instruction timing; the sound timer beeps while nonzero (beep itself is
rendering-layer concern, not here).
"""


class Timers:
    def __init__(self):
        self.delay = 0
        self.sound = 0

    def tick(self):
        """Advance one 60 Hz frame: decrement both timers, floor at 0."""
        if self.delay > 0:
            self.delay -= 1
        if self.sound > 0:
            self.sound -= 1

    def set_delay(self, value: int):
        self.delay = value & 0xFF

    def set_sound(self, value: int):
        self.sound = value & 0xFF

    @property
    def beeping(self) -> bool:
        return self.sound > 0