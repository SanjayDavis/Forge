"""Memory opcode units: ANNN LD I, FX1E ADD I, FX29 FONT, FX33 BCD,
FX55 store, FX65 load.

Store/load use the quirks-free variant: I advances by X+1 bytes after
FX55/FX65 (modern interpreters reset I to the start; the classic COSMAC
behaviour increments — this core follows the incrementing semantics so the
I register stays usable for sequential buffers).
"""


def op_ld_i(cpu, addr):
    """ANNN — I = NNN."""
    cpu.reg.set_i(addr)


def op_add_i(cpu, x):
    """FX1E — I += Vx (VF untouched)."""
    cpu.reg.set_i(cpu.reg.i + cpu.reg.vx(x))


def op_font(cpu, x):
    """FX29 — I = address of glyph for the low nibble of Vx."""
    from ..fontset import FONT_BASE
    cpu.reg.set_i(FONT_BASE + (cpu.reg.vx(x) & 0x0F) * 5)


def op_bcd(cpu, x):
    """FX33 — store BCD (hundreds, tens, units) of Vx at I, I+1, I+2."""
    v = cpu.reg.vx(x)
    cpu.memory.write(cpu.reg.i, v // 100)
    cpu.memory.write(cpu.reg.i + 1, (v // 10) % 10)
    cpu.memory.write(cpu.reg.i + 2, v % 10)


def op_store_mem(cpu, x):
    """FX55 — store V0..Vx at I; I advances past the block."""
    for r in range(x + 1):
        cpu.memory.write(cpu.reg.i + r, cpu.reg.vx(r))
    cpu.reg.set_i(cpu.reg.i + x + 1)


def op_load_mem(cpu, x):
    """FX65 — load V0..Vx from I; I advances past the block."""
    for r in range(x + 1):
        cpu.reg.set_vx(r, cpu.memory.read(cpu.reg.i + r))
    cpu.reg.set_i(cpu.reg.i + x + 1)
