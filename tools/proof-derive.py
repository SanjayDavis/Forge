#!/usr/bin/env python3
"""Derive Proof artifacts from a Forge events.log.

Reproduces graph.json and metrics.json solely from events.log, per the
Forge Proof Standard derivation rule (§5). Also emits _replay_facts.md,
numbered milestones a human turns into replay.md.

Usage:
    python tools/proof-derive.py examples/<name>
"""
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

FIELD_DEFAULTS = {
    "forge_version": "unknown",
    "conforms_to": "proof-spec-0.1",
    "language": "python",
}


def replay(events):
    """Reconstruct final task state and edge list from the event log."""
    status = {}   # task id -> 'done' | 'in_progress' | 'needs_revision' | 'todo'
    priority = {}
    title = {}
    edges = []    # (dep, targ)
    milestones = []
    meta = {
        "op_counts": Counter(e["op"] for e in events),
        "first_ts": min(e.get("ts") for e in events if e.get("ts")),
        "last_ts": max(e.get("ts") for e in events if e.get("ts")),
        "proposal_id": next((e["id"] for e in events if e["op"] == "proposal_committed"), None),
    }
    for e in events:
        op, seq = e["op"], e["seq"]
        if op == "task_created":
            status[e["id"]] = "todo"
            priority[e["id"]] = e.get("priority", "medium")
            title[e["id"]] = e.get("title", e["id"])
            milestones.append((seq, "task_created", e["id"], "planned"))
        elif op == "task_started":
            status[e["id"]] = "in_progress"
        elif op == "verification_failed":
            status[e["id"]] = "needs_revision"
            milestones.append((seq, "verification_failed", e["id"], e.get("reason", "")))
        elif op == "verification_passed":
            status[e["id"]] = "done"
            milestones.append((seq, "verification_passed", e["id"], ""))
        elif op == "task_reopened":
            status[e["id"]] = "todo"
            milestones.append((seq, "task_reopened", e["id"], ""))
        elif op == "task_retried":
            status[e["id"]] = "in_progress"
            milestones.append((seq, "task_retried", e["id"], ""))
        elif op == "dependency_added":
            edges.append((e["depends_on"], e["task"]))
    return {
        "tasks": {tid: {"id": tid, "title": title[tid], "status": status[tid],
                        "priority": priority[tid]}
                  for tid in status},
        "edges": edges, "status": status, "meta": meta,
        "milestones": milestones,
    }


def main(example_dir, forge_version="unknown"):
    root = Path(example_dir)
    events = [json.loads(l) for l in
              (root / "events.log").read_text(encoding="utf-8").splitlines() if l.strip()]
    r = replay(events)
    counts = r["meta"]["op_counts"]

    tasks = []
    for tid in sorted(r["tasks"], key=lambda t: min(e["seq"] for e in events
                                                    if e["op"] == "task_created" and e["id"] == t)):
        t = r["tasks"][tid]
        tasks.append({"id": t["id"], "title": t["title"], "status": t["status"],
                      "priority": t["priority"], "subsystem": t.get("subsystem")})

    graph = {
        "proof": root.name,
        "forge_version": forge_version,
        "derived_from": "events.log",
        "log_tail_ts": r["meta"]["last_ts"],  # pure function of the log: artifacts must
        # regenerate byte-identically; a wall-clock timestamp would break that
        "tasks": tasks,
        "dependencies": [{"task": t, "depends_on": d} for d, t in r["edges"]],
    }

    t0 = datetime.fromisoformat(r["meta"]["first_ts"].replace("Z", "+00:00"))
    t1 = datetime.fromisoformat(r["meta"]["last_ts"].replace("Z", "+00:00"))
    minutes = round((t1 - t0).total_seconds() / 60)

    passes = counts.get("verification_passed", 0)
    failures = counts.get("verification_failed", 0)
    metrics = {
        "proof": root.name,
        "status": "completed" if all(t["status"] == "done" for t in tasks) else "partial",
        "language": FIELD_DEFAULTS["language"],
        "tasks": len(tasks),
        "events": len(events),
        "verification_passes": passes,
        "verification_failures": failures,
        "retries": counts.get("task_retried", 0),
        "duration_minutes": minutes,
        "llm": "not recorded",
        "forge_version": forge_version,
        "conforms_to": FIELD_DEFAULTS["conforms_to"],
        "claims": [],  # filled by the human author in README
    }

    (root / "graph.json").write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    (root / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    # replay facts: ordered milestones (human turns this narrative)
    by_task = {}
    for m in r["milestones"]:
        by_task.setdefault(m[2], []).append(m)
    lines = ["# Replay facts (derived from events.log)\n",
             f"- tasks: {len(tasks)} · events: {len(events)} · "
             f"passes: {passes} · failures: {failures} · retries: {metrics['retries']} · "
             f"duration: {minutes} min\n"]
    for seq, op, tid, note in sorted(r["milestones"]):
        note = f" — {note}" if note else ""
        lines.append(f"- seq {seq}  {op:<22} {tid}{note}")
    (root / "demo").mkdir(exist_ok=True)
    (root / "demo" / "_replay_facts.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"derived {root.name}: {len(tasks)} tasks, {len(events)} events, "
          f"{passes} passes, {failures} failures, {minutes} min")
    print(f"  -> {root/'graph.json'}, {root/'metrics.json'}, "
          f"{root/'demo'/'_replay_facts.md'}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("example_dir")
    ap.add_argument("--forge-version", default="unknown")
    a = ap.parse_args()
    main(a.example_dir, a.forge_version)