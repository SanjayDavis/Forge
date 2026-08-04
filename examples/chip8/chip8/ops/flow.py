"""Flow-control opcode units: 00EE RET, 1NNN JP, 2NNN CALL, 3XNN/4XNN skip imm,
5XY0/9XY0 skip register, BNNN JP V0.

Each unit is a plain function (cpu, operand...) registered by cpu.py's
high-nibble dispatch table. Skips advance PC by a further 2 bytes (the fetch
already advanced it past the current instruction).
"""


def op_ret(cpu):
    """00EE — return from subroutine."""
    cpu.reg.pc = cpu.stack.pop()


def op_jmp(cpu, addr):
    """1NNN — jump to address NNN."""
    cpu.reg.pc = addr


def op_call(cpu, addr):
    """2NNN — call subroutine at NNN (push return address)."""
    cpu.stack.push(cpu.reg.pc)
    cpu.reg.pc = addr


def op_skip_eq_imm(cpu, x, nn):
    """3XNN — skip next instruction if Vx == NN."""
    if cpu.reg.vx(x) == nn:
        cpu.reg.inc_pc(2)


def op_skip_ne_imm(cpu, x, nn):
    """4XNN — skip next instruction if Vx != NN."""
    if cpu.reg.vx(x) != nn:
        cpu.reg.inc_pc(2)


def op_skip_reg(cpu, x, y):
    """5XY0 — skip next instruction if Vx == Vy."""
    if cpu.reg.vx(x) == cpu.reg.vx(y):
        cpu.reg.inc_pc(2)


def op_skip_reg_ne(cpu, x, y):
    """9XY0 — skip next instruction if Vx != Vy."""
    if cpu.reg.vx(x) != cpu.reg.vx(y):
        cpu.reg.inc_pc(2)


def op_jmp_v0(cpu, addr):
    """BNNN — jump to NNN + V0."""
    cpu.reg.pc = (addr + cpu.reg.vx(0)) & 0xFFFF
