"""Memory opcode tests: ANNN, FX1E, FX29, FX33, FX55, FX65."""
import unittest
from _util import mk_cpu, write_ops, run
from chip8.fontset import FONT_BASE


class MemTest(unittest.TestCase):
    def setUp(self):
        self.cpu = mk_cpu()
        self.cpu.reg.set_pc(0x300)

    def test_ld_i(self):
        write_ops(self.cpu, 0xA123)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.i, 0x123)

    def test_add_i(self):
        self.cpu.reg.set_i(0x100)
        self.cpu.reg.set_vx(0, 0x50)
        write_ops(self.cpu, 0xF01E)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.i, 0x150)

    def test_font_points_to_glyph(self):
        self.cpu.reg.set_vx(0, 0x0A)
        write_ops(self.cpu, 0xF029)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.i, FONT_BASE + 10 * 5)

    def test_bcd(self):
        self.cpu.reg.set_i(0x400)
        self.cpu.reg.set_vx(0, 123)           # BCD of 123 -> 1,2,3
        write_ops(self.cpu, 0xF033)
        run(self.cpu)
        self.assertEqual(self.cpu.memory.read(0x400), 1)   # hundreds
        self.assertEqual(self.cpu.memory.read(0x401), 2)   # tens
        self.assertEqual(self.cpu.memory.read(0x402), 3)   # units

    def test_store_mem_advances_i(self):
        self.cpu.reg.set_i(0x400)
        self.cpu.reg.set_vx(0, 1)
        self.cpu.reg.set_vx(1, 2)
        self.cpu.reg.set_vx(2, 3)
        write_ops(self.cpu, 0xF255)          # store V0..V2
        run(self.cpu)
        self.assertEqual([self.cpu.memory.read(0x400 + k) for k in range(3)], [1, 2, 3])
        self.assertEqual(self.cpu.reg.i, 0x403)

    def test_load_mem_advances_i(self):
        for k, v in enumerate((9, 8, 7)):
            self.cpu.memory.write(0x400 + k, v)
        self.cpu.reg.set_i(0x400)
        write_ops(self.cpu, 0xF265)          # load V0..V2
        run(self.cpu)
        self.assertEqual([self.cpu.reg.vx(k) for k in range(3)], [9, 8, 7])
        self.assertEqual(self.cpu.reg.i, 0x403)


class TimerOpTest(unittest.TestCase):
    """F-family system-timer ops: FX07 read, FX15/FX18 write."""

    def setUp(self):
        self.cpu = mk_cpu()
        self.cpu.reg.set_pc(0x300)

    def test_read_delay(self):
        self.cpu.timers.set_delay(5)
        write_ops(self.cpu, 0xF207)          # V2 = delay
        run(self.cpu)
        self.assertEqual(self.cpu.reg.vx(2), 5)

    def test_write_delay_and_sound(self):
        self.cpu.reg.set_vx(0, 7)
        write_ops(self.cpu, 0xF015, 0xF018)  # delay=7, sound=7
        run(self.cpu, 2)
        self.assertEqual(self.cpu.timers.delay, 7)
        self.assertEqual(self.cpu.timers.sound, 7)


if __name__ == "__main__":
    unittest.main()