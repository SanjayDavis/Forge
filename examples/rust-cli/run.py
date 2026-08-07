"""Entry point: python run.py <subcommand> <file> [-n N] | python run.py test

Thin wrapper so the proof's commands are checkable as `python run.py ...`
(the canonical CLI form referenced in README §4/§5). Equivalent to the
cargo/rcli commands; keeps Python out of the build path (C3) — this file
only shells out.
"""
import subprocess
import sys


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("build", "make"):
        return subprocess.call(["cargo", "build"])
    if args[0] in ("test",):
        return subprocess.call(["cargo", "test"])
    if args[0] in ("clean",):
        return subprocess.call(["cargo", "clean"])
    # rcli subcommand form: stats|describe|head <file> [-n N]
    return subprocess.call(["cargo", "run", "--quiet", "--", *args])


if __name__ == "__main__":
    sys.exit(main())