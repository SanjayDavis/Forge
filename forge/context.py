"""Context Builder: assembles a focused, deterministic context package for a
task. This is the ONLY thing an LLM client needs to see to work on a task —
it solves the "LLM wastes context reconstructing project state" problem by
making the kernel do the reconstruction, once, cheaply, in code.

Pure function of graph state; renders to JSON (canonical) or markdown
(human/LLM friendly).
"""

from __future__ import annotations

import json

from .model import Graph, STATUS_DONE
from .scheduler import blockers, is_container, progress

STATUS_ICON = {"todo": "\u26aa", "in_progress": "\U0001f535",
               "needs_revision": "\U0001f534", "done": "\u2705"}


def build_context(g: Graph, task_id: str) -> dict:
    t = g.tasks[task_id]
    deps = []
    for d in t.depends_on:
        dt = g.tasks[d]
        deps.append({"id": d, "title": dt.title,
                     "status": dt.effective_status(g.tasks),
                     "done": dt.effective_status(g.tasks) == STATUS_DONE,
                     "evidence": len(dt.evidence)})
    blocked_by = blockers(g, task_id)
    dependents = [{"id": x.id, "title": x.title,
                   "status": x.effective_status(g.tasks)}
                  for x in g.tasks.values() if task_id in x.depends_on]
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "effective_status": t.effective_status(g.tasks),
        "container": is_container(t),
        "acceptance": list(t.acceptance),
        "files": list(t.files),
        "notes": list(t.notes),
        "last_failure": t.last_failure,
        "dependencies": deps,
        "blockers": blocked_by,
        "blocks": dependents,
        "evidence": [{"kind": e.kind, "source": e.source, "detail": e.detail, "ts": e.ts}
                     for e in t.evidence],
        "project": progress(g),
    }


def _icon(status: str) -> str:
    return STATUS_ICON.get(status, "\u2753")


def to_markdown(ctx: dict) -> str:
    lines: list[str] = []
    lines.append(f"# {ctx['id']} — {ctx['title']}")
    lines.append("")
    eff = ctx["effective_status"]
    if ctx["container"]:
        lines.append(f"**Status:** {_icon(eff)} {eff} (container: completes when children complete)")
    else:
        lines.append(f"**Status:** {_icon(eff)} {eff}")
    if ctx["description"]:
        lines.append("")
        lines.append(ctx["description"])
    lines.append("")
    lines.append("## Acceptance criteria")
    if ctx["acceptance"]:
        lines.extend(f"- {a}" for a in ctx["acceptance"])
    else:
        lines.append("_(none)_")
    lines.append("")
    lines.append("## Files")
    if ctx["files"]:
        lines.extend(f"- `{f}`" for f in ctx["files"])
    else:
        lines.append("_(none)_")
    lines.append("")
    lines.append("## Dependencies (must be done first)")
    if ctx["dependencies"]:
        for d in ctx["dependencies"]:
            lines.append(f"- {d['id']} {_icon(d['status'])} ({d['status']})")
    else:
        lines.append("_(none — ready to start)_")
    lines.append("")
    lines.append("## Blockers")
    if ctx["blockers"]:
        lines.extend(f"- {b}" for b in ctx["blockers"])
    else:
        lines.append("_(none)_")
    lines.append("")
    lines.append("## Blocks (tasks waiting on this)")
    if ctx["blocks"]:
        lines.extend(f"- {b['id']} {_icon(b['status'])}" for b in ctx["blocks"])
    else:
        lines.append("_(nothing)_")
    lines.append("")
    lines.append("## Evidence")
    if ctx["evidence"]:
        for e in ctx["evidence"]:
            tag = "HARD" if e["kind"] == "hard" else "soft"
            detail = f" — {e['detail']}" if e["detail"] else ""
            lines.append(f"- [{tag}] {e['source']}{detail} ({e['ts']})")
    else:
        lines.append("_(none)_")
    if ctx["last_failure"]:
        lines.append("")
        lines.append(f"## Last verification failure\n{ctx['last_failure']}")
    if ctx["notes"]:
        lines.append("")
        lines.append("## Notes")
        lines.extend(f"- {n}" for n in ctx["notes"])
    lines.append("")
    lines.append("## Project")
    p = ctx["project"]
    lines.append(f"- progress: {p['done']}/{p['total']} done ({p['percent']}%)")
    lines.append(f"- todo {p['todo']} | in progress {p['in_progress']} | "
                 f"needs revision {p['needs_revision']} | done {p['done']}")
    return "\n".join(lines)


def to_json(ctx: dict) -> str:
    return json.dumps(ctx, indent=2, ensure_ascii=False)


def status_icon(status: str) -> str:
    return _icon(status)
