"""ALU opcode tests: 6XNN, 7XNN, 8XYN family, CXNN."""
import unittest
from _util import mk_cpu, write_ops, run
from chip8.rng import RNG


class AluTest(unittest.TestCase):
    def setUp(self):
        self.cpu = mk_cpu()

    def test_ld_imm(self):
        write_ops(self.cpu, 0x6123)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.vx(1), 0x23)

    def test_add_imm(self):
        self.cpu.reg.set_vx(0, 0x05)
        write_ops(self.cpu, 0x7003)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.vx(0), 0x08)

    def test_ld_reg(self):
        self.cpu.reg.set_vx(0, 1)
        self.cpu.reg.set_vx(1, 9)
        write_ops(self.cpu, 0x8010)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.vx(0), 9)

    def test_or_and_xor(self):
        cases = [(0x8011, 0b1100 | 0b1010), (0x8012, 0b1100 & 0b1010),
                 (0x8013, 0b1100 ^ 0b1010)]
        for op, expect in cases:
            self.cpu.reg.set_vx(0, 0b1100)
            self.cpu.reg.set_vx(1, 0b1010)
            self.cpu.reg.set_pc(0x300)
            write_ops(self.cpu, op)
            run(self.cpu)
            self.assertEqual(self.cpu.reg.vx(0), expect)

    def test_add_carry_sets_vf(self):
        self.cpu.reg.set_vx(0, 0xFF)
        self.cpu.reg.set_vx(1, 0x01)
        write_ops(self.cpu, 0x8014)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.vx(0), 0x00)
        self.assertEqual(self.cpu.reg.vf, 1)

    def test_add_no_carry(self):
        self.cpu.reg.set_vx(0, 2)
        self.cpu.reg.set_vx(1, 3)
        write_ops(self.cpu, 0x8014)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.vx(0), 5)
        self.assertEqual(self.cpu.reg.vf, 0)

    def test_sub_no_borrow(self):
        self.cpu.reg.set_vx(0, 5)
        self.cpu.reg.set_vx(1, 3)
        write_ops(self.cpu, 0x8015)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.vx(0), 2)
        self.assertEqual(self.cpu.reg.vf, 1)

    def test_sub_borrow(self):
        self.cpu.reg.set_vx(0, 3)
        self.cpu.reg.set_vx(1, 5)
        write_ops(self.cpu, 0x8015)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.vx(0), (3 - 5) & 0xFF)
        self.assertEqual(self.cpu.reg.vf, 0)

    def test_shr(self):
        self.cpu.reg.set_vx(0, 0b1010)
        write_ops(self.cpu, 0x8016)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.vf, 0)
        self.assertEqual(self.cpu.reg.vx(0), 0b0101)

    def test_shr_lsb_flag(self):
        self.cpu.reg.set_vx(0, 0b0001)
        write_ops(self.cpu, 0x8016)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.vf, 1)

    def test_subn(self):
        self.cpu.reg.set_vx(0, 3)
        self.cpu.reg.set_vx(1, 5)
        write_ops(self.cpu, 0x8017)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.vx(0), 2)
        self.assertEqual(self.cpu.reg.vf, 1)

    def test_shl(self):
        self.cpu.reg.set_vx(0, 0b10000001)
        write_ops(self.cpu, 0x801E)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.vf, 1)
        self.assertEqual(self.cpu.reg.vx(0), 0b00000010)

    def test_rand_masks(self):
        # deterministic with a fixed seed
        self.cpu.rng = RNG(seed=42)
        expected = (RNG(seed=42).next_byte() & 0x7F)
        write_ops(self.cpu, 0xC07F)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.vx(0), expected)


if __name__ == "__main__":
    unittest.main()