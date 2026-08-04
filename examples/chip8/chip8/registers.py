"""Register file: V0-VF (8-bit), I (16-bit index), PC, SP.

8-bit arithmetic wraps mod 256. PC and I are 16-bit. SP is the stack pointer
into the call stack (lives in chip8.stack).
"""


class Registers:
    def __init__(self):
        self.reset()

    def reset(self):
        self.v = [0] * 16          # V0..VF data registers
        self.i = 0                 # index register (16-bit)
        self.pc = 0x0000           # program counter
        self.sp = 0                # stack pointer

    # -- data registers V0..VF -------------------------------------------------
    def vx(self, x: int) -> int:
        return self.v[x]

    def set_vx(self, x: int, value: int):
        self.v[x] = value & 0xFF

    @property
    def vf(self):
        return self.v[0xF]

    @vf.setter
    def vf(self, value: int):
        self.v[0xF] = value & 0xFF

    # -- 16-bit registers ------------------------------------------------------
    def set_i(self, value: int):
        self.i = value & 0xFFFF

    def set_pc(self, value: int):
        self.pc = value & 0xFFFF

    def inc_pc(self, by=2):
        self.pc = (self.pc + by) & 0xFFFF