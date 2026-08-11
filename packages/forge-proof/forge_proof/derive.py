"""Vendored proof derivation (byte-faithful port of tools/proof-derive.py).

Reproduces graph.json and metrics.json solely from events.log, per the
Forge Proof Standard derivation rule (proofs/PROOF_SPEC.md §5), plus
demo/_replay_facts.md. The port keeps the canonical tools/ script's exact
logic and JSON serialization so both produce byte-identical artifacts —
that parity is pinned by tests/test_proof_core.py. Stdlib only.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

FIELD_DEFAULTS = {
    "forge_version": "unknown",
    "conforms_to": "proof-spec-0.1",
    "language": "python",
}

_LANGUAGE_HINTS = [
    ("rs", "Rust"),
    ("cpp", "C++"), ("cc", "C++"), ("cxx", "C++"),
    ("hpp", "C++"), ("hxx", "C++"),
    ("py", "python"), ("pyw", "python"),
]


def _subsystem_of(e):
    for note in e.get("notes") or []:
        if str(note).strip().startswith("subsystem:"):
            return str(note).split(":", 1)[1].strip()
    return None


def _infer_language(events):
    """Primary implementation language, inferred from file references in the
    log (task descriptions, evidence records). Pure function of events.log."""
    import re as _re
    hits = Counter()
    stack = list(events)
    while stack:
        v = stack.pop()
        if isinstance(v, dict):
            stack.extend(v.values())
        elif isinstance(v, list):
            stack.extend(v)
        elif isinstance(v, str):
            for ext, lang in _LANGUAGE_HINTS:
                if _re.search(r"\.%s\b" % ext, v):
                    hits[lang] += 1
    if not hits:
        return FIELD_DEFAULTS["language"]
    return max(hits, key=lambda lang: (hits[lang], -("C++|Rust|python".split("|").index(lang))))


def _infer_claims(events, root):
    claims = [c for e in events if e["op"] == "claims_claimed"
              for c in e.get("claims", [])]
    if not claims:
        prop = root / "proposal.json"
        if prop.exists():
            claims = json.loads(prop.read_text(encoding="utf-8")).get("claims", [])
    return claims


def replay(events):
    """Reconstruct final task state and edge list from the event log."""
    status = {}
    priority = {}
    title = {}
    subsystem = {}
    edges = []
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
    deps = {}
    for e in events:
        if e["op"] == "dependency_added":
            deps.setdefault(e["task"], set()).add(e["depends_on"])
    frontier = {}
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
            frontier[e["id"]] = "pending"
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


def derive_dir(example_dir, forge_version="unknown", snapshot=None):
    """Derive graph.json / metrics.json / demo/_replay_facts.md into
    example_dir from its events.log. Byte-parity with
    tools/proof-derive.py main(). Returns a summary dict."""
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
        "log_tail_ts": r["meta"]["last_ts"],
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
        "language": _infer_language(events),
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
        "claims": _infer_claims(events, root),
    }

    (root / "graph.json").write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    (root / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    if snapshot:
        snap_dir = root / "demo" / "snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        (snap_dir / f"{snapshot}.graph.json").write_text(
            json.dumps(graph, indent=2) + "\n", encoding="utf-8")

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
    return {"tasks": len(tasks), "events": len(events), "passes": passes,
            "failures": failures, "minutes": minutes, "status": metrics["status"],
            "max_ready_queue": r["meta"]["max_ready_queue"]}