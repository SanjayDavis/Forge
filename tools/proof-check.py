#!/usr/bin/env python3
"""Validate a proof bundle against the Forge Proof Standard (proofs/PROOF_SPEC.md).

Checks the conformance checklist (§6): required artifacts, raw events.log,
graph/log consistency, metrics derivability, media constraints.

Usage:
    python tools/proof-check.py examples/<name>
Exit code 0 = conforming, 1 = non-conforming (problems printed).
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REQUIRED_FILES = ["README.md", "events.log", "graph.json", "graph.png",
                  "replay.md", "metrics.json", "demo.mp4"]
REQUIRED_METRICS = ["proof", "status", "language", "tasks", "events",
                    "verification_passes", "verification_failures", "retries",
                    "duration_minutes", "llm", "forge_version", "conforms_to",
                    "claims"]
README_SECTIONS = ["What was built", "Why this proof exists", "Final architecture",
                   "Commands", "Reproduce", "Artifact index", "Behavior notes",
                   "Lessons learned"]


def problems(root: Path):
    out = []

    # 1. README with all 8 sections
    readme = root / "README.md"
    if not readme.exists():
        out.append("missing README.md")
    else:
        text = readme.read_text(encoding="utf-8")
        for sec in README_SECTIONS:
            if not re.search(r"^#{1,3}\s+.*" + re.escape(sec), text, re.M):
                out.append(f"README missing section: {sec}")

    # 2. events.log: raw, contiguous seq
    ev_file = root / "events.log"
    if not ev_file.exists():
        out.append("missing events.log")
    else:
        events = []
        for i, line in enumerate(ev_file.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                out.append(f"events.log line {i} is not valid JSON")
                continue
            events.append(ev)
        if events:
            seqs = [e["seq"] for e in events if "seq" in e]
            if seqs != list(range(1, len(seqs) + 1)):
                out.append("events.log seq not contiguous from 1")
            counts = Counter(e["op"] for e in events)
            if not any(op.startswith("task_created") for op in counts):
                out.append("events.log has no task_created events")

    # 3. graph.json matches events.log
    gf = root / "graph.json"
    if not gf.exists():
        out.append("missing graph.json")
    else:
        g = json.loads(gf.read_text(encoding="utf-8"))
        for t in g.get("tasks", []):
            for k in ("id", "title", "status", "priority"):
                if k not in t:
                    out.append(f"graph.json task {t.get('id')} missing '{k}'")
        if events:
            created = {e["id"] for e in events if e["op"] == "task_created"}
            gids = {t["id"] for t in g.get("tasks", [])}
            if gids != created:
                out.append("graph.json task ids differ from events.log")
            deps = {(e["depends_on"], e["task"]) for e in events
                    if e["op"] == "dependency_added"}
            gdeps = {(d["depends_on"], d["task"]) for d in g.get("dependencies", [])}
            if gdeps != deps:
                out.append("graph.json dependencies differ from events.log")

    # 4/5. graph.png, replay.md presence
    for f in ("graph.png", "replay.md"):
        p = root / f
        if not p.exists():
            out.append(f"missing {f}")
    if (root / "replay.md").exists():
        rt = (root / "replay.md").read_text(encoding="utf-8")
        for kw in ("Goal", "Outcome", "Timeline", "Turning points"):
            if kw not in rt:
                out.append(f"replay.md missing '{kw}'")

    # 6. metrics.json derivable
    mf = root / "metrics.json"
    if not mf.exists():
        out.append("missing metrics.json")
    else:
        m = json.loads(mf.read_text(encoding="utf-8"))
        for k in REQUIRED_METRICS:
            if k not in m:
                out.append(f"metrics.json missing field '{k}'")
        if events and "tasks" in m and "events" in m:
            if m["tasks"] != len({e["id"] for e in events if e["op"] == "task_created"}):
                out.append("metrics.json 'tasks' != log task count")
            if m["events"] != len(events):
                out.append("metrics.json 'events' != log line count")
            counts = Counter(e["op"] for e in events)
            pairs = [("verification_passes", "verification_passed"),
                     ("verification_failures", "verification_failed"),
                     ("retries", "task_retried")]
            for key, op in pairs:
                if key in m and m[key] != counts.get(op, 0):
                    out.append(f"metrics.json '{key}' != log count ({m[key]} vs {counts.get(op, 0)})")

    # 7. screenshots >= 2 PNGs
    shots = sorted((root / "screenshots").glob("*.png")) if (root / "screenshots").exists() else []
    if len(shots) < 2:
        out.append(f"screenshots/ has {len(shots)} PNGs (need >= 2)")

    # 8. demo.mp4 constraints (<= 120s, <= 720p)
    demo = root / "demo.mp4"
    if demo.exists():
        try:
            r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=width,height",
                                "-show_entries", "format=duration",
                                "-of", "json", str(demo)], capture_output=True, text=True)
            info = json.loads(r.stdout)
            dur = float(info["format"]["duration"])
            w, h = info["streams"][0]["width"], info["streams"][0]["height"]
            if dur > 120:
                out.append(f"demo.mp4 too long: {dur:.0f}s (> 120s)")
            if w > 1280 or h > 720:
                out.append(f"demo.mp4 too large: {w}x{h} (> 720p)")
        except Exception as e:
            out.append(f"demo.mp4 unreadable: {e}")

    # 9. clean-checkout run commands (static sanity: entrypoints exist)
    if not (root / "run.py").exists():
        out.append("no run.py entrypoint (README commands not checkable)")

    # 10. INDEX entry
    idx = root.parent.parent / "proofs" / "INDEX.md"
    if idx.exists() and root.name not in idx.read_text(encoding="utf-8"):
        out.append(f"no INDEX.md entry for {root.name}")

    return out


def main(proof_dir):
    root = Path(proof_dir)
    probs = problems(root)
    if probs:
        print(f"NON-CONFORMING: {root.name}")
        for p in probs:
            print(f"  - {p}")
        return 1
    print(f"CONFORMING: {root.name} — all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))