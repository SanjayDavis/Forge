#!/usr/bin/env bash
# demo/record.sh — capture REAL terminal evidence for Proof #5.
#
# Records four real captures into examples/swarm/demo/record/*.txt:
#   01-demo.txt       swarm platform actually running (jobs in -> drained)
#   02-tests.txt      the project test suite passing (197 tests)
#   03-invariants.txt S1..S10 invariant verdict on the final bundle
#   04-conformance.txt proof-check conformance verdict
#
# Clean-checkout reproducible: the project tree is materialised FRESH by
# source_gen.py (never reuses the .proof-work run leftover), and the
# commands are exactly the README's commands.
#
# Usage:  PYTHON=/path/to/python bash examples/swarm/demo/record.sh
#
# Requires: matplotlib + networkx + pytest in PYTHON's env (same env as the
# README tells you to create). Runs from the REPO ROOT so all paths are
# absolute; never inherits PYTHONPATH.
set -euo pipefail
cd "$(dirname "$0")/../../.."      # repo root (examples/swarm/demo -> root)
PY=${PYTHON:-python3}
command -v "$PY" >/dev/null 2>&1 || PY=python
export PYTHONPATH=                # never inherit hermes-agent site-packages

P=examples/swarm
RECORD=$P/demo/record
TREE=$P/demo/_tree
mkdir -p "$RECORD"

echo "== materialising fresh swarm tree (source_gen.py)"
rm -rf "$TREE"
"$PY" "$P/source_gen.py" --tree "$TREE" --manifest "$P/demo/_manifest.json" >/dev/null

echo "== recording 01: demo_drain (artifact actually running)"
rm -f "$RECORD/session.db"
d=$("$PY" "$TREE/scripts/demo_drain.py" --db "$RECORD/session.db")
printf '$ python scripts/demo_drain.py --db session.db\n%s\ndemo drain OK\n' "$d" > "$RECORD/01-demo.txt"

echo "== recording 02: pytest suite (tests passing)"
t=$(cd "$TREE" && "$PY" -m pytest tests -p no:cacheprovider -o addopts="" --no-header -q 2>&1 | tail -5)
printf 'cd swarm-project\n$ python -m pytest tests -q\n%s\n' "$t" > "$RECORD/02-tests.txt"

echo "== recording 03: S1..S10 invariant checker"
s=$("$PY" "$P/check_invariants.py" "$P" 2>&1)
printf '%s\n' "$s" > "$RECORD/03-invariants.txt"

echo "== recording 04: proof-check conformance"
c=$("$PY" tools/proof-check.py "$P" 2>&1)
printf '%s\n' "$c" > "$RECORD/04-conformance.txt"

echo "recorded: $(ls "$RECORD")"