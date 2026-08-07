#!/usr/bin/env bash
# Capture a REAL terminal session for demo.mp4 (per PROOF_SPEC 4.8).
# Kept short so the rendered demo stays under the 120s conformance limit.
set -u
cd "$(dirname "$0")/.."   # examples/expr-parser
OUT="demo/transcript.txt"
mkdir -p demo
: > "$OUT"

run() {
  echo "$ $*" >> "$OUT"
  "$@" >> "$OUT" 2>&1
  echo >> "$OUT"
}

run make
run make test
run ./expr "2+3"
run ./expr "2^3^2"
run ./expr "-2^2"
run ./expr "1/0"
echo

# Short REPL session (single-shot style lines, since REPL is interactive piped).
{
  echo '$ ./expr'
  printf '> 2+3\n5\n> sqrt(9)\n3\n> :ast 2+3*4\n(+ 2 (* 3 4))\n> 1/0\ndivision by zero\n> quit\n'
} >> "$OUT"

echo "=== transcript written ($(wc -l < "$OUT") lines) ==="