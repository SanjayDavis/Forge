"""Display opcode tests: 00E0 CLS, DXYN DRW (draw, wrap, collision)."""
import unittest
from _util import mk_cpu, write_ops, run
from chip8.display import WIDTH, HEIGHT


class DisplayTest(unittest.TestCase):
    def setUp(self):
        self.cpu = mk_cpu()
        self.cpu.reg.set_pc(0x300)

    def put_sprite(self, addr, data):
        for i, b in enumerate(data):
            self.cpu.memory.write(addr + i, b)

    def test_cls_clears(self):
        self.cpu.display.set(10, 10, 1)
        write_ops(self.cpu, 0x00E0)
        run(self.cpu)
        self.assertEqual(sum(self.cpu.display.pixels), 0)

    def test_draw_lights_pixels(self):
        self.put_sprite(0x500, [0xFF] * 5)             # full 8x5 block
        self.cpu.reg.set_i(0x500)
        self.cpu.reg.set_vx(0, 3)
        self.cpu.reg.set_vx(1, 4)
        write_ops(self.cpu, 0xD015)          # DRW V0, V1, 5
        run(self.cpu)
        self.assertEqual(self.cpu.display.get(3, 4), 1)      # top-left lit
        self.assertEqual(self.cpu.display.get(10, 4), 1)     # top-row right edge
        self.assertEqual(self.cpu.display.get(11, 4), 0)     # outside sprite
        self.assertEqual(self.cpu.display.get(3, 8), 1)      # bottom row lit
        self.assertEqual(self.cpu.display.get(3, 9), 0)      # below sprite
        self.assertEqual(self.cpu.reg.vf, 0)  # no collision yet

    def test_draw_at_right_edge(self):
        self.put_sprite(0x500, [0x80])       # single leftmost bit
        self.cpu.reg.set_i(0x500)
        self.cpu.reg.set_vx(0, WIDTH - 1)    # right edge
        self.cpu.reg.set_vx(1, HEIGHT - 1)   # bottom edge
        write_ops(self.cpu, 0xD011)
        run(self.cpu)
        self.assertEqual(self.cpu.display.get(WIDTH - 1, HEIGHT - 1), 1)

    def test_draw_wraps_horizontally(self):
        self.put_sprite(0x500, [0x01])       # rightmost bit -> wraps to col 0
        self.cpu.reg.set_i(0x500)
        self.cpu.reg.set_vx(0, WIDTH - 1)    # draw at col 63 => bit lands col 6
        self.cpu.reg.set_vx(1, 1)
        write_ops(self.cpu, 0xD011)
        run(self.cpu)
        self.assertEqual(self.cpu.display.get((WIDTH - 1 + 7) % WIDTH, 1), 1)

    def test_draw_collision_sets_vf(self):
        self.put_sprite(0x500, [0xFF])
        self.cpu.reg.set_i(0x500)
        self.cpu.reg.set_vx(0, 2)
        self.cpu.reg.set_vx(1, 2)
        write_ops(self.cpu, 0xD011, 0xD011)   # draw twice at the same spot
        run(self.cpu, 2)
        self.assertEqual(self.cpu.reg.vf, 1)  # second draw toggled pixels off


if __name__ == "__main__":
    unittest.main()