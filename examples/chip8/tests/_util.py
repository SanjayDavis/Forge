"""Shared test helpers: build a CPU, load opcodes at a fresh address, run steps."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chip8.cpu import CPU  # noqa: E402


def mk_cpu():
    cpu = CPU()
    cpu.install_defaults()
    cpu.reset()
    cpu.reg.set_pc(0x300)          # scratch program address
    return cpu


def write_ops(cpu, *words):
    """Write big-endian opcode words starting at the current PC."""
    pc = 0x300
    for i, w in enumerate(words):
        cpu.memory.write(pc + i * 2, (w >> 8) & 0xFF)
        cpu.memory.write(pc + i * 2 + 1, w & 0xFF)


def run(cpu, n=1):
    for _ in range(n):
        cpu.step()