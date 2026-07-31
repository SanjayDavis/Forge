"""Reference client — the HUMAN.

The first client was the planner. The second is a person: a tiny script
that proves the SDK is comfortable for a non-AI. If a human can't use
ForgeClient comfortably, an AI won't either.

    next -> do the work -> attach hard evidence -> verify

The human never touches the graph. ForgeClient is the only surface,
exactly like the planner. The loop stops when nothing is ready.
"""
from __future__ import annotations

import argparse
import sys

from forge import ForgeClient


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="reference-client",
        description="human client: walk the next task, do it, verify it")
    ap.add_argument("-d", "--dir", default=".",
                    help="project directory (default: .)")
    ap.add_argument("--auto", action="store_true",
                    help="no prompts — for tests and CI")
    args = ap.parse_args(argv)

    client = ForgeClient(args.dir)
    while True:
        task = client.next()
        if task is None:
            print("nothing ready — all done or blocked")
            return 0
        tid = task["id"]
        client.start(tid)  # claim it — dependents stay blocked until verified
        print(f"next: {tid} — {task['title']} ({task['status']})")
        if not args.auto:
            input("Press Enter when done: ")
        client.attach_evidence(tid, "hard", "human",
                               "completed by hand via reference client")
        client.verify(tid)  # the kernel decides; the human never does
        print(f"verified: {tid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
