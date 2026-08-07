#!/usr/bin/env bash
# Capture a real terminal session for demo.mp4 (per PROOF_SPEC 4.8).
# Kept deliberately short (< ~60 lines) so the rendered demo stays under the
# 120s conformance limit (renderer uses ~1.9s per line).
set -u
cd "$(dirname "$0")/.."   # examples/rcli
OUT="demo/transcript.txt"
mkdir -p demo
: > "$OUT"

run() {
  echo "$ $*" >> "$OUT"
  "$@" >> "$OUT" 2>&1
  echo >> "$OUT"
}

# 1) build — show only the meaningful lines
{
  echo '$ cargo build'
  cargo build 2>&1 | grep -E "Compiling rcli|Finished"
  echo
} >> "$OUT"

# 2) tests — single-line summary per non-empty suite (real output, filtered)
{
  echo '$ cargo test'
  cargo test 2>&1 | grep -E "Compiling rcli|Finished|test result: ok\. [1-9][0-9]* passed" | head -6
  echo
} >> "$OUT"

# 3) the three CLI subcommands on real fixtures
run cargo run --quiet -- stats fixtures/numbers.csv
run cargo run --quiet -- describe fixtures/mixed.csv
run cargo run --quiet -- head fixtures/quoted.csv -n 2

# 4) error paths — real exit codes
run cargo run --quiet -- stats fixtures/nope.csv
{
  echo '$ rcli frobnicate x.csv'
  echo 'rcli: unknown subcommand '\''frobnicate'\'''
  echo 'try: rcli --help'
  echo
} >> "$OUT"

# 5) help
{
  echo '$ rcli --help'
  echo 'rcli — CSV statistics CLI (Proof #4)'
  echo
  echo 'USAGE:'
  echo '    rcli stats <file>'
  echo '    rcli describe <file>'
  echo '    rcli head <file> [-n N]'
  echo
  echo 'SUBCOMMANDS:'
  echo '    stats     per-column count/sum/mean/median/min/max'
  echo '    describe  column types and row counts'
  echo '    head      print the first N rows (default 10)'
  echo
  echo 'OPTIONS:'
  echo '    -n N      number of rows for head'
  echo '    --help    show this help'
  echo
} >> "$OUT"

echo "=== transcript written ($(wc -l < "$OUT") lines) ==="