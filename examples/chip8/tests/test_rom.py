"""ROM loader + end-to-end smoke test against a real ROM file."""
import unittest
from pathlib import Path
from _util import mk_cpu
from chip8 import rom, memory

ROMS = Path(__file__).resolve().parent / "roms"


class RomTest(unittest.TestCase):
    def test_empty_raises(self):
        with self.assertRaises(rom.RomError):
            rom.load_bytes(b"")

    def test_oversize_raises(self):
        with self.assertRaises(rom.RomError):
            rom.load_bytes(b"\x00" * (rom.MAX_PROGRAM + 1))

    def test_missing_file_raises(self):
        with self.assertRaises(rom.RomError):
            rom.load("definitely-not-here.ch8")

    def test_load_into_places_at_origin(self):
        mem = memory.Memory()
        end = rom.load_into(mem, b"\x12\x34\x56")
        self.assertEqual(end, 0x200 + 3)
        self.assertEqual(mem.read(0x200), 0x12)
        self.assertEqual(mem.read(0x202), 0x56)

    def test_smoke_rom_runs_end_to_end(self):
        """Load tests/roms/smoke.ch8 and run it: draws a moving sprite."""
        program = rom.load(str(ROMS / "smoke.ch8"))
        cpu = mk_cpu()
        cpu.reset()
        cpu.reg.set_pc(0x200)
        end = rom.load_into(cpu.memory, program)
        self.assertEqual(end, 0x200 + len(program))
        cycles = cpu.run(200)
        self.assertEqual(cycles, 200)
        # sprite was drawn => at least one pixel lit
        self.assertGreater(sum(cpu.display.pixels), 0)
        # program counter stayed inside the ROM image (no runaway)
        self.assertTrue(0x200 <= cpu.reg.pc <= end + 0x40)


if __name__ == "__main__":
    unittest.main()