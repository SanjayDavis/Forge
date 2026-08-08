"""Core domain model for the Forge kernel.

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

# --- schema freeze (v1) ---------------------------------------------------
# Event schema is versioned like Git's object model: once frozen, ops and
# field semantics do not change. New fields/ops require a schema version
# bump and a migration, never a silent edit.
SCHEMA_VERSION = 1

PRIORITIES = ("low", "medium", "high")
PRIORITY_WEIGHT = {"low": 0, "medium": 1, "high": 2}

# Required fields + types per op. Enforced on every event, including replay,
# so a corrupt or foreign event fails loudly with its seq number.
# The map covers ALL known fields (required + optional); OP_REQUIRED lists the
# required subset. Unknown fields are rejected (system keys seq/ts/v excepted)
# so foreign events and type-confused optional fields fail loudly instead of
# silently corrupting the graph or crashing later renders.
OP_SHAPES: dict[str, dict[str, type]] = {
    "task_created":        {"id": str, "title": str, "description": str, "acceptance": list,
                            "files": list, "notes": list, "priority": str},
    "task_updated":        {"id": str, "title": str, "description": str, "acceptance": list,
                            "files": list, "priority": str},
    "dependency_added":    {"task": str, "depends_on": str},
    "dependency_removed":  {"task": str, "depends_on": str},
    "task_expanded":       {"task": str, "children": list},
    "task_started":        {"id": str},
    "verification_failed": {"id": str, "reason": str},
    "task_retried":        {"id": str},
    "verification_passed": {"id": str, "force": bool},
    "task_reopened":       {"id": str},
    "evidence_added":      {"id": str, "kind": str, "source": str, "detail": str},
    "note_added":          {"id": str, "text": str},
    "task_deleted":        {"id": str},
    "claims_claimed":      {"id": str, "claims": list, "note": str},
}

OP_REQUIRED: dict[str, tuple[str, ...]] = {
    "task_created":        ("id", "title"),
    "task_updated":        ("id",),
    "dependency_added":    ("task", "depends_on"),
    "dependency_removed":  ("task", "depends_on"),
    "task_expanded":       ("task", "children"),
    "task_started":        ("id",),
    "verification_failed": ("id", "reason"),
    "task_retried":        ("id",),
    "verification_passed": ("id",),
    "task_reopened":       ("id",),
    "evidence_added":      ("id", "kind", "source"),
    "note_added":          ("id", "text"),
    "task_deleted":        ("id",),
    "claims_claimed":      ("claims",),
}

# Keys the store stamps after validation; validate() must tolerate them on
# replay/import because from_events() folds already-stamped events.
_SYSTEM_KEYS = ("seq", "ts", "v")

# Task ids become filesystem path components (artifact filenames) in
# executor/plugin land, so they are restricted to a safe slug-like charset:
# alphanumeric first char, then alnum / dot / underscore / hyphen. This blocks
# path traversal ("../x", "a/b", "..\x"), leading-dot hidden files, and
# Windows-reserved device names (CON, NUL, COM1 ...).
_TASK_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
_WIN_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} \
    | {f"lpt{i}" for i in range(1, 10)}

# Single-line contract fields must not contain line breaks: the Context
# Contract renders them as one line each and parse_context is line-based, so an
# embedded newline would smuggle fake sections into the package an LLM reads.
# Description is the one multi-line field (rendered as a block scalar).
def _reject_ctrl(value: Any, field: str, what: str = "field") -> None:
    if isinstance(value, str) and ("\n" in value or "\r" in value):
        raise GraphError(f"{what} {field!r} must not contain line breaks")


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
    priority: str = "medium"
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
    def from_events(cls, events: Iterable[dict]) -> "Graph":
        g = cls()
        for ev in events:
            g.validate(ev)   # foreign/corrupt input must fail loudly, not KeyError
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
                    files: Iterable[str] = (), notes: Iterable[str] = (), id: str | None = None,
                    priority: str = "medium") -> dict:
        tid = id or self.next_id(title)
        ev = {"op": "task_created", "id": tid, "title": title, "description": description,
              "acceptance": list(acceptance), "files": list(files), "notes": list(notes),
              "priority": priority}
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
                                "files": list(c.get("files", [])),
                                "priority": c.get("priority", "medium")})
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
        op = ev.get("op")
        shape = OP_SHAPES.get(op)
        if shape is None:
            raise GraphError(f"unknown event op: {op!r}")
        for key in OP_REQUIRED[op]:
            if key not in ev:
                raise GraphError(f"event {op!r} is missing required field {key!r}")
        # every present field must be a known field of the right type —
        # including optional fields, so type confusion can never be persisted
        # (a bad optional field used to be accepted and then crash later
        # renders; now it fails loudly at the event boundary)
        for key, val in ev.items():
            if key in _SYSTEM_KEYS or key == "op":
                continue
            if key not in shape:
                raise GraphError(f"event {op!r} has unknown field {key!r}")
            if not isinstance(val, shape[key]):
                raise GraphError(f"event {op!r}: field {key!r} must be {shape[key].__name__}, got {type(val).__name__}")
        fn = getattr(self, f"_validate_{op}")
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
        if not _TASK_ID_RE.fullmatch(tid) or tid.lower() in _WIN_RESERVED:
            raise GraphError(
                f"task id must be a safe slug ([a-zA-Z0-9][a-zA-Z0-9._-]*), got {tid!r}")
        if tid in self.tasks:
            raise GraphError(f"task already exists: {tid}")
        if not title or not title.strip():
            raise GraphError("task title must be non-empty")
        _reject_ctrl(title, "title")
        if ev.get("priority", "medium") not in PRIORITIES:
            raise GraphError(f"priority must be one of {', '.join(PRIORITIES)}, got {ev.get('priority')!r}")
        for lst, what in (("acceptance", "acceptance item"), ("files", "file"),
                          ("notes", "note")):
            for item in ev.get(lst, []):
                if not isinstance(item, str):
                    raise GraphError(f"{what} must be a string, got {type(item).__name__}")
                _reject_ctrl(item, lst, what)

    def _validate_task_updated(self, ev):
        self._require(ev["id"])
        if not any(k in ev for k in ("title", "description", "acceptance", "files", "priority")):
            raise GraphError("task_updated needs at least one field to change")
        if "priority" in ev and ev["priority"] not in PRIORITIES:
            raise GraphError(f"priority must be one of {', '.join(PRIORITIES)}, got {ev['priority']!r}")
        if "title" in ev:
            if not ev["title"].strip():
                raise GraphError("task title must be non-empty")
            _reject_ctrl(ev["title"], "title")
        for lst, what in (("acceptance", "acceptance item"), ("files", "file")):
            for item in ev.get(lst, []):
                if not isinstance(item, str):
                    raise GraphError(f"{what} must be a string, got {type(item).__name__}")
                _reject_ctrl(item, lst, what)

    def _validate_task_expanded(self, ev):
        t = self._require(ev["task"])
        if t.effective_status(self.tasks) == STATUS_DONE:
            raise GraphError(f"cannot expand a completed task: {ev['task']}")
        kids = ev["children"]
        if not kids:
            raise GraphError("expand needs at least one child")
        ids = []
        for c in kids:
            if not isinstance(c, dict):
                raise GraphError(f"child must be an object with id/title, got {type(c).__name__}")
            if "id" not in c or not isinstance(c["id"], str) or not c["id"].strip():
                raise GraphError("child id must be a non-empty string")
            if not _TASK_ID_RE.fullmatch(c["id"]) or c["id"].lower() in _WIN_RESERVED:
                raise GraphError(
                    f"child id must be a safe slug ([a-zA-Z0-9][a-zA-Z0-9._-]*), got {c['id']!r}")
            if "title" not in c or not isinstance(c["title"], str) or not c["title"].strip():
                raise GraphError("child title must be a non-empty string")
            _reject_ctrl(c["title"], "title", "child")
            ids.append(c["id"])
        if len(set(ids)) != len(ids):
            raise GraphError("duplicate child ids in expand")
        for c in kids:
            if c["id"] in self.tasks:
                raise GraphError(f"child id already exists: {c['id']}")
            if c.get("priority", "medium") not in PRIORITIES:
                raise GraphError(f"child priority must be one of {', '.join(PRIORITIES)}, "
                                 f"got {c.get('priority')!r}")

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
        _reject_ctrl(ev.get("reason", ""), "reason")

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
        _reject_ctrl(ev.get("source", ""), "source", "evidence")
        _reject_ctrl(ev.get("detail", ""), "detail", "evidence")

    def _validate_note_added(self, ev):
        self._require(ev["id"])
        if not (ev.get("text") or "").strip():
            raise GraphError("note text must be non-empty")
        _reject_ctrl(ev.get("text", ""), "text", "note")

    def _validate_task_deleted(self, ev):
        t = self._require(ev["id"])
        dependents = [x.id for x in self.tasks.values() if ev["id"] in x.depends_on]
        if dependents:
            raise GraphError(f"cannot delete {ev['id']}: depended on by {', '.join(sorted(dependents))}")
        if t.composite and t.depends_on:
            raise GraphError(f"cannot delete {ev['id']}: it has children (delete them first)")

    def _validate_claims_claimed(self, ev):
        """Project-level claim record (Proof Standard). No task state is
        touched: the event asserts this project has been demonstrated against
        Claim IDs from proofs/PROOF_SPEC.md §2. `claims` must be a non-empty
        list of non-empty Claim IDs."""
        claims = ev.get("claims")
        if not claims or not all(isinstance(c, str) and c.strip() for c in claims):
            raise GraphError("claims_claimed requires a non-empty list of claim IDs")
        for c in claims:
            if not re.fullmatch(r"C\d+", c):
                raise GraphError(f"claim id {c!r} must look like a Claim ID (C1..C7)")

    def _apply_claims_claimed(self, ev):
        """No-op: the event records project-level claim assertions and never
        mutates task state (the graph stays a pure function of workflow)."""

    # ------------------------------------------------------------------ apply (mutates; assumes event already validated)
    def apply(self, ev: dict) -> None:
        fn = getattr(self, f"_apply_{ev['op']}")
        fn(ev)
        self.seq = max(self.seq, int(ev.get("seq", 0)))

    def _apply_task_created(self, ev):
        self.tasks[ev["id"]] = TaskNode(
            id=ev["id"], title=ev["title"], description=ev.get("description", ""),
            acceptance=list(ev.get("acceptance", [])), files=list(ev.get("files", [])),
            notes=list(ev.get("notes", [])), priority=ev.get("priority", "medium"),
            created_seq=ev["seq"])

    def _apply_task_updated(self, ev):
        t = self.tasks[ev["id"]]
        if "title" in ev: t.title = ev["title"]
        if "description" in ev: t.description = ev["description"]
        if "acceptance" in ev: t.acceptance = list(ev["acceptance"])
        if "files" in ev: t.files = list(ev["files"])
        if "priority" in ev: t.priority = ev["priority"]

    def _apply_task_expanded(self, ev):
        parent = self.tasks[ev["task"]]
        parent.composite = True
        if parent.status == STATUS_TODO:
            parent.status = STATUS_IN_PROGRESS
        for c in ev["children"]:
            self.tasks[c["id"]] = TaskNode(
                id=c["id"], title=c["title"], description=c.get("description", ""),
                acceptance=list(c.get("acceptance", [])), files=list(c.get("files", [])),
                priority=c.get("priority", "medium"),
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
