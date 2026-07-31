"""The official Project Kernel API.

This is the ONLY surface through which anything — human CLI, planner agent,
executor, verifier, MCP server — may read or modify a project. Planners do
not write to the graph; they propose events, the kernel validates and
applies them:

    propose -> validate -> append to log -> apply to graph -> done

Every mutation is: build event via Graph builder (validated against the
current graph), persist under the file lock, apply to memory. The event log
remains the single source of truth; the in-memory graph is a projection.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from .context import STATUS_ICON, build_context, to_json, to_markdown
from .model import Graph, GraphError, SCHEMA_VERSION, TaskNode
from .scheduler import blockers, is_container, next_task, progress, ready_tasks
from .store import Store


class Kernel:
    """Official facade over Store + Graph. Thread-safe for writes (the file
    lock serializes appends); in-memory reads reflect the last applied
    event in this process."""

    def __init__(self, directory: str) -> None:
        self.store = Store(directory)
        self.graph = Graph()
        if not self.store.exists():
            self.store.init()
        self.replay()

    # ------------------------------------------------------------------ reads
    def task(self, task_id: str) -> TaskNode:
        t = self.graph.tasks.get(task_id)
        if t is None:
            raise GraphError(f"no such task: {task_id}")
        return t

    def context(self, task_id: str, fmt: str = "markdown") -> str:
        ctx = build_context(self.graph, task_id)
        return to_json(ctx) if fmt == "json" else to_markdown(ctx)

    def ready(self) -> list[str]:
        return [t.id for t in ready_tasks(self.graph)]

    def next(self) -> str | None:
        t = next_task(self.graph)
        return t.id if t else None

    def blockers(self, task_id: str, chain: bool = False):
        return blockers(self.graph, task_id, chain=chain)

    def progress(self) -> dict:
        return progress(self.graph)

    def history(self, task_id: str) -> list[dict[str, Any]]:
        """Every event touching a task, oldest first: created, expanded,
        deps added/removed, started, verification, evidence, notes."""
        self.task(task_id)
        out = []
        for ev in self.store.read_events():
            if ev.get("id") == task_id or ev.get("task") == task_id:
                out.append(ev)
            elif ev.get("depends_on") == task_id:
                out.append(ev)
            elif ev.get("op") == "task_expanded" and any(
                    c["id"] == task_id for c in ev.get("children", [])):
                out.append(ev)
        return out

    def inspect(self, task_id: str) -> dict[str, Any]:
        """Everything about one task, for humans and debugging agents."""
        t = self.task(task_id)
        g = self.graph
        eff = t.effective_status(g.tasks)
        kids = [g.tasks[d] for d in t.depends_on]
        done_kids = sum(1 for k in kids if k.effective_status(g.tasks) == "done")
        completion = (done_kids / len(kids)) if kids else (1.0 if eff == "done" else 0.0)
        # files produced by this task and everything beneath it
        produced: list[str] = []
        seen_ids: set[str] = set()

        def collect(tid: str) -> None:
            if tid in seen_ids:
                return
            seen_ids.add(tid)
            node = g.tasks[tid]
            produced.extend(node.files)
            for d in node.depends_on:
                collect(d)

        collect(task_id)
        produced = sorted(set(produced))
        return {
            "id": t.id, "title": t.title, "description": t.description,
            "status": eff, "priority": t.priority,
            "container": is_container(t),
            "completion": round(completion * 100),
            "completion_text": f"{done_kids}/{len(kids)} children done" if kids
                               else ("done" if eff == "done" else "not started"),
            "children": [{"id": k.id, "title": k.title,
                          "status": k.effective_status(g.tasks),
                          "icon": STATUS_ICON[k.effective_status(g.tasks)]} for k in kids],
            "depends_on": [d for d in t.depends_on],
            "blocks": sorted(x.id for x in g.tasks.values() if task_id in x.depends_on),
            "acceptance": t.acceptance, "files": t.files, "produces": produced,
            "notes": t.notes, "last_failure": t.last_failure,
            "evidence": [{"kind": e.kind, "source": e.source, "detail": e.detail, "ts": e.ts}
                         for e in t.evidence],
            "history": [{"seq": ev["seq"], "op": ev["op"],
                         "ts": ev.get("ts", ""),
                         "summary": _history_summary(ev)} for ev in self.history(task_id)],
            "project": progress(g),
        }

    def query(self, expr: str):
        from .query import run_query
        return run_query(self.graph, expr)

    def export_events(self) -> list[dict[str, Any]]:
        """Canonical, portable snapshot of the project (event log as JSON)."""
        return self.store.read_events()

    # ------------------------------------------------------------------ mutations
    def _commit(self, ev: dict) -> dict:
        stamped = self.store.append([ev])[0]
        self.graph.apply(stamped)
        return stamped

    def create_task(self, title: str, description: str = "", acceptance: Iterable[str] = (),
                    files: Iterable[str] = (), notes: Iterable[str] = (),
                    id: str | None = None, priority: str = "medium") -> dict:
        return self._commit(self.graph.create_task(title, description, acceptance,
                                                   files, notes, id=id, priority=priority))

    def update_task(self, task_id: str, **changes) -> dict:
        return self._commit(self.graph.update_task(task_id, **changes))

    def expand(self, task_id: str, children: Iterable[dict]) -> dict:
        return self._commit(self.graph.expand(task_id, children))

    def add_dependency(self, task_id: str, depends_on: str) -> dict:
        return self._commit(self.graph.add_dependency(task_id, depends_on))

    def remove_dependency(self, task_id: str, depends_on: str) -> dict:
        return self._commit(self.graph.remove_dependency(task_id, depends_on))

    def start(self, task_id: str) -> dict:
        return self._commit(self.graph.start(task_id))

    def verify_fail(self, task_id: str, reason: str) -> dict:
        return self._commit(self.graph.verify_fail(task_id, reason))

    def retry(self, task_id: str) -> dict:
        return self._commit(self.graph.retry(task_id))

    def verify_pass(self, task_id: str, force: bool = False) -> dict:
        return self._commit(self.graph.verify_pass(task_id, force=force))

    def reopen(self, task_id: str) -> dict:
        return self._commit(self.graph.reopen(task_id))

    def add_evidence(self, task_id: str, kind: str, source: str, detail: str = "") -> dict:
        return self._commit(self.graph.add_evidence(task_id, kind, source, detail))

    def add_note(self, task_id: str, text: str) -> dict:
        return self._commit(self.graph.add_note(task_id, text))

    def delete(self, task_id: str) -> dict:
        return self._commit(self.graph.delete(task_id))

    # ------------------------------------------------------------------ log ops
    def undo(self, n: int = 1) -> list[dict[str, Any]]:
        removed = self.store.undo(n)
        self.replay()
        return removed

    def replay(self) -> dict:
        events = self.store.read_events()
        self.graph = Graph.from_events(events)
        p = progress(self.graph)
        return {"events": len(events), "tasks": len(self.graph.tasks), "done": p["done"]}

    def import_events(self, events: list[dict[str, Any]]) -> dict:
        """Merge events from another project export. The incoming log is
        validated by folding it in isolation first; task-id collisions with
        the current project are rejected (resolve and retry), not silently
        overwritten. Sequence numbers are re-stamped locally."""
        if not isinstance(events, list) or not events:
            raise GraphError("nothing to import")
        # validate + fold incoming log in isolation (bad events fail here).
        # Proposals carry no seq (SPEC §9.4): the kernel assigns it, so the
        # isolated fold pre-stamps temporary sequence numbers.
        folded = []
        for i, e in enumerate(events):
            copy = dict(e)
            copy["seq"] = i + 1
            copy.setdefault("ts", "")
            copy.setdefault("v", SCHEMA_VERSION)
            folded.append(copy)
        foreign = Graph.from_events(folded)
        overlap = set(foreign.tasks) & set(self.graph.tasks)
        if overlap:
            raise GraphError(
                f"merge conflict: {len(overlap)} task id(s) already exist "
                f"(first: {', '.join(sorted(overlap)[:5])}) — resolve and retry")
        stamped = self.store.append([dict(e) for e in events])
        self.replay()
        return {"imported": len(stamped), "tasks": len(self.graph.tasks)}

    def to_export_json(self) -> str:
        return json.dumps(self.export_events(), ensure_ascii=False, indent=2)


def _history_summary(ev: dict) -> str:
    op = ev["op"]
    if op == "task_created":
        return f'"{ev["title"]}" (priority {ev.get("priority", "medium")})'
    if op == "task_expanded":
        return f"into {len(ev['children'])} children: {', '.join(c['id'] for c in ev['children'])}"
    if op == "dependency_added":
        return f"{ev['task']} now depends on {ev['depends_on']}"
    if op == "dependency_removed":
        return f"{ev['task']} no longer depends on {ev['depends_on']}"
    if op == "verification_failed":
        return f"reason: {ev.get('reason', '')}"
    if op == "verification_passed":
        return "forced" if ev.get("force") else ""
    if op == "evidence_added":
        return f"[{ev['kind']}] {ev['source']}"
    return ""
