"""ROM loader: file bytes -> program memory at 0x200.

CHIP-8 programs are loaded at 0x200 by convention (interpreter + fonts live
below). The loader validates size and bounds so malformed ROMs fail loudly
before any execution, instead of corrupting interpreter memory.
"""

ORIGIN = 0x200          # standard program load address
MAX_PROGRAM = 0x1000 - ORIGIN  # 3584 bytes fit in 4 KiB at 0x200


class RomError(ValueError):
    """Raised for unreadable or oversized ROM files."""


def load_bytes(program: bytes) -> None:
    """Validate a program fits the addressable region."""
    if len(program) == 0:
        raise RomError("empty ROM: nothing to load")
    if len(program) > MAX_PROGRAM:
        raise RomError(f"ROM too large: {len(program)} bytes "
                       f"(max {MAX_PROGRAM} at 0x{ORIGIN:03X})")


def load(path) -> bytes:
    """Read a ROM file from disk and validate it."""
    try:
        with open(path, "rb") as fh:
            program = fh.read()
    except OSError as exc:
        raise RomError(f"cannot read ROM {path}: {exc}") from exc
    load_bytes(program)
    return program


def load_into(memory, program: bytes, origin: int = ORIGIN) -> int:
    """Place a validated program into memory at `origin`; returns end address."""
    load_bytes(program)
    memory.load(program, origin)
    return origin + len(program)
