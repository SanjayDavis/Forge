"""CHIP-8 emulator (Proof #2). Standard 4KiB, 16-key, 64x32, 5MHz-ish core.

Subsystem layout (mirrors examples/chip8/proposal.json):
  memory, registers, stack, timers, rng, display, keypad, fontset
  joined by chip8.cpu (fetch-decode-execute).
Stdlib-only. No external deps.
"""

__version__ = "0.2.0"
__all__ = [
    "memory", "registers", "stack", "timers", "rng",
    "display", "keypad", "fontset", "cpu",
]