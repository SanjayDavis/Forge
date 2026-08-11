"""CLI registration for forge-proof (the `proof` command).

Follows the forge.commands entry-point contract (see forge/plugins.py):
``register(subparsers)`` adds the `proof` subparser with its own
argument shape and returns the handler map. The handler never receives
a Kernel (main() dispatches proof outside the project gate) — proof
tooling is stdlib-only and kernel-free by design.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import check as proof_check
from . import derive as proof_derive
from . import replay as proof_replay
from .bundle import bundle_dir


def register(subparsers: argparse._SubParsersAction) -> dict:
    """Entry point for ``forge.commands``: add `proof` and return its handler."""
    c = subparsers.add_parser(
        "proof", help="proof evidence pipeline: check / derive / replay / "
                     "bundle (provided by forge-proof)")
    sub = c.add_subparsers(dest="proof_cmd", required=True, metavar="SUB",
                           title="proof subcommands")
    pc = sub.add_parser("check", help="validate a proof bundle against the "
                         "Proof Standard §6 conformance checklist")
    pc.add_argument("dir")
    pd = sub.add_parser("derive", help="derive graph.json/metrics.json/replay "
                         "facts from events.log (§5 derivation rule)")
    pd.add_argument("dir")
    pd.add_argument("--forge-version", default="unknown")
    pd.add_argument("--snapshot", default=None,
                    help="also copy graph.json to demo/snapshots/<name>.graph.json")
    pr = sub.add_parser("replay", help="render replay.md from the derived facts "
                         "(Goal/Outcome/Timeline/Turning points, seq citations)")
    pr.add_argument("dir")
    pb = sub.add_parser("bundle", help="emit the full artifact bundle "
                         "(README/events.log/graph.json/graph.png/replay.md/"
                         "metrics.json/screenshots/demo.mp4) and validate it")
    pb.add_argument("dir")
    pb.add_argument("--forge-version", default="unknown")
    return {"proof": cmd_proof}


def _req_dir(path: str) -> Path | None:
    root = Path(path)
    if not root.is_dir():
        print(f"error: {path} is not a directory", file=sys.stderr)
        return None
    return root


def cmd_proof(args, k=None) -> int:
    """Handler for all proof subcommands (k is always None — proof never
    needs a project Kernel; main() bypasses the project gate for it)."""
    root = _req_dir(args.dir)
    if root is None:
        return 1
    if args.proof_cmd == "check":
        return proof_check.verdict(root, proof_check.problems(root))
    if args.proof_cmd == "derive":
        try:
            proof_derive.derive_dir(str(root), forge_version=args.forge_version,
                                    snapshot=args.snapshot)
            return 0
        except FileNotFoundError:
            print(f"error: {root / 'events.log'} not found — nothing to derive",
                  file=sys.stderr)
            return 1
    if args.proof_cmd == "replay":
        try:
            proof_replay.render_dir(str(root))
            return 0
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
    if args.proof_cmd == "bundle":
        return bundle_dir(str(root), forge_version=args.forge_version)
    print(f"error: unknown proof subcommand {args.proof_cmd!r}", file=sys.stderr)
    return 1