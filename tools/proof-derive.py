#!/usr/bin/env python3
"""Derive Proof artifacts from a Forge events.log.

Reproduces graph.json and metrics.json solely from events.log, per the
Forge Proof Standard derivation rule (§5). Also emits _replay_facts.md,
numbered milestones a human turns into replay.md. metrics.json includes
max_ready_queue (widest simultaneously-executable frontier — a graph
parallelism property, independent of the executor).

Usage:
    python tools/proof-derive.py examples/<name> [--forge-version X] [--snapshot NAME]
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


def _subsystem_of(e):
    """Subsystem tag from a task_created event's notes list.

    The proposal schema (docs/EVENTS.md) does not define a top-level
    `subsystem` field; Proof #5's proposal embeds it as a structured note
    ("subsystem: auth"). Parsing the note keeps graph.json a pure function
    of events.log. Proofs whose notes do not carry the marker get None
    (graph.png falls back to the 'other' border color).
    """
    for note in e.get("notes") or []:
        if str(note).strip().startswith("subsystem:"):
            return str(note).split(":", 1)[1].strip()
    return None


def replay(events):
    """Reconstruct final task state and edge list from the event log."""
    status = {}   # task id -> 'done' | 'in_progress' | 'needs_revision' | 'todo'
    priority = {}
    title = {}
    subsystem = {}
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
            subsystem[e["id"]] = _subsystem_of(e)
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
    # --- max ready queue: the widest simultaneously-executable frontier ---
    # A property of the project's dependency structure (graph parallelism),
    # not of the executor: at the busiest point, how many tasks were ready.
    # Pass 1: full DAG (the plan fixes all edges before execution starts).
    deps = {}
    for e in events:
        if e["op"] == "dependency_added":
            deps.setdefault(e["task"], set()).add(e["depends_on"])
    # Pass 2: simulate the frontier over the event stream.
    frontier = {}  # tid -> 'pending' | 'running' | 'done' | 'cancelled'
    peak, peak_seq, peak_ev = 0, None, ("", "")

    def ready_count():
        return sum(1 for t, s in frontier.items()
                   if s == "pending" and all(frontier.get(d) == "done"
                                             for d in deps.get(t, ())))

    for e in events:
        op, seq = e["op"], e["seq"]
        if op == "task_created":
            frontier[e["id"]] = "pending"
        elif op == "task_started":
            frontier[e["id"]] = "running"
        elif op == "verification_passed":
            frontier[e["id"]] = "done"
        elif op == "verification_failed":
            frontier[e["id"]] = "pending"   # executable again (retry)
        elif op == "task_reopened":
            frontier[e["id"]] = "pending"
        elif op == "task_retried":
            frontier[e["id"]] = "running"
        elif op == "task_cancelled":
            frontier[e["id"]] = "cancelled"
        rc = ready_count()
        if rc > peak:
            peak, peak_seq, peak_ev = rc, seq, (op, e.get("id", ""))
    meta["max_ready_queue"] = peak
    meta["max_ready_queue_at"] = {"seq": peak_seq, "event": peak_ev[0], "id": peak_ev[1]}
    return {
        "tasks": {tid: {"id": tid, "title": title[tid], "status": status[tid],
                        "priority": priority[tid], "subsystem": subsystem.get(tid)}
                  for tid in status},
        "edges": edges, "status": status, "meta": meta,
        "milestones": milestones,
    }


def main(example_dir, forge_version="unknown", snapshot=None):
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
        "max_ready_queue": r["meta"]["max_ready_queue"],
        "max_ready_queue_at": r["meta"]["max_ready_queue_at"],
        "duration_minutes": minutes,
        "llm": "not recorded",
        "forge_version": forge_version,
        "conforms_to": FIELD_DEFAULTS["conforms_to"],
        "claims": [c for e in events if e["op"] == "claims_claimed"
                   for c in e.get("claims", [])],
    }

    (root / "graph.json").write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    (root / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    if snapshot:  # keep an evolving-demo snapshot of the graph per subsystem milestone
        snap_dir = root / "demo" / "snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        (snap_dir / f"{snapshot}.graph.json").write_text(
            json.dumps(graph, indent=2) + "\n", encoding="utf-8")

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
          f"{passes} passes, {failures} failures, {minutes} min, "
          f"max_ready_queue={r['meta']['max_ready_queue']}")
    print(f"  -> {root/'graph.json'}, {root/'metrics.json'}, "
          f"{root/'demo'/'_replay_facts.md'}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("example_dir")
    ap.add_argument("--forge-version", default="unknown")
    ap.add_argument("--snapshot", default=None,
                    help="copy graph.json to demo/snapshots/<name>.graph.json "
                         "(per-subsystem evidence for an evolving demo)")
    a = ap.parse_args()
    main(a.example_dir, a.forge_version, a.snapshot)