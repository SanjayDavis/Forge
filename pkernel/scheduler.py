"""Scheduler: derived states and work selection. Deterministic, no AI.

'Blocked' is never stored — it is derived from dependencies. 'Ready' is
derived from effective status + dependencies. Containers (composite tasks
with children) are not work items themselves; their children are.
"""

from __future__ import annotations

from .model import Graph, STATUS_DONE, STATUS_IN_PROGRESS, STATUS_NEEDS_REVISION, STATUS_TODO


def is_container(t) -> bool:
    return t.composite and bool(t.depends_on)


def ready_tasks(g: Graph):
    """Tasks that can be worked on now: todo, not a container, all deps done.
    Ordered by creation sequence (stable, deterministic)."""
    out = [
        t for t in g.tasks.values()
        if not is_container(t)
        and t.effective_status(g.tasks) == STATUS_TODO
        and all(g.tasks[d].effective_status(g.tasks) == STATUS_DONE for d in t.depends_on)
    ]
    out.sort(key=lambda t: t.created_seq)
    return out


def next_task(g: Graph):
    """The single next task, or None."""
    ready = ready_tasks(g)
    return ready[0] if ready else None


def blockers(g: Graph, task_id: str, chain: bool = False):
    """Incomplete dependencies of a task. chain=True returns every
    root-cause path from the task to the leaves of the dependency tree."""
    task = g.tasks[task_id]
    if not chain:
        return [d for d in task.depends_on
                if g.tasks[d].effective_status(g.tasks) != STATUS_DONE]

    paths: list[list[str]] = []

    def walk(tid: str, path: list[str]) -> None:
        for d in g.tasks[tid].depends_on:
            if g.tasks[d].effective_status(g.tasks) != STATUS_DONE:
                np = path + [d]
                paths.append(np)
                walk(d, np)

    walk(task_id, [task_id])
    return paths


def progress(g: Graph) -> dict:
    counts = {s: 0 for s in (STATUS_TODO, STATUS_IN_PROGRESS, STATUS_NEEDS_REVISION, STATUS_DONE)}
    for t in g.tasks.values():
        counts[t.effective_status(g.tasks)] += 1
    total = len(g.tasks)
    percent = round(100 * counts[STATUS_DONE] / total, 1) if total else 0.0
    return {"total": total, "done": counts[STATUS_DONE],
            "in_progress": counts[STATUS_IN_PROGRESS],
            "needs_revision": counts[STATUS_NEEDS_REVISION],
            "todo": counts[STATUS_TODO], "percent": percent}
