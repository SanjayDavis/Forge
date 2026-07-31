"""ReferencePlanner — M2B, the first untrusted client of Forge.

Implements the Planner Protocol (SPEC §9): goal in, proposal out.
The planner never owns the graph. It has no handle to the kernel, the
log, or any live state — it receives an immutable snapshot and returns
one structured object:

    {
      "proposal_id": "prop_...",
      "reason": "...",
      "confidence": 0.9,
      "events": [ ... ]          # no seq — the kernel stamps it (§9.4)
    }

This is a REFERENCE planner: deterministic, stdlib-only, no AI. It
exists to prove the boundary and exercise the commit path. Any LLM
planner is a drop-in replacement behind the same protocol — same
shape, same commit path, same rules.

Planner constraints enforced here (§9.6):
  - only task_created / task_expanded / task_updated / dependency_added
  - no event carries a seq (the kernel assigns sequence numbers)
  - every referenced task id is created by this proposal (predicted
    with the kernel's own slugify/next_id derivation, so dependency
    events land on the ids the kernel will actually generate)
"""
from __future__ import annotations

import uuid

from forge.model import slugify

# SPEC §9.6: the ops a planner may propose. Verification and execution
# events are the executor's domain (§10) and are rejected here.
ALLOWED_OPS = ("task_created", "task_expanded", "task_updated", "dependency_added")

# Required fields per op (mirrors OP_SHAPES for the planner's subset).
_ENVELOPE_REQ = ("proposal_id", "reason", "confidence", "events")
_OP_REQ = {
    "task_created": ("id", "title"),
    "task_updated": ("id",),
    "task_expanded": ("task", "children"),
    "dependency_added": ("task", "depends_on"),
}

_DEFAULT_MILESTONES = ("Foundation", "Core", "Acceptance")


class ProposalError(Exception):
    """A proposal violates the Planner Protocol (SPEC §9)."""


def validate_proposal(proposal) -> None:
    """Protocol-level validation of the proposal envelope and events.

    The kernel remains the authority: this checks the *envelope* and
    the planner's allowed surface (§9.3, §9.6). Event-level semantics
    (cycles, unknown tasks, transitions) are enforced by the kernel on
    commit. Raises ProposalError with a structured reason.
    """
    if not isinstance(proposal, dict):
        raise ProposalError("proposal must be an object")
    for field in _ENVELOPE_REQ:
        if field not in proposal:
            raise ProposalError(f"missing envelope field: {field}")
    if not isinstance(proposal["proposal_id"], str) or not proposal["proposal_id"]:
        raise ProposalError("proposal_id must be a non-empty string")
    if not isinstance(proposal["reason"], str) or not proposal["reason"].strip():
        raise ProposalError("reason must be a non-empty string")
    conf = proposal["confidence"]
    if isinstance(conf, bool) or not isinstance(conf, (int, float)):
        raise ProposalError("confidence must be a number")
    if not 0.0 <= conf <= 1.0:
        raise ProposalError("confidence must be in [0, 1]")

    events = proposal["events"]
    if not isinstance(events, list) or not events:
        raise ProposalError("events must be a non-empty list")
    for i, ev in enumerate(events):
        if not isinstance(ev, dict):
            raise ProposalError(f"event {i}: must be an object")
        if "seq" in ev:
            raise ProposalError(
                f"event {i}: proposal events carry no seq — the kernel stamps it (§9.4)")
        op = ev.get("op")
        if op not in ALLOWED_OPS:
            raise ProposalError(
                f"event {i}: op '{op}' not allowed for a planner (§9.6)")
        for field in _OP_REQ[op]:
            if field not in ev:
                raise ProposalError(f"event {i}: missing '{field}' for {op}")
        if op == "task_expanded":
            for c in ev["children"]:
                if not isinstance(c, dict):
                    raise ProposalError(f"event {i}: children must be objects")
                if not (isinstance(c.get("title"), str) and c["title"]):
                    raise ProposalError(f"event {i}: child needs a non-empty title")
                if not (isinstance(c.get("id"), str) and c["id"]):
                    raise ProposalError(f"event {i}: child needs a non-empty id")


class ReferencePlanner:
    """Deterministic, stdlib-only planner. Goal in, proposal out.

    Decomposes a goal into a root task with three milestone children
    (Foundation -> Core -> Acceptance) joined by a dependency chain.
    The decomposition is a skeleton: it is structurally correct by
    construction, and domain intelligence belongs to a smarter planner
    behind the same protocol.
    """

    def plan(self, goal: str, children=None, priority: str = "medium",
             confidence: float = 0.9, reason: str | None = None) -> dict:
        goal = (goal or "").strip()
        if not goal:
            raise ProposalError("goal must be a non-empty string")
        if priority not in ("low", "medium", "high"):
            raise ProposalError(f"priority must be low/medium/high, got {priority!r}")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) \
                or not 0.0 <= confidence <= 1.0:
            raise ProposalError("confidence must be a number in [0, 1]")

        root_id = slugify(goal)
        if children is None:
            children = [
                {"title": f"{goal} — {m}", "priority": priority}
                for m in _DEFAULT_MILESTONES
            ]

        # Predict the ids the kernel will derive (model.py expand:
        # next_id over existing tasks + reserved, in order).
        existing = {root_id}
        child_ids: list[str] = []
        for c in children:
            base = slugify(c["title"])
            cand, n = base, 2
            while cand in existing:
                cand = f"{base}-{n}"
                n += 1
            existing.add(cand)
            child_ids.append(cand)

        events = [{
            "op": "task_created", "id": root_id, "title": goal,
            "description": "", "acceptance": [], "files": [], "notes": [],
            "priority": priority,
        }]
        events.append({
            "op": "task_expanded", "task": root_id,
            "children": [
                {
                    "id": cid,
                    "title": c["title"],
                    "description": c.get("description", ""),
                    "acceptance": list(c.get("acceptance", [])),
                    "files": list(c.get("files", [])),
                    "priority": c.get("priority", priority),
                }
                for cid, c in zip(child_ids, children)
            ],
        })
        for i in range(1, len(child_ids)):
            events.append({
                "op": "dependency_added",
                "task": child_ids[i],
                "depends_on": child_ids[i - 1],
            })

        proposal = {
            "proposal_id": f"prop_{root_id[:20]}_{uuid.uuid4().hex[:8]}",
            "reason": reason or (
                f"Decompose '{goal}' into {', '.join(_DEFAULT_MILESTONES).lower()} "
                f"milestones with a dependency chain"),
            "confidence": confidence,
            "events": events,
        }
        validate_proposal(proposal)  # self-check before returning
        return proposal
