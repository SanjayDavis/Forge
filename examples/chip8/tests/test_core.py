"""Core subsystem unit tests: memory, registers, stack, timers, rng, keypad,
fontset, display."""
import unittest

from chip8 import memory, registers, stack, timers, rng, keypad, fontset, display


class MemoryTest(unittest.TestCase):
    def test_roundtrip(self):
        m = memory.Memory()
        m.write(0x200, 0xAB)
        self.assertEqual(m.read(0x200), 0xAB)
        # adjacent byte still zero
        self.assertEqual(m.read(0x201), 0)

    def test_write_wraps_byte(self):
        m = memory.Memory()
        m.write(0x100, 0x1FF)
        self.assertEqual(m.read(0x100), 0xFF)

    def test_bounds(self):
        m = memory.Memory()
        for bad in (-1, 4096):
            with self.assertRaises(memory.MemoryError):
                m.read(bad)

    def test_load_program(self):
        m = memory.Memory()
        m.load(b"\x00\xE0\x12\x00", base=0x200)
        self.assertEqual(m.read_word(0x200), 0x00E0)

    def test_read_word_big_endian(self):
        m = memory.Memory()
        m.write(0x300, 0x12)
        m.write(0x301, 0x34)
        self.assertEqual(m.read_word(0x300), 0x1234)


class RegistersTest(unittest.TestCase):
    def test_vx_wraps(self):
        r = registers.Registers()
        r.set_vx(3, 0x1FF)
        self.assertEqual(r.vx(3), 0xFF)

    def test_i_pc_16bit(self):
        r = registers.Registers()
        r.set_i(0x12345)
        self.assertEqual(r.i, 0x2345)
        r.set_pc(0x1FFFF)
        self.assertEqual(r.pc, 0xFFFF)

    def test_vf_flag_register(self):
        r = registers.Registers()
        r.vf = 1
        self.assertEqual(r.v[0xF], 1)


class StackTest(unittest.TestCase):
    def test_lifo(self):
        s = stack.Stack()
        s.push(0x200)
        s.push(0x210)
        self.assertEqual(s.pop(), 0x210)
        self.assertEqual(s.pop(), 0x200)

    def test_underflow(self):
        s = stack.Stack()
        with self.assertRaises(stack.StackError):
            s.pop()

    def test_overflow(self):
        s = stack.Stack()
        for _ in range(stack.STACK_SIZE):
            s.push(0x200)
        with self.assertRaises(stack.StackError):
            s.push(0x200)


class TimersTest(unittest.TestCase):
    def test_decrement_to_zero(self):
        t = timers.Timers()
        t.set_delay(3)
        t.set_sound(2)
        t.tick(); t.tick(); t.tick()
        self.assertEqual(t.delay, 0)
        self.assertEqual(t.sound, 0)

    def test_floor_at_zero(self):
        t = timers.Timers()
        t.tick()
        self.assertEqual(t.delay, 0)


class RNGTest(unittest.TestCase):
    def test_deterministic_seed(self):
        a = [rng.RNG(seed=42).next_byte() for _ in range(5)]
        b = [rng.RNG(seed=42).next_byte() for _ in range(5)]
        self.assertEqual(a, b)

    def test_byte_range(self):
        r = rng.RNG(seed=1)
        for _ in range(1000):
            self.assertLessEqual(r.next_byte(), 255)


class KeypadTest(unittest.TestCase):
    def test_press_release(self):
        k = keypad.Keypad()
        k.press("A")
        self.assertTrue(k.is_pressed("A"))
        k.release("A")
        self.assertFalse(k.is_pressed("A"))

    def test_int_normalization(self):
        k = keypad.Keypad()
        k.press(0xF)
        self.assertEqual(k.any_pressed(), 0xF)
        k.clear()
        self.assertIsNone(k.any_pressed())


class FontsetTest(unittest.TestCase):
    def test_glyph_count_and_load(self):
        m = memory.Memory()
        base = fontset.load(m)
        self.assertEqual(base, fontset.FONT_BASE)
        self.assertEqual(len(fontset.GLYPHS), 80)  # 16 glyphs * 5 bytes
        self.assertEqual(m.read(base), 0xF0)       # glyph '0' starts 0xF0

    def test_glyph_lookup(self):
        self.assertEqual(len(fontset.glyph(0xF)), 5)


class FrameBufferTest(unittest.TestCase):
    def test_clear(self):
        d = display.Display()
        d.pixels[0] = 1
        d.clear()
        self.assertEqual(sum(d.pixels), 0)

    def test_collision_flag(self):
        d = display.Display()
        # draw a full block, then re-draw the same block -> collision
        block = bytes([0xFF] * 5)
        first = d.draw_sprite(0, 0, block)
        second = d.draw_sprite(0, 0, block)
        self.assertEqual(first, 0)
        self.assertEqual(second, 1)
        # redrawn = erased
        self.assertEqual(sum(d.pixels), 0)

    def test_wraps_at_edges(self):
        d = display.Display()
        d.draw_sprite(display.WIDTH - 1, display.HEIGHT - 1, b"\x80")
        # a single set bit at the last pixel
        self.assertEqual(d.pixels[-1], 1)


if __name__ == "__main__":
    unittest.main()