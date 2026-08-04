"""Arithmetic/load opcode units: 6XNN LD Vx, 7XNN ADD Vx, 8XYN ALU family,
CXNN RND Vx, NN.

The 8XYN family is the densest: 8XY0-8XYE covers LD/OR/AND/XOR/ADD/SUB/SHR/
SUBN/SHL, with VF as the flag register (borrow, LSB/MSB shifted out).
8-bit arithmetic wraps mod 256.
"""


def op_ld_imm(cpu, x, nn):
    """6XNN — Vx = NN."""
    cpu.reg.set_vx(x, nn)


def op_add_imm(cpu, x, nn):
    """7XNN — Vx += NN (no VF change)."""
    cpu.reg.set_vx(x, (cpu.reg.vx(x) + nn) & 0xFF)


def op_alu(cpu, x, y, n):
    """8XYN — ALU family; VF carries flags."""
    vx, vy = cpu.reg.vx(x), cpu.reg.vx(y)
    if n == 0x0:      # LD Vx, Vy
        cpu.reg.set_vx(x, vy)
    elif n == 0x1:    # OR
        cpu.reg.set_vx(x, vx | vy)
    elif n == 0x2:    # AND
        cpu.reg.set_vx(x, vx & vy)
    elif n == 0x3:    # XOR
        cpu.reg.set_vx(x, vx ^ vy)
    elif n == 0x4:    # ADD, VF = carry
        s = vx + vy
        cpu.reg.set_vx(x, s & 0xFF)
        cpu.reg.vf = 1 if s > 0xFF else 0
    elif n == 0x5:    # SUB, VF = not borrow
        cpu.reg.set_vx(x, (vx - vy) & 0xFF)
        cpu.reg.vf = 1 if vx >= vy else 0
    elif n == 0x6:    # SHR Vx, VF = LSB shifted out
        cpu.reg.vf = vx & 1
        cpu.reg.set_vx(x, vx >> 1)
    elif n == 0x7:    # SUBN, VF = not borrow (Vy - Vx)
        cpu.reg.set_vx(x, (vy - vx) & 0xFF)
        cpu.reg.vf = 1 if vy >= vx else 0
    elif n == 0xE:    # SHL Vx, VF = MSB shifted out
        cpu.reg.vf = (vx >> 7) & 1
        cpu.reg.set_vx(x, (vx << 1) & 0xFF)
    else:
        raise cpu.UnknownOpcode(f"8XY{n:X} (reserved ALU variant)")


def op_rand(cpu, x, nn):
    """CXNN — Vx = random byte & NN."""
    cpu.reg.set_vx(x, cpu.rng.next_byte() & nn)
