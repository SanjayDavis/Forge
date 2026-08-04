"""Timer opcode units: FX07 read delay, FX15/FX18 write delay/sound.

FX07 reads the delay timer into Vx; FX15 writes Vx to the delay timer;
FX18 writes Vx to the sound (beep) timer. Timing/tick lives in chip8.timers.
"""


def op_timer_read(cpu, x):
    """FX07 — Vx = delay timer."""
    cpu.reg.set_vx(x, cpu.timers.delay)


def op_timer_write(cpu, x, n):
    """FX15 / FX18 — delay (n=0x15) or sound (n=0x18) timer = Vx."""
    value = cpu.reg.vx(x)
    if n == 0x15:
        cpu.timers.set_delay(value)
    else:
        cpu.timers.set_sound(value)