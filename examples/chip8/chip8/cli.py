"""Headless CHIP-8 CLI: run a ROM, trace opcodes, dump ASCII frames.

No windowing/GUI — the emulator is fully deterministic and can be driven from
the shell. This is the runnable artifact for the cli-run task and what the
proof's demo transcript is generated from:

    python -m chip8 tests/roms/smoke.ch8 --cycles 200 --trace
"""
import argparse
import sys
from . import rom
from .cpu import CPU, UnknownOpcode
from .memory import Memory
from .display import WIDTH, HEIGHT


def ascii_frame(display) -> str:
    px = display.pixels
    return "\n".join(
        "".join("#" if px[y * WIDTH + x] else "." for x in range(WIDTH))
        for y in range(HEIGHT)
    )


def run_rom(rom_path, cycles=60, seed=None, trace=False):
    """Run a ROM headlessly; returns (cpu, executed). Raises UnknownOpcode."""
    cpu = CPU(memory=Memory())
    cpu.install_defaults()
    cpu.reset()
    from .rng import RNG
    if seed is not None:
        cpu.rng = RNG(seed=seed)
    program = rom.load(rom_path)
    rom.load_into(cpu.memory, program)
    cpu.reg.set_pc(0x200)

    executed = 0
    for _ in range(cycles):
        try:
            op = cpu.step()
        except UnknownOpcode as exc:
            print(f"  [halt] unknown opcode at 0x{cpu.reg.pc - 2 & 0xFFF:03X}: {exc}")
            break
        if trace:
            addr = (cpu.reg.pc - 2) & 0xFFF
            print(f"  0x{addr:03X}: {op:04X}  [pc→0x{cpu.reg.pc & 0xFFF:03X}]")
        executed += 1
    return cpu, executed


def main(argv=None):
    ap = argparse.ArgumentParser(prog="chip8",
                                 description="Headless CHIP-8 emulator")
    ap.add_argument("rom", help="path to a .ch8 ROM")
    ap.add_argument("--cycles", type=int, default=60)
    ap.add_argument("--seed", type=int, default=None,
                    help="fix RNG seed for reproducibility")
    ap.add_argument("--trace", action="store_true",
                    help="print each executed opcode")
    ap.add_argument("--frame", action="store_true",
                    help="print an ASCII dump of the final framebuffer")
    a = ap.parse_args(argv)

    cpu, executed = run_rom(a.rom, cycles=a.cycles, seed=a.seed, trace=a.trace)

    if a.frame:
        print("--- framebuffer ---")
        print(ascii_frame(cpu.display))
    lit = sum(cpu.display.pixels)
    print(f"ran {a.rom}: {executed} cycles, pc=0x{cpu.reg.pc & 0xFFF:03X}, "
          f"V0=0x{cpu.reg.vx(0):02X}, pixels lit={lit}")
    return 0 if executed == a.cycles else 1


if __name__ == "__main__":
    sys.exit(main())