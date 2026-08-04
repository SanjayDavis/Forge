"""Display opcode units: 00E0 CLS, DXYN DRW.

CLS clears the 64x32 buffer. DRW reads an 8-column, N-row sprite from memory
at I and XORs it at (Vx, Vy); VF is set to 1 if any pixel flipped to off
(collision) — the quirks-free behaviour.
"""


def op_cls(cpu):
    """00E0 — clear the display."""
    cpu.display.clear()


def op_draw(cpu, x, y, n):
    """DXYN — draw N-byte sprite at I to (Vx, Vy); VF = collision."""
    x, y = cpu.reg.vx(x), cpu.reg.vx(y)
    sprite = bytes(cpu.memory.read(cpu.reg.i + r) for r in range(n))
    collision = cpu.display.draw_sprite(x, y, sprite)
    cpu.reg.vf = 1 if collision else 0