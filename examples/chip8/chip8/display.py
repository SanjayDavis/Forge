"""64x32 monochrome display framebuffer.

Pixels are 1-bit, stored row-major in a bytearray. The DRW opcode XORs an 8xN
sprite into the buffer at (x, y); when a set pixel flips to 0 (collision),
VF is set. Wraps at screen edges per the original hardware.
"""

WIDTH = 64
HEIGHT = 32


class Display:
    def __init__(self):
        self.pixels = bytearray(WIDTH * HEIGHT)

    def clear(self):
        self.pixels[:] = b"\x00" * (WIDTH * HEIGHT)

    def get(self, x: int, y: int) -> int:
        return self.pixels[y * WIDTH + x]

    def set(self, x: int, y: int, value: int) -> bool:
        """Set a pixel (bounds-safe), returning whether it collided (was on).

        Stray coordinates are ignored (no wrap collision for out-of-screen).
        """
        if not (0 <= y < HEIGHT and 0 <= x < WIDTH):
            return False
        idx = y * WIDTH + x
        old = self.pixels[idx]
        new = value & 1
        self.pixels[idx] = new
        return old == 1 and new == 0

    def draw_sprite(self, x: int, y: int, sprite: bytes) -> int:
        """XOR an 8-wide, len(sprite)-tall sprite at (x,y). Returns 1 on collision."""
        collision = 0
        for row, byte in enumerate(sprite):
            py = (y + row) % HEIGHT          # wrap vertically like real hardware
            for bit in range(8):
                px = (x + bit) % WIDTH        # wrap horizontally
                sx = (byte >> (7 - bit)) & 1
                if sx == 0:
                    continue
                idx = py * WIDTH + px
                if self.pixels[idx] == 1:
                    collision = 1
                self.pixels[idx] ^= 1
        return collision