#!/usr/bin/env python
"""Verify each fixture parses under the real rcli binary (empty.csv -> exit 1).

Matches the fixtures task acceptance: every fixture parses via the CLI except
empty.csv, which must be an Empty error (exit 1).
"""
import os
import subprocess
import sys

BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "target", "debug", "rcli.exe")

CASES = [
    # (fixture, expect_success)
    ("numbers.csv", True),
    ("mixed.csv", True),
    ("quoted.csv", True),
    ("unicode.csv", True),
    ("header-only.csv", True),
    ("crlf.csv", True),
    ("empty.csv", False),
]

ok = True
for name, expect in CASES:
    path = os.path.join("fixtures", name)
    r = subprocess.run([BIN, "stats", path], capture_output=True, text=True)
    good = (r.returncode == 0) == expect
    ok = ok and good
    print(f"  {name:18} exit={r.returncode} (expect_success={expect}) -> {'ok' if good else 'BAD'}")

print("FIXTURES_OK" if ok else "FIXTURES_BAD")
sys.exit(0 if ok else 1)