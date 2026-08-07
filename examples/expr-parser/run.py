"""Entry point: python run.py <expr> | python run.py test | python run.py build

Thin wrapper so the proof's commands are checkable as `python run.py ...`
(the canonical CLI form referenced in README §4/§5). Equivalent to the
make/./expr commands; keeps the Python out of the build path (C3) — this
file only shells out.
"""
import subprocess
import sys


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("build", "make"):
        return subprocess.call(["make"])
    if args[0] in ("test",):
        return subprocess.call(["make", "test"])
    if args[0] in ("clean",):
        return subprocess.call(["make", "clean"])
    # Treat remaining args as an expression (single-shot mode).
    expr = " ".join(args)
    return subprocess.call(["expr", expr])


if __name__ == "__main__":
    sys.exit(main())
