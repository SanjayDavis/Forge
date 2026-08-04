"""CLI registration for forge-planner (the `plan` command).

The forge CLI discovers commands through the ``forge.commands``
entry-point group. This module is that entry point: it adds the `plan`
subparser (owning its argument shape) and returns the command handler.
"""

from __future__ import annotations

import argparse
import json

from forge import ForgeClient

from .planner import ReferencePlanner


def register(subparsers: argparse._SubParsersAction) -> dict:
    """Entry point for ``forge.commands``: add `plan` and return its handler."""
    c = subparsers.add_parser(
        "plan", help="reference planner: GOAL -> proposal (SPEC §9); commit is opt-in")
    c.add_argument("goal")
    c.add_argument("--priority", choices=["low", "medium", "high"], default="medium")
    c.add_argument("--confidence", type=float, default=0.9)
    c.add_argument("--commit", action="store_true",
                   help="commit the proposal through the kernel (atomic: whole or nothing)")
    return {"plan": cmd_plan}


def cmd_plan(args, k=None) -> int:
    client = ForgeClient(args.dir)  # the CLI speaks the SDK too
    proposal = ReferencePlanner(client).plan(
        args.goal, priority=args.priority, confidence=args.confidence)
    if args.commit:
        result = client.propose(proposal)  # envelope + kernel verdict
        print(f"committed {result['committed']} events from {result['proposal_id']} "
              f"(confidence {result['confidence']}) -> project now has "
              f"{result['tasks']} tasks")
    else:
        print(json.dumps(proposal, ensure_ascii=False, indent=2))
    return 0
