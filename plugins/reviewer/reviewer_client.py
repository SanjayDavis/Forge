"""Reference reviewer client — the REVIEWER slot, runnable.

The composed pipeline in one runnable: the executor slot produces
hard evidence (write stub artifacts, machine-check them), then the
reviewer slot judges the acceptance criteria against that evidence
and the kernel decides done. Deterministic checks are the executor's
hard evidence; architecture/design judgment is the reviewer's soft
evidence — the roadmap's two layers, in order.

    python plugins/reviewer/reviewer_client.py -d PROJECT [--limit N]

An LLM reviewer is this loop with a different judge.
"""
from __future__ import annotations

import argparse
import os
import sys

from forge import ForgeClient, GraphError
from plugins.executor import default_worker
from plugins.reviewer import ReferenceReviewer


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="reviewer-client",
        description="reference reviewer: walk ready tasks, write stub "
                    "artifacts (executor slot), judge acceptance "
                    "(reviewer slot), let the kernel verify")
    ap.add_argument("-d", "--dir", default=".",
                    help="project directory (default: .)")
    ap.add_argument("--artifact-dir", default=None,
                    help="where artifacts land (default: DIR/artifacts)")
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after N tasks (default: all ready tasks)")
    args = ap.parse_args(argv)

    artifact_dir = args.artifact_dir or os.path.join(args.dir, "artifacts")
    client = ForgeClient(args.dir)
    reviewer = ReferenceReviewer(client)
    results = []
    while args.limit is None or len(results) < args.limit:
        task = client.next()
        if task is None:
            break
        tid = task["id"]
        # ---- executor slot: claim, work, hard evidence
        try:
            client.start(tid)
        except GraphError:
            pass  # in_progress = resume (retry path, §10.2)
        ctx = client.context(tid)
        result = default_worker(ctx, artifact_dir=artifact_dir)
        ok = all(
            isinstance(a, dict) and "path" in a and "bytes" in a
            and os.path.exists(a["path"])
            and os.path.getsize(a["path"]) == a["bytes"]
            for a in result.get("artifacts") or [])
        if not ok:
            results.append(reviewer._reject(
                tid, "executor slot: artifact check failed"))
            continue
        for a in result["artifacts"]:
            client.attach_evidence(
                tid, "hard", "executor:artifact-check",
                f"{a['path']} exists ({a['bytes']} bytes)")
        # ---- reviewer slot: judge, soft evidence, kernel decides
        results.append(reviewer.review(tid))
    for r in results:
        if r["status"] == "done":
            print(f"done: {r['task']} — approved, soft evidence attached")
        elif r["status"] == "needs_revision":
            print(f"needs_revision: {r['task']} — {r['reason']}")
        else:
            print(f"blocked: {r['task']} — {r['reason']}")
    if not results or args.limit is None:
        print("nothing ready — all done or blocked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
