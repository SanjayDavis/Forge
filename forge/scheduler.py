"""Scheduler: derived states and work selection. Deterministic, no AI.

'Blocked' is never stored — it is derived from dependencies. 'Ready' is
derived from effective status + dependencies. Containers (expanded tasks)
are not work items; their children are. Ready order: priority (high first),
then creation order.
"""

from __future__ import annotations

from .model import PRIORITY_WEIGHT, STATUS_DONE, STATUS_NEEDS_REVISION, STATUS_TODO, Graph

STATUS_IN_PROGRESS = "in_progress"


def effective(g: Graph, tid: str) -> str:
    return g.tasks[tid].effective_status(g.tasks)


def is_container(t) -> bool:
    return bool(t.composite and t.depends_on)


def ready_tasks(g: Graph):
    """Tasks that can be worked on now: todo, deps done, not a container."""
    out = [
        t for t in g.tasks.values()
        if not is_container(t)
        and t.effective_status(g.tasks) == STATUS_TODO
        and all(g.tasks[d].effective_status(g.tasks) == STATUS_DONE for d in t.depends_on)
    ]
    out.sort(key=lambda t: (-PRIORITY_WEIGHT.get(t.priority, 1), t.created_seq))
    return out


def next_task(g: Graph):
    ready = ready_tasks(g)
    return ready[0] if ready else None


def blockers(g: Graph, task_id: str, chain: bool = False):
    """Incomplete dependencies of a task. With chain=True, full root-cause
    paths from the task down to each leaf blocker."""
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
    counts = {STATUS_TODO: 0, STATUS_IN_PROGRESS: 0, STATUS_NEEDS_REVISION: 0, STATUS_DONE: 0}
    for t in g.tasks.values():
        counts[t.effective_status(g.tasks)] += 1
    total = len(g.tasks)
    pct = round(100 * counts[STATUS_DONE] / total, 1) if total else 0.0
    return {"total": total, "done": counts[STATUS_DONE],
            "in_progress": counts[STATUS_IN_PROGRESS],
            "needs_revision": counts[STATUS_NEEDS_REVISION],
            "todo": counts[STATUS_TODO], "percent": pct}
