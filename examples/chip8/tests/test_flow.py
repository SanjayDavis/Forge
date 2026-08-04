"""Flow-control opcode tests: JMP, CALL/RET, skip imm, skip reg, JP V0."""
import unittest
from _util import mk_cpu, write_ops, run


class FlowTest(unittest.TestCase):
    def setUp(self):
        self.cpu = mk_cpu()

    def test_jmp(self):
        write_ops(self.cpu, 0x1ABC)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.pc, 0xABC)

    def test_call_pushes_and_jumps(self):
        write_ops(self.cpu, 0x2345)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.pc, 0x345)
        self.assertEqual(self.cpu.stack.pop(), 0x302)   # return addr = after CALL

    def test_ret_pops(self):
        self.cpu.stack.push(0xABC)
        self.cpu.reg.set_pc(0x300)
        write_ops(self.cpu, 0x00EE)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.pc, 0xABC)

    def test_skip_eq_imm(self):
        self.cpu.reg.set_vx(0, 0x42)
        write_ops(self.cpu, 0x3042, 0x6000)   # skip LD V0,0 (==), canary
        run(self.cpu, 2)
        self.assertEqual(self.cpu.reg.vx(0), 0x42)    # canary skipped

    def test_no_skip_eq_imm(self):
        self.cpu.reg.set_vx(0, 0x42)
        write_ops(self.cpu, 0x3099, 0x6000)   # 0x42 != 0x99, no skip
        run(self.cpu, 2)
        self.assertEqual(self.cpu.reg.vx(0), 0x00)    # canary ran

    def test_skip_ne_imm(self):
        self.cpu.reg.set_vx(0, 0x42)
        write_ops(self.cpu, 0x40FF, 0x6000)   # V0 != 0xFF -> skip
        run(self.cpu, 2)
        self.assertEqual(self.cpu.reg.vx(0), 0x42)

    def test_skip_reg_eq(self):
        self.cpu.reg.set_vx(0, 7)
        self.cpu.reg.set_vx(1, 7)
        write_ops(self.cpu, 0x5010, 0x6000)
        run(self.cpu, 2)
        self.assertEqual(self.cpu.reg.vx(0), 7)

    def test_skip_reg_ne(self):
        self.cpu.reg.set_vx(0, 7)
        self.cpu.reg.set_vx(1, 8)
        write_ops(self.cpu, 0x9010, 0x6000)
        run(self.cpu, 2)
        self.assertEqual(self.cpu.reg.vx(0), 7)

    def test_jmp_v0(self):
        self.cpu.reg.set_vx(0, 5)
        write_ops(self.cpu, 0xB100)
        run(self.cpu)
        self.assertEqual(self.cpu.reg.pc, 0x105)


if __name__ == "__main__":
    unittest.main()