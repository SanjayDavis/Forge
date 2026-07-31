"""Reference executor client — the EXECUTOR slot, runnable.

The same loop the reference client (plugins/reference/) proves for the
human, driven by the executor plugin: next -> start -> context -> work
-> hard evidence -> verify. An LLM executor is this loop with a
different worker.

    python plugins/executor/executor_client.py -d PROJECT [--limit N]
"""
from __future__ import annotations

import argparse
import os
import sys

from forge import ForgeClient
from plugins.executor import ReferenceExecutor


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="executor-client",
        description="reference executor: walk ready tasks, write stub "
                    "artifacts, let the kernel verify")
    ap.add_argument("-d", "--dir", default=".",
                    help="project directory (default: .)")
    ap.add_argument("--artifact-dir", default=None,
                    help="where artifacts land (default: DIR/artifacts)")
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after N tasks (default: all ready tasks)")
    args = ap.parse_args(argv)

    artifact_dir = args.artifact_dir or os.path.join(args.dir, "artifacts")
    client = ForgeClient(args.dir)
    executor = ReferenceExecutor(client, artifact_dir=artifact_dir)
    results = executor.run(limit=args.limit)
    for r in results:
        if r["status"] == "done":
            print(f"done: {r['task']} — {len(r['artifacts'])} artifact(s), "
                  "hard evidence attached")
        elif r["status"] == "expanded":
            print(f"expanded: {r['task']} → {', '.join(r['children'])}")
        else:
            print(f"needs_revision: {r['task']} — {r['reason']}")
    if not results or args.limit is None:
        print("nothing ready — all done or blocked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
