"""replay.md renderer for `forge proof replay`.

Builds a human-readable timeline with the Proof Standard's required
structure (Goal / Outcome / Timeline / Turning points, with `seq`
citations) purely from machine-derived inputs: demo/_replay_facts.md and
metrics.json. When proposal.json carries a `reason`, it becomes the Goal;
otherwise the Goal points at the README.
"""
from __future__ import annotations

import json
from pathlib import Path

TURNING_OPS = ("verification_failed", "task_retried", "task_reopened")


def render_replay(name: str, facts: str, metrics: dict,
                  goal: str | None = None) -> str:
    lines = facts.splitlines()
    timeline = [ln for ln in lines if ln.strip().startswith("- seq ")]
    turning = [ln for ln in timeline
               if any(op in ln for op in TURNING_OPS)]
    m = metrics
    goal_txt = goal or ("(see README.md — 'What was built' and 'Why this proof exists')")

    head = [
        f"# {name} — replay",
        "",
        "Automatically derived from `events.log` (via `demo/_replay_facts.md` + "
        "`metrics.json`); every milestone cites `seq` numbers for "
        "cross-checking.",
        "",
        "## Goal",
        "",
        goal_txt,
        "",
        "## Outcome",
        "",
        f"- tasks: **{m.get('tasks', '?')}** · events: **{m.get('events', '?')}** · "
        f"passes: **{m.get('verification_passes', '?')}** · "
        f"failures: **{m.get('verification_failures', '?')}** · "
        f"retries: **{m.get('retries', '?')}**",
        f"- duration: **{m.get('duration_minutes', '?')} min** · "
        f"status: **{m.get('status', '?')}** · "
        f"max_ready_queue: **{m.get('max_ready_queue', '?')}** "
        f"(peaked at seq {m.get('max_ready_queue_at', {}).get('seq', '?')})",
        "- numbers match `metrics.json`, which is derived from `events.log` alone.",
        "",
        "## Timeline",
        "",
        *[f"{ln}" for ln in timeline],
    ]
    if turning:
        head += [
            "",
            "## Turning points",
            "",
            *[f"{ln}" for ln in turning],
        ]
    else:
        head += ["", "## Turning points", "", "None — no failures, retries, or reopens."]
    head += ["", f"*rendered by forge proof replay from {len(timeline)} seq-cited milestones*"]
    return "\n".join(head) + "\n"


def render_dir(proof_dir) -> None:
    """Render replay.md into proof_dir (facts + metrics must exist)."""
    root = Path(proof_dir)
    facts_path = root / "demo" / "_replay_facts.md"
    if not facts_path.exists():
        raise FileNotFoundError(
            f"no derived facts at {facts_path} — run 'forge proof derive {root.name}' first")
    metrics = json.loads((root / "metrics.json").read_text(encoding="utf-8"))
    goal = None
    prop = root / "proposal.json"
    if prop.exists():
        try:
            goal = json.loads(prop.read_text(encoding="utf-8")).get("reason")
        except json.JSONDecodeError:
            goal = None
    md = render_replay(root.name, facts_path.read_text(encoding="utf-8"),
                       metrics, goal)
    (root / "replay.md").write_text(md, encoding="utf-8")
    print(f"wrote {root / 'replay.md'} "
          f"({metrics.get('tasks', '?')} tasks, "
          f"{metrics.get('events', '?')} events)")
    return md