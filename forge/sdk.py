"""Forge SDK — the public interface every client is allowed to touch.

This is the boundary. Humans, planner agents, executors, reviewers, and
MCP servers talk to Forge ONLY through this module (or the CLI, which
speaks it too). Nothing here contains graph logic, replay logic, or
scheduling logic — those stay in the kernel. The SDK is a thin facade
over the official Kernel API plus the two client-facing contracts:

  * the Proposal Protocol (SPEC §9): an envelope the kernel either
    commits atomically or rejects whole;
  * the Context Contract: the standard ~500-token package a coding
    agent receives instead of the whole repository.

If a client needs a private shortcut into forge.* internals, that is a
bug in this module — the kernel API is missing something.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from .kernel import Kernel
from .model import Graph, slugify  # noqa: F401  (slugify: public id rule)
from .scheduler import next_task


# --------------------------------------------------------------------------- proposal protocol (SPEC §9)
class ProposalError(ValueError):
    """A proposal violates the protocol (SPEC §9): wrong envelope shape,
    op outside the client's allowlist, or a pre-stamped seq. The kernel
    never sees it."""


# ops a planner proposal may carry (SPEC §9.6). Executors/reviewers have
# their own allowlists in their own milestones; the kernel remains the
# authority on op shapes.
PLANNER_OPS = ("task_created", "task_expanded", "task_updated",
               "dependency_added")

# F3: a rejection an agent cannot act on is a stalled agent. Every
# rejection therefore carries the expected shape, not just the rule that
# was broken — "missing 'title' for task_created (expected: id, title)"
# tells a planner what to emit; "missing field" alone does not, and the
# observed failure mode was N identical rejections with zero progress.
_OP_SHAPE_HELP: dict[str, str] = {
    "task_created":     "expected: id (str, kebab-case), title (str), "
                       "description (str), acceptance (list of str), "
                       "files (list of str), priority (low|medium|high), "
                       "notes (list of str)",
    "task_updated":     "expected: id (str), plus any of title, description, "
                       "acceptance (list), files (list), priority",
    "task_expanded":    "expected: task (str, existing id), children (list of "
                       "{id, title, ...}) — the kernel derives child ids and "
                       "turns the parent into a container",
    "dependency_added": "expected: task (str), depends_on (str) — both must "
                       "already exist in the graph",
}

# fields that must be present on a proposal (SPEC §9.1-§9.3)
_REQUIRED_FIELDS = ("proposal_id", "reason", "confidence", "events")

# required fields per op — the protocol's presence check, mirroring the
# kernel's OP_SHAPES for the planner's subset. Type/state authority stays
# in the kernel; this gives clients structured, early feedback.
_OP_REQ = {
    "task_created": ("id", "title"),
    "task_updated": ("id",),
    "task_expanded": ("task", "children"),
    "dependency_added": ("task", "depends_on"),
}


def validate_proposal(proposal: Any) -> None:
    """Envelope checks only. Type and state validation is the kernel's
    job (import_events); this just proves the client read the protocol.

    Every rejection names the expected shape (F2/F3). A client that
    cannot act on a rejection retries it verbatim and never converges,
    so the message is part of the contract, not decoration."""
    # The §9.1 envelope, quoted once so every envelope rejection can
    # answer "what should it have looked like?" without a doc lookup.
    envelope = ("expected envelope: {proposal_id: str, reason: str, "
                "confidence: number 0.0-1.0, events: [event, ...]} "
                "(SPEC §9.1-§9.3)")
    if not isinstance(proposal, dict):
        raise ProposalError(f"proposal must be a JSON object — {envelope}")
    for field in _REQUIRED_FIELDS:
        if field not in proposal:
            raise ProposalError(f"missing field '{field}' (SPEC §9.1) — {envelope}")
    if not isinstance(proposal["proposal_id"], str) or not proposal["proposal_id"]:
        raise ProposalError(
            f"proposal_id must be a non-empty string — {envelope}")
    if not isinstance(proposal["reason"], str) or not proposal["reason"]:
        raise ProposalError(f"reason must be a non-empty string — {envelope}")
    conf = proposal["confidence"]
    if isinstance(conf, bool) or not isinstance(conf, (int, float)):
        raise ProposalError(f"confidence must be a number — {envelope}")
    if not 0.0 <= conf <= 1.0:
        raise ProposalError(f"confidence must be in [0, 1], got {conf} — {envelope}")
    events = proposal["events"]
    if not isinstance(events, list) or not events:
        raise ProposalError(
            f"events must be a non-empty list (SPEC §9.3) — {envelope}")
    for i, ev in enumerate(events):
        if not isinstance(ev, dict) or "op" not in ev:
            raise ProposalError(
                f"event {i}: must be an object with an 'op' — {_OP_SHAPE_HELP['task_created']}")
        if ev["op"] not in PLANNER_OPS:
            raise ProposalError(
                f"op '{ev['op']}' not allowed for a planner (§9.6) — "
                f"allowed ops: {', '.join(PLANNER_OPS)}; "
                f"{_OP_SHAPE_HELP['task_created']}")
        shape = _OP_SHAPE_HELP[ev["op"]]
        if "seq" in ev:
            raise ProposalError(
                "proposal events must not carry 'seq' — the kernel "
                f"stamps sequence numbers on commit (§9.4). {shape}")
        for field in _OP_REQ[ev["op"]]:
            if field not in ev:
                raise ProposalError(
                    f"event {i}: missing '{field}' for {ev['op']} (§9.3) — {shape}")
        if ev["op"] == "task_expanded":
            for j, c in enumerate(ev["children"]):
                if not isinstance(c, dict):
                    raise ProposalError(
                        f"event {i}: child {j} must be an object with 'id' and "
                        f"'title', got {type(c).__name__} — {shape}")
                if not (isinstance(c.get("title"), str) and c["title"]):
                    raise ProposalError(
                        f"event {i}: child {j} needs a non-empty title "
                        f"(got {c.get('title')!r}) — {shape}")
                if not (isinstance(c.get("id"), str) and c["id"]):
                    raise ProposalError(
                        f"event {i}: child {j} needs a non-empty id "
                        f"(got {c.get('id')!r}) — {shape}")


# --------------------------------------------------------------------------- context contract
def context_package(g: Graph, task_id: str) -> dict:
    """The standard context package for one task — the CONTRACT between
    Forge and every coding agent (SPEC Appendix C: Context Contract).

    Knowledge = task notes; Constraints = notes prefixed 'constraint:'.
    Both ride the frozen event schema; the convention lives here.
    """
    t = g.tasks[task_id]
    notes = list(t.notes)
    constraints = [n[len("constraint:"):].strip()
                   for n in notes if n.lower().startswith("constraint:")]
    knowledge = [n for n in notes if not n.lower().startswith("constraint:")]
    deps = []
    for d in t.depends_on:
        dt = g.tasks[d]
        deps.append({"id": d, "title": dt.title,
                     "status": dt.effective_status(g.tasks),
                     "done": dt.effective_status(g.tasks) == "done"})
    produced: set[str] = set()

    def collect(tid: str, seen: set[str]) -> None:
        if tid in seen:
            return
        seen.add(tid)
        node = g.tasks[tid]
        produced.update(node.files)
        for d in node.depends_on:
            collect(d, seen)

    collect(task_id, set())
    return {
        "task": t.id,
        "title": t.title,
        "description": t.description,
        "acceptance": list(t.acceptance),
        "dependencies": deps,
        "knowledge": knowledge,
        "relevant_files": sorted(set(t.files) | produced),
        "evidence": [{"kind": e.kind, "source": e.source, "detail": e.detail}
                     for e in t.evidence],
        "constraints": constraints,
    }


def _yaml_scalar(v: str) -> str:
    # Line-based contract: an embedded newline would split the value across
    # lines and let it be misread as a section header / extra items (context
    # injection). Escape line breaks so the value always renders as one line.
    if "\n" in v or "\r" in v:
        v = v.replace("\r", "\\r").replace("\n", "\\n")
    if (v == "" or v != v.strip()
            or any(ch in v for ch in ":#{}[],&*!|>'\"%@`")
            or v[0] in "-? "):
        return "'" + v.replace("'", "''") + "'"
    return v


def _yaml_items(entries: Iterable[tuple[str, str]]) -> list[str]:
    return [f"  - {_yaml_scalar(v)}" for _, v in entries]


def to_yaml(pkg: dict) -> str:
    """Render the contract package as YAML — the ~500-token shape a
    coding agent consumes. Section order is fixed; every section is
    present so clients can rely on the shape."""
    out: list[str] = []
    title = pkg["title"] if pkg["title"] else pkg["task"]
    out.append(f"Task: {_yaml_scalar(pkg['task'])} — {_yaml_scalar(title)}")
    desc = pkg["description"].strip()
    if desc:
        out.append("Description: |")
        out.extend(f"  {ln}" for ln in desc.splitlines() if ln.strip())
    else:
        out.append("Description: (none)")
    out.append("Acceptance:")
    out.extend(_yaml_items(("", a) for a in pkg["acceptance"]) or ["  (none)"])
    if pkg["dependencies"]:
        out.append("Dependencies:")
        for d in pkg["dependencies"]:
            mark = "\u2713" if d["done"] else "\u25cb"
            out.append(f"  - {_yaml_scalar(d['id'])} {mark} ({d['status']})")
    else:
        out.append("Dependencies: (none \u2014 ready to start)")
    out.append("Knowledge:")
    out.extend(_yaml_items(("", k) for k in pkg["knowledge"]) or ["  (none)"])
    out.append("Relevant Files:")
    out.extend(_yaml_items(("", f) for f in pkg["relevant_files"]) or ["  (none)"])
    if pkg["evidence"]:
        out.append("Evidence:")
        for e in pkg["evidence"]:
            tag = "hard" if e["kind"] == "hard" else "soft"
            detail = f" — {_yaml_scalar(e['detail'])}" if e["detail"] else ""
            out.append(f"  - [{tag}] {_yaml_scalar(e['source'])}{detail}")
    else:
        out.append("Evidence: (none)")
    out.append("Constraints:")
    out.extend(_yaml_items(("", c) for c in pkg["constraints"]) or ["  (none)"])
    return "\n".join(out)


def to_json(pkg: dict) -> str:
    return json.dumps(pkg, indent=2, ensure_ascii=False)


class ContextError(ValueError):
    """The Context Contract package is malformed (SPEC Appendix C). The
    kernel never sees it; this is client-side tooling."""


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s.startswith("'") and s.endswith("'"):
        return s[1:-1].replace("''", "'")
    return s


def parse_context(text: str) -> dict:
    """Parse the frozen Context Contract YAML subset emitted by
    `to_yaml` / `ForgeClient.context()`. Strictly bound to the
    contract's fixed shape (section order, indented items, single-quoted
    scalars) — not a general YAML parser. This is the canonical reader
    for the Context Contract; every client (executor, reviewer, MCP
    server) consumes the same package natively."""
    lines = text.splitlines()
    if not lines or not lines[0].startswith("Task: "):
        raise ContextError(
            "context package must open with 'Task: <id> — <title>'")
    rest = lines[0][len("Task: "):]
    if " — " not in rest:
        raise ContextError("context header must be 'Task: <id> — <title>'")
    task_id, title = rest.split(" — ", 1)  # id is first; title may contain ' — ' itself
    pkg: dict = {
        "task": _unquote(task_id),
        "title": _unquote(title),
        "description": "",
        "acceptance": [],
        "dependencies": [],
        "knowledge": [],
        "relevant_files": [],
        "evidence": [],
        "constraints": [],
    }
    section: str | None = None
    for line in lines[1:]:
        if line and not line.startswith(" "):
            head = line.rstrip()
            if "(" in head:
                section = None            # "(none)" placeholders
            elif head.startswith("Description"):
                section = "description"
            else:
                key = head.rstrip(":").strip().lower().replace(" ", "_")
                section = key if key in pkg else None
            continue
        if section is None:
            continue
        item = line.strip()
        if not item:
            continue
        if section == "description":
            pkg["description"] += ("\n" + item) if pkg["description"] else item
            continue
        if item.startswith("(none"):
            continue
        if item.startswith("- "):
            pkg[section].append(_unquote(item[2:].strip()))
    return pkg


# --------------------------------------------------------------------------- the client
class ForgeClient:
    """The public SDK. One implementation; every client — Hermes, Claude
    Code, Codex, a human with a terminal, an MCP server — uses this and
    nothing else. No graph logic, no replay, no scheduler: all of that
    is the kernel's. If you find yourself reaching past this class,
    the SDK is missing a method (add it here, not in your client)."""

    def __init__(self, directory: str = ".") -> None:
        self.kernel = Kernel(directory)

    # ---- planner / human flow
    def next(self) -> dict | None:
        """The single next work item, as a plain snapshot: highest
        priority, then creation order. None when nothing is ready."""
        t = next_task(self.kernel.graph)
        if t is None:
            return None
        return {"id": t.id, "title": t.title,
                "description": t.description,
                "status": t.effective_status(self.kernel.graph.tasks),
                "priority": t.priority}

    def context(self, task_id: str) -> str:
        """The Context Contract package for TASK, as YAML (Appendix C)."""
        return to_yaml(context_package(self.kernel.graph, task_id))

    def propose(self, proposal: dict) -> dict:
        """Commit a proposal atomically (SPEC §9): envelope validated
        here, then the kernel validates and applies — whole or nothing.
        Raises ProposalError (protocol) or GraphError (kernel)."""
        validate_proposal(proposal)
        result = self.kernel.import_events(proposal["events"])
        return {"proposal_id": proposal["proposal_id"],
                "confidence": proposal["confidence"],
                "committed": result["imported"],
                "tasks": result["tasks"]}

    # ---- executor / reviewer flow
    def start(self, task_id: str) -> dict:
        """Claim TASK: todo -> in_progress."""
        return self.kernel.start(task_id)

    def expand(self, task_id: str, children: Iterable[dict]) -> dict:
        """Re-split TASK into children (SPEC §10.3): the kernel derives
        the child ids, turns TASK into a container, and commits
        atomically — validated like every other kernel event, rejected
        whole on any violation. The container then completes when its
        children do."""
        return self.kernel.expand(task_id, children)

    def attach_evidence(self, task_id: str, kind: str, source: str,
                        detail: str = "") -> dict:
        """Hard evidence = tests/compile/benchmark; soft = review."""
        return self.kernel.add_evidence(task_id, kind, source, detail)

    def verify(self, task_id: str) -> dict:
        """Run the verifier gate (I6): only started tasks with all
        dependencies done can pass; force never bypasses the status
        gate. On pass the task is done — the executor never decides
        this itself."""
        return self.kernel.verify_pass(task_id)

    def verify_fail(self, task_id: str, reason: str) -> dict:
        """Reject: in_progress -> needs_revision (reviewer flow)."""
        return self.kernel.verify_fail(task_id, reason)

    def retry(self, task_id: str) -> dict:
        """needs_revision -> in_progress (SPEC §10.2: after a failed
        pass, an executor may retry to continue)."""
        return self.kernel.retry(task_id)

    # ---- inspection
    def query(self, expr: str) -> list[Any]:
        return self.kernel.query(expr)

    def progress(self) -> dict:
        return self.kernel.progress()

    def replay(self) -> dict:
        return self.kernel.replay()
