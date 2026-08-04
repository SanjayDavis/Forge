"""Input opcode tests: EX9E / EXA1 key skip, FX0A key wait."""
import unittest
from _util import mk_cpu, write_ops, run


class InputTest(unittest.TestCase):
    def setUp(self):
        self.cpu = mk_cpu()
        self.cpu.reg.set_pc(0x300)

    def test_ex9e_skips_when_pressed(self):
        self.cpu.reg.set_vx(0, 0x0A)          # key A
        self.cpu.keypad.press(0xA)
        write_ops(self.cpu, 0xE09E, 0x6000)   # skip LD V0,0
        run(self.cpu, 2)
        self.assertEqual(self.cpu.reg.vx(0), 0x0A)   # canary skipped

    def test_ex9e_no_skip_when_released(self):
        self.cpu.reg.set_vx(0, 0x0A)
        write_ops(self.cpu, 0xE09E, 0x6000)
        run(self.cpu, 2)
        self.assertEqual(self.cpu.reg.vx(0), 0x00)   # canary ran

    def test_exa1_skips_when_released(self):
        self.cpu.reg.set_vx(0, 0x03)
        write_ops(self.cpu, 0xE0A1, 0x6000)
        run(self.cpu, 2)
        self.assertEqual(self.cpu.reg.vx(0), 0x03)   # canary skipped

    def test_fx0a_blocks_then_stores(self):
        write_ops(self.cpu, 0xF00A)           # wait for key into V0
        run(self.cpu)                         # nothing pressed -> rewind
        self.assertEqual(self.cpu.reg.pc, 0x300)
        self.cpu.keypad.press(0x05)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.vx(0), 0x05)
        self.assertEqual(self.cpu.reg.pc, 0x302)


if __name__ == "__main__":
    unittest.main()