"""Core domain model for the Project Kernel.

Pure, deterministic, zero dependencies. No I/O, no AI.

The graph is a fold over an event log: every mutation is an event, and the
graph state is derived by applying events in sequence. Replay is exact;
undo is truncation; nothing is ever stored twice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

STATUS_TODO = "todo"
STATUS_IN_PROGRESS = "in_progress"
STATUS_NEEDS_REVISION = "needs_revision"
STATUS_DONE = "done"
VALID_STATUSES = (STATUS_TODO, STATUS_IN_PROGRESS, STATUS_NEEDS_REVISION, STATUS_DONE)

EVIDENCE_HARD = "hard"
EVIDENCE_SOFT = "soft"
VALID_EVIDENCE_KINDS = (EVIDENCE_HARD, EVIDENCE_SOFT)


class GraphError(Exception):
    """Raised for invalid events or illegal transitions. Message is user-facing."""


@dataclass
class Evidence:
    kind: str            # hard (tests/compile/benchmark) or soft (LLM/human review)
    source: str          # e.g. "unittest", "peer review"
    detail: str
    ts: str


@dataclass
class TaskNode:
    id: str
    title: str
    description: str = ""
    status: str = STATUS_TODO
    acceptance: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    composite: bool = False
    last_failure: str | None = None
    created_seq: int = 0

    def effective_status(self, tasks: dict[str, "TaskNode"]) -> str:
        """Composite tasks derive 'done' from their children: a container
        completes when everything it depends on completes."""
        if self.composite and self.depends_on:
            if all(tasks[d].effective_status(tasks) == STATUS_DONE for d in self.depends_on):
                return STATUS_DONE
        return self.status


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "task"


class Graph:
    """Event-sourced task graph. Mutations go through builder methods that
    validate against current state and return an event; the caller persists
    the event (Store.append) and then applies it (Graph.apply)."""

    def __init__(self) -> None:
        self.tasks: dict[str, TaskNode] = {}
        self.seq: int = 0

    # ------------------------------------------------------------------ construction
    @classmethod
    def from_events(cls, events: Iterable[dict[str, Any]]) -> "Graph":
        g = cls()
        for ev in events:
            g.apply(ev)
        return g

    def next_id(self, title: str, reserved: set[str] | None = None) -> str:
        base = slugify(title)
        cand = base
        n = 2
        reserved = reserved or set()
        while cand in self.tasks or cand in reserved:
            cand = f"{base}-{n}"
            n += 1
        return cand

    # ------------------------------------------------------------------ event builders (validate -> return event)
    def create_task(self, title: str, description: str = "", acceptance: Iterable[str] = (),
                    files: Iterable[str] = (), notes: Iterable[str] = (), id: str | None = None) -> dict:
        tid = id or self.next_id(title)
        ev = {"op": "task_created", "id": tid, "title": title, "description": description,
              "acceptance": list(acceptance), "files": list(files), "notes": list(notes)}
        self.validate(ev)
        return ev

    def update_task(self, task_id: str, **changes) -> dict:
        ev = {"op": "task_updated", "id": task_id, **changes}
        self.validate(ev)
        return ev

    def expand(self, task_id: str, children: Iterable[dict]) -> dict:
        """Turn a task into a container: children become its dependencies,
        so it completes when all children complete. Children start ready."""
        ev_children: list[dict] = []
        reserved: set[str] = set()
        for c in children:
            cid = self.next_id(c["title"], reserved)
            reserved.add(cid)
            ev_children.append({"id": cid, "title": c["title"],
                                "description": c.get("description", ""),
                                "acceptance": list(c.get("acceptance", [])),
                                "files": list(c.get("files", []))})
        ev = {"op": "task_expanded", "task": task_id, "children": ev_children}
        self.validate(ev)
        return ev

    def add_dependency(self, task_id: str, depends_on: str) -> dict:
        ev = {"op": "dependency_added", "task": task_id, "depends_on": depends_on}
        self.validate(ev)
        return ev

    def remove_dependency(self, task_id: str, depends_on: str) -> dict:
        ev = {"op": "dependency_removed", "task": task_id, "depends_on": depends_on}
        self.validate(ev)
        return ev

    def start(self, task_id: str) -> dict:
        ev = {"op": "task_started", "id": task_id}
        self.validate(ev)
        return ev

    def verify_fail(self, task_id: str, reason: str) -> dict:
        ev = {"op": "verification_failed", "id": task_id, "reason": reason}
        self.validate(ev)
        return ev

    def retry(self, task_id: str) -> dict:
        ev = {"op": "task_retried", "id": task_id}
        self.validate(ev)
        return ev

    def verify_pass(self, task_id: str, force: bool = False) -> dict:
        ev = {"op": "verification_passed", "id": task_id, "force": bool(force)}
        self.validate(ev)
        return ev

    def reopen(self, task_id: str) -> dict:
        ev = {"op": "task_reopened", "id": task_id}
        self.validate(ev)
        return ev

    def add_evidence(self, task_id: str, kind: str, source: str, detail: str = "") -> dict:
        ev = {"op": "evidence_added", "id": task_id, "kind": kind, "source": source, "detail": detail}
        self.validate(ev)
        return ev

    def add_note(self, task_id: str, text: str) -> dict:
        ev = {"op": "note_added", "id": task_id, "text": text}
        self.validate(ev)
        return ev

    def delete(self, task_id: str) -> dict:
        ev = {"op": "task_deleted", "id": task_id}
        self.validate(ev)
        return ev

    # ------------------------------------------------------------------ validation (no mutation)
    def validate(self, ev: dict) -> None:
        fn = getattr(self, f"_validate_{ev.get('op')}", None)
        if fn is None:
            raise GraphError(f"unknown event op: {ev.get('op')!r}")
        fn(ev)

    def _require(self, task_id: str) -> TaskNode:
        t = self.tasks.get(task_id)
        if t is None:
            raise GraphError(f"no such task: {task_id}")
        return t

    def _would_cycle(self, task_id: str, dep_id: str) -> bool:
        """Adding edge task_id -> dep_id. Cycle iff dep_id transitively depends on task_id."""
        stack, seen = [dep_id], set()
        while stack:
            n = stack.pop()
            if n == task_id:
                return True
            if n in seen:
                continue
            seen.add(n)
            stack.extend(self.tasks[n].depends_on)
        return False

    def _validate_task_created(self, ev):
        tid, title = ev["id"], ev["title"]
        if not isinstance(tid, str) or not tid.strip():
            raise GraphError("task id must be a non-empty string")
        if re.search(r"\s", tid):
            raise GraphError(f"task id must not contain whitespace: {tid!r}")
        if tid in self.tasks:
            raise GraphError(f"task already exists: {tid}")
        if not title or not title.strip():
            raise GraphError("task title must be non-empty")

    def _validate_task_updated(self, ev):
        self._require(ev["id"])
        if not any(k in ev for k in ("title", "description", "acceptance", "files")):
            raise GraphError("task_updated needs at least one field to change")

    def _validate_task_expanded(self, ev):
        t = self._require(ev["task"])
        if t.effective_status(self.tasks) == STATUS_DONE:
            raise GraphError(f"cannot expand a completed task: {ev['task']}")
        kids = ev["children"]
        if not kids:
            raise GraphError("expand needs at least one child")
        ids = [c["id"] for c in kids]
        if len(set(ids)) != len(ids):
            raise GraphError("duplicate child ids in expand")
        for c in kids:
            if c["id"] in self.tasks:
                raise GraphError(f"child id already exists: {c['id']}")
            if not c["title"].strip():
                raise GraphError("child title must be non-empty")

    def _validate_dependency_added(self, ev):
        task_id, dep_id = ev["task"], ev["depends_on"]
        self._require(task_id)
        self._require(dep_id)
        if task_id == dep_id:
            raise GraphError(f"task cannot depend on itself: {task_id}")
        if dep_id in self.tasks[task_id].depends_on:
            raise GraphError(f"dependency already exists: {task_id} -> {dep_id}")
        if self._would_cycle(task_id, dep_id):
            raise GraphError(f"dependency would create a cycle: {task_id} -> {dep_id}")

    def _validate_dependency_removed(self, ev):
        task_id, dep_id = ev["task"], ev["depends_on"]
        t = self._require(task_id)
        self._require(dep_id)
        if dep_id not in t.depends_on:
            raise GraphError(f"no such dependency to remove: {task_id} -> {dep_id}")

    def _validate_task_started(self, ev):
        t = self._require(ev["id"])
        if t.status != STATUS_TODO:
            raise GraphError(f"only 'todo' tasks can be started; {ev['id']} is '{t.status}'")

    def _validate_verification_failed(self, ev):
        t = self._require(ev["id"])
        if t.status not in (STATUS_IN_PROGRESS, STATUS_NEEDS_REVISION):
            raise GraphError(f"only in-progress tasks can fail verification; {ev['id']} is '{t.status}'")
        if not (ev.get("reason") or "").strip():
            raise GraphError("verification_failed needs a reason")

    def _validate_task_retried(self, ev):
        t = self._require(ev["id"])
        if t.status != STATUS_NEEDS_REVISION:
            raise GraphError(f"only 'needs_revision' tasks can be retried; {ev['id']} is '{t.status}'")

    def _validate_verification_passed(self, ev):
        t = self._require(ev["id"])
        if t.status not in (STATUS_IN_PROGRESS, STATUS_NEEDS_REVISION):
            raise GraphError(f"only in-progress tasks can pass verification; {ev['id']} is '{t.status}'")
        if t.composite and t.depends_on:
            raise GraphError(f"{ev['id']} is a container; it completes when all its children complete")
        if not ev.get("force"):
            missing = [d for d in t.depends_on
                       if self.tasks[d].effective_status(self.tasks) != STATUS_DONE]
            if missing:
                raise GraphError(
                    f"dependencies not done: {', '.join(missing)} (use --force to override)")

    def _validate_task_reopened(self, ev):
        t = self._require(ev["id"])
        if t.status != STATUS_DONE:
            raise GraphError(f"only 'done' tasks can be reopened; {ev['id']} is '{t.status}'")

    def _validate_evidence_added(self, ev):
        self._require(ev["id"])
        if ev["kind"] not in VALID_EVIDENCE_KINDS:
            raise GraphError(f"evidence kind must be 'hard' or 'soft', got {ev['kind']!r}")
        if not (ev.get("source") or "").strip():
            raise GraphError("evidence needs a source (e.g. 'unittest', 'peer review')")

    def _validate_note_added(self, ev):
        self._require(ev["id"])
        if not (ev.get("text") or "").strip():
            raise GraphError("note text must be non-empty")

    def _validate_task_deleted(self, ev):
        t = self._require(ev["id"])
        dependents = [x.id for x in self.tasks.values() if ev["id"] in x.depends_on]
        if dependents:
            raise GraphError(f"cannot delete {ev['id']}: depended on by {', '.join(sorted(dependents))}")
        if t.composite and t.depends_on:
            raise GraphError(f"cannot delete {ev['id']}: it has children (delete them first)")

    # ------------------------------------------------------------------ apply (mutates; assumes event already validated)
    def apply(self, ev: dict) -> None:
        fn = getattr(self, f"_apply_{ev['op']}")
        fn(ev)
        self.seq = max(self.seq, int(ev.get("seq", 0)))

    def _apply_task_created(self, ev):
        self.tasks[ev["id"]] = TaskNode(
            id=ev["id"], title=ev["title"], description=ev.get("description", ""),
            acceptance=list(ev.get("acceptance", [])), files=list(ev.get("files", [])),
            notes=list(ev.get("notes", [])), created_seq=ev["seq"])

    def _apply_task_updated(self, ev):
        t = self.tasks[ev["id"]]
        if "title" in ev: t.title = ev["title"]
        if "description" in ev: t.description = ev["description"]
        if "acceptance" in ev: t.acceptance = list(ev["acceptance"])
        if "files" in ev: t.files = list(ev["files"])

    def _apply_task_expanded(self, ev):
        parent = self.tasks[ev["task"]]
        parent.composite = True
        if parent.status == STATUS_TODO:
            parent.status = STATUS_IN_PROGRESS
        for c in ev["children"]:
            self.tasks[c["id"]] = TaskNode(
                id=c["id"], title=c["title"], description=c.get("description", ""),
                acceptance=list(c.get("acceptance", [])), files=list(c.get("files", [])),
                created_seq=ev["seq"])
            parent.depends_on.append(c["id"])

    def _apply_dependency_added(self, ev):
        self.tasks[ev["task"]].depends_on.append(ev["depends_on"])

    def _apply_dependency_removed(self, ev):
        self.tasks[ev["task"]].depends_on.remove(ev["depends_on"])

    def _apply_task_started(self, ev):
        self.tasks[ev["id"]].status = STATUS_IN_PROGRESS

    def _apply_verification_failed(self, ev):
        t = self.tasks[ev["id"]]
        t.status = STATUS_NEEDS_REVISION
        t.last_failure = ev.get("reason", "")

    def _apply_task_retried(self, ev):
        t = self.tasks[ev["id"]]
        t.status = STATUS_IN_PROGRESS
        t.last_failure = None

    def _apply_verification_passed(self, ev):
        t = self.tasks[ev["id"]]
        t.status = STATUS_DONE
        t.last_failure = None

    def _apply_task_reopened(self, ev):
        self.tasks[ev["id"]].status = STATUS_IN_PROGRESS

    def _apply_evidence_added(self, ev):
        self.tasks[ev["id"]].evidence.append(
            Evidence(kind=ev["kind"], source=ev["source"], detail=ev.get("detail", ""), ts=ev["ts"]))

    def _apply_note_added(self, ev):
        self.tasks[ev["id"]].notes.append(ev["text"])

    def _apply_task_deleted(self, ev):
        tid = ev["id"]
        del self.tasks[tid]
        for t in self.tasks.values():
            if tid in t.depends_on:
                t.depends_on.remove(tid)

    # ------------------------------------------------------------------ queries & consistency
    def dependents(self, task_id: str) -> list[TaskNode]:
        return [t for t in self.tasks.values() if task_id in t.depends_on]

    def roots(self) -> list[TaskNode]:
        """Top-level goals: tasks that nothing depends on."""
        depended = {d for t in self.tasks.values() for d in t.depends_on}
        return sorted((t for t in self.tasks.values() if t.id not in depended),
                      key=lambda t: t.created_seq)

    def problems(self) -> list[str]:
        """Full consistency check. Empty list == healthy."""
        out: list[str] = []
        for tid, t in self.tasks.items():
            if t.status not in VALID_STATUSES:
                out.append(f"{tid}: invalid status {t.status!r}")
            if len(set(t.depends_on)) != len(t.depends_on):
                out.append(f"{tid}: duplicate dependencies")
            for d in t.depends_on:
                if d not in self.tasks:
                    out.append(f"{tid}: unknown dependency {d}")
                elif d == tid:
                    out.append(f"{tid}: self-dependency")
        if self._has_cycle():
            out.append("graph contains a cycle")
        return out

    def _has_cycle(self) -> bool:
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {tid: WHITE for tid in self.tasks}

        def dfs(n: str) -> bool:
            color[n] = GRAY
            for d in self.tasks[n].depends_on:
                if d not in self.tasks:
                    continue
                if color[d] == GRAY:
                    return True
                if color[d] == WHITE and dfs(d):
                    return True
            color[n] = BLACK
            return False

        return any(dfs(n) for n in self.tasks if color[n] == WHITE)
