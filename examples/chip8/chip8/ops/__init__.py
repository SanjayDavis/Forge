"""Opcode units package.

Each module implements a group of CHIP-8 instructions as plain functions of
signature (cpu, ...). cpu.FAMILY (see chip8.cpu) routes the high nibble to the
right unit. Keeping units here lets every opcode task land as real, testable
code in the file the proposal names.
"""