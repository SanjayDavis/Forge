"""CLI registration for forge-bharatcode (the `plan-bharatcode` command)."""

from __future__ import annotations

import argparse
import json
import os
import sys

from forge import ForgeClient, ProposalError, GraphError

from .planner import BharatCodePlanner, BharatCodeError


def register(subparsers: argparse._SubParsersAction) -> dict:
    c = subparsers.add_parser(
        "plan-bharatcode",
        help="LLM planner via BharatCode's model API: GOAL -> proposal (SPEC §9)")
    c.add_argument("goal")
    c.add_argument("--priority", choices=["low", "medium", "high"], default="medium")
    c.add_argument("--confidence", type=float, default=0.9)
    c.add_argument("--model", default=None, help="BharatCode model id (default qwen-3.8-27b)")
    c.add_argument("--commit", action="store_true",
                   help="commit the proposal through the kernel (atomic)")
    return {"plan-bharatcode": cmd_plan_bharatcode}


def cmd_plan_bharatcode(args, k=None) -> int:
    client = ForgeClient(args.dir)
    if args.model:
        os.environ.setdefault("BHARATCODE_MODEL", args.model)
    try:
        planner = BharatCodePlanner(client, model=args.model)
        proposal = planner.plan(args.goal, priority=args.priority,
                                confidence=args.confidence)
    except (BharatCodeError, ProposalError) as e:
        print(f"planning failed: {e}", file=sys.stderr)
        return 1
    if args.commit:
        try:
            result = client.propose(proposal)
        except (ProposalError, GraphError) as e:
            print(f"commit failed: {e}", file=sys.stderr)
            return 1
        print(f"committed {result['committed']} events from {result['proposal_id']} "
              f"(confidence {result['confidence']}) -> project now has "
              f"{result['tasks']} tasks")
    else:
        print(json.dumps(proposal, ensure_ascii=False, indent=2))
    return 0
