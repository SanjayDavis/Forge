"""Fetch-decode-execute core: chip8.CPU.

Binds the subsystems (memory, registers, stack, timers, rng, display, keypad)
with an opcode dispatcher. step() fetches a word at PC (PC advances by 2), then
routes by high nibble to the opcode units in chip8.ops.*. run() loops steps,
Optionally ticking timers at the caller's 60 Hz cadence.
"""

import chip8.ops.flow as flow
import chip8.ops.alu as alu
import chip8.ops.mem as mem
import chip8.ops.display as display_ops
import chip8.ops.input as input_ops
import chip8.ops.timers as timer_ops
import chip8.display as fb
import chip8.fontset as fontset


class UnknownOpcode(RuntimeError):
    """Raised when the CPU hits an opcode it cannot decode."""


def _op_family_0(cpu, op):
    last12 = op & 0x0FFF
    if last12 == 0x0E0:
        display_ops.op_cls(cpu)
    elif last12 == 0x0EE:
        flow.op_ret(cpu)
    else:
        # 0NNN: call machine routine at NNN (rare, not emulated) — ignore.
        pass


def _op_family_e(cpu, op):
    x, nn = (op >> 8) & 0xF, op & 0xFF
    if nn == 0x9E:
        input_ops.op_key_skip(cpu, x, ne=False)
    elif nn == 0xA1:
        input_ops.op_key_skip(cpu, x, ne=True)
    else:
        raise UnknownOpcode(f"{op:04X} (bad key opcode)")


def _op_family_f(cpu, op):
    x, nn = (op >> 8) & 0xF, op & 0xFF
    if nn == 0x07:
        timer_ops.op_timer_read(cpu, x)
    elif nn == 0x0A:
        input_ops.op_key_wait(cpu, x)
    elif nn in (0x15, 0x18):
        timer_ops.op_timer_write(cpu, x, n=nn)
    elif nn == 0x1E:
        mem.op_add_i(cpu, x)
    elif nn == 0x29:
        mem.op_font(cpu, x)
    elif nn == 0x33:
        mem.op_bcd(cpu, x)
    elif nn == 0x55:
        mem.op_store_mem(cpu, x)
    elif nn == 0x65:
        mem.op_load_mem(cpu, x)
    else:
        raise UnknownOpcode(f"{op:04X} (unknown F-family)")


# dispatch routes by high nibble (task cpu-fde acceptance); each family
# decodes the raw opcode into the operands its opcode unit expects.
FAMILY = {
    0x0: _op_family_0,   # 00E0 CLS / 00EE RET / 0NNN ignore
    0x1: lambda c, op: flow.op_jmp(c, op & 0xFFF),
    0x2: lambda c, op: flow.op_call(c, op & 0xFFF),
    0x3: lambda c, op: flow.op_skip_eq_imm(c, (op >> 8) & 0xF, op & 0xFF),
    0x4: lambda c, op: flow.op_skip_ne_imm(c, (op >> 8) & 0xF, op & 0xFF),
    0x5: lambda c, op: flow.op_skip_reg(c, (op >> 8) & 0xF, (op >> 4) & 0xF),
    0x6: lambda c, op: alu.op_ld_imm(c, (op >> 8) & 0xF, op & 0xFF),
    0x7: lambda c, op: alu.op_add_imm(c, (op >> 8) & 0xF, op & 0xFF),
    0x8: lambda c, op: alu.op_alu(c, (op >> 8) & 0xF, (op >> 4) & 0xF, op & 0xF),
    0x9: lambda c, op: flow.op_skip_reg_ne(c, (op >> 8) & 0xF, (op >> 4) & 0xF),
    0xA: lambda c, op: mem.op_ld_i(c, op & 0xFFF),
    0xB: lambda c, op: flow.op_jmp_v0(c, op & 0xFFF),
    0xC: lambda c, op: alu.op_rand(c, (op >> 8) & 0xF, op & 0xFF),
    0xD: lambda c, op: display_ops.op_draw(c, (op >> 8) & 0xF, (op >> 4) & 0xF, op & 0xF),
    0xE: _op_family_e,
    0xF: _op_family_f,
}


class CPU:
    def __init__(self, memory=None, registers=None, stack=None, timers=None,
                 rng=None, display=None, keypad=None):
        self.memory = memory
        self.registers = registers
        self.stack = stack
        self.timers = timers
        self.rng = rng
        self.display = display
        self.keypad = keypad
        # convenience aliases used by the opcode units
        self.reg = registers
        self.cycles = 0

    def install_defaults(self):
        """Build every subsystem if not provided; load the fontset."""
        if self.memory is None:
            from .memory import Memory
            self.memory = Memory()
        if self.registers is None:
            from .registers import Registers
            self.registers = Registers()
            self.reg = self.registers
        if self.stack is None:
            from .stack import Stack
            self.stack = Stack()
        if self.timers is None:
            from .timers import Timers
            self.timers = Timers()
        if self.rng is None:
            from .rng import RNG
            self.rng = RNG()
        if self.display is None:
            self.display = fb.Display()
        if self.keypad is None:
            from .keypad import Keypad
            self.keypad = Keypad()
        fontset.load(self.memory)

    def reset(self):
        self.registers.reset()
        self.stack.reset()
        self.display.clear()
        self.timers.delay = 0
        self.timers.sound = 0
        self.registers.set_pc(0x200)   # program entry
        self.cycles = 0

    def fetch(self) -> int:
        """Read the next opcode (big-endian word) and advance PC by 2."""
        op = self.memory.read_word(self.registers.pc & 0xFFFF)
        self.registers.inc_pc(2)
        return op

    def step(self) -> int:
        """Execute exactly one instruction; returns the opcode executed."""
        op = self.fetch()
        high = (op >> 12) & 0xF
        handler = FAMILY[high]
        handler(self, op)
        self.cycles += 1
        return op

    def run(self, cycles: int) -> int:
        """Execute up to `cycles` instructions; returns cycles executed."""
        done = 0
        for _ in range(cycles):
            self.step()
            done += 1
        return done