"""4 KiB memory-mapped RAM bus.

CHIP-8 uses 4096 bytes of RAM (0x000-0xFFF). Interpreter/fonts usually live in
0x000-0x1FF; programs are loaded at 0x200 by convention. Byte read/write with
bounds checking.
"""

MEMORY_SIZE = 4096
PROGRAM_START = 0x200


class MemoryError(IndexError):
    """Raised on out-of-range memory access."""


class Memory:
    def __init__(self):
        self._data = bytearray(MEMORY_SIZE)

    @property
    def size(self):
        return MEMORY_SIZE

    def read(self, addr: int) -> int:
        self._check(addr)
        return self._data[addr]

    def write(self, addr: int, value: int):
        self._check(addr)
        self._data[addr] = value & 0xFF

    def read_word(self, addr: int) -> int:
        """Big-endian 16-bit read used by the fetch stage."""
        return (self.read(addr) << 8) | self.read(addr + 1)

    def load(self, data: bytes, base: int = PROGRAM_START):
        """Load a program image into memory, validating the destination range."""
        if base < 0 or base + len(data) > MEMORY_SIZE:
            raise MemoryError(f"load range {base}..{base+len(data)} out of {MEMORY_SIZE} bytes")
        self._data[base:base + len(data)] = data

    def dump(self, start: int = 0, end: int = MEMORY_SIZE, width: int = 16) -> str:
        """Hex dump for diagnostics / demo evidence."""
        lines = []
        for off in range(start, end, width):
            chunk = bytes(self._data[off:off + width])
            hexs = " ".join(f"{b:02x}" for b in chunk)
            asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{off:04x}  {hexs:<47}  {asc}")
        return "\n".join(lines)

    def _check(self, addr: int):
        if not (0 <= addr < MEMORY_SIZE):
            raise MemoryError(f"address {addr:#x} out of range [0x000, 0xFFF]")