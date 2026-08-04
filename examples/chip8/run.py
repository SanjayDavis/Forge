"""Entry point: python run.py <rom> [--cycles N] [--seed N] [--trace] [--frame]

Thin wrapper so the proof's commands are checkable as `python run.py ...`
(the canonical CLI form in README §5). Equivalent to `python -m chip8`.
"""
import sys
from chip8.cli import main

if __name__ == "__main__":
    sys.exit(main())