"""16-slot call stack for CALL/RET.

Standard CHIP-8 allows 16 nested subroutine calls. Push/pop with overflow and
underflow guards so malformed ROMs fail loudly instead of corrupting memory.
"""

STACK_SIZE = 16


class StackError(RuntimeError):
    pass


class Stack:
    def __init__(self):
        self._slots = [0] * STACK_SIZE
        self._sp = 0

    @property
    def sp(self):
        return self._sp

    def push(self, addr: int):
        if self._sp >= STACK_SIZE:
            raise StackError(f"stack overflow (>{STACK_SIZE} frames)")
        self._slots[self._sp] = addr & 0xFFFF
        self._sp += 1

    def pop(self) -> int:
        if self._sp <= 0:
            raise StackError("stack underflow (RET without CALL)")
        self._sp -= 1
        return self._slots[self._sp]

    def reset(self):
        self._sp = 0