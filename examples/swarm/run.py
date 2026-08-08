#!/usr/bin/env python3
"""Proof #5 (swarm) entry point: python run.py [--smoke | --check | --derive]

Thin wrapper so the proof's README commands are checkable from a clean
checkout as `python run.py ...`:

  python run.py --smoke   harness self-test (8 tasks, 2 agent processes,
                          real files, ~seconds) — proves the multi-agent
                          machinery end to end
  python run.py --check   run the S1..S10 invariant checker on this proof
                          bundle
  python run.py --derive  regenerate graph.json/metrics.json from
                          events.log (proof-derive, byte-identical)

Nothing here touches the kernel; the public SDK + proof tooling only.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))


def main():
    ap = argparse.ArgumentParser(description="Proof #5 (swarm) entry point")
    ap.add_argument("--smoke", action="store_true", help="harness self-test")
    ap.add_argument("--check", action="store_true",
                    help="run the S1..S10 invariant checker")
    ap.add_argument("--derive", action="store_true",
                    help="re-derive graph.json/metrics.json from events.log")
    args = ap.parse_args()

    sys.path.insert(0, HERE)
    sys.path.insert(0, REPO)
    if args.smoke:
        from run_agents import run_smoke
        run_smoke()
        return 0
    if args.check:
        from check_invariants import main as check_main
        sys.argv = [sys.argv[0], HERE]
        return check_main()
    if args.derive:
        r = subprocess.run([sys.executable,
                            os.path.join(REPO, "tools", "proof-derive.py"),
                            HERE, "--forge-version", "0.1.0a3"])
        return r.returncode
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
