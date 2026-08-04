"""Input opcode units: EX9E/EXA1 key skip, FX0A key wait.

The hex keypad maps keys 0-F. EX9E skips if the key in Vx is pressed, EXA1 if
it is not. FX0A blocks until a key is pressed (the fetch already advanced PC,
so it rewinds if no key is down and re-runs next cycle).
"""


def op_key_skip(cpu, x, ne):
    """EX9E / EXA1 — skip next if key in Vx is pressed / not pressed."""
    key = cpu.reg.vx(x) & 0x0F
    pressed = cpu.keypad.is_pressed(key)
    if pressed != ne:            # ne=0 for EX9E (skip when pressed)
        cpu.reg.inc_pc(2)


def op_key_wait(cpu, x):
    """FX0A — wait for a keypress; store it in Vx."""
    if not cpu.keypad.any_pressed():
        cpu.reg.pc -= 2          # rewind so the wait re-runs
        return
    for key in range(16):
        if cpu.keypad.is_pressed(key):
            cpu.reg.set_vx(x, key)
            return