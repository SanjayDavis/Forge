"""ReferencePlanner — M2B, the first untrusted client of Forge.

Implements the Planner Protocol (SPEC §9): goal in, proposal out.
The planner never owns the graph. It consumes ONLY the public SDK
(`forge.ForgeClient`, `forge.validate_proposal`, `forge.slugify`) —
no kernel internals. That is the architectural proof: if a plugin can
operate entirely through the public interfaces, the kernel boundary
is real.

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

from forge import ForgeClient, PLANNER_OPS, ProposalError, slugify, validate_proposal

# Backward-compatible alias (pre-M2D name): the ops allowlist is the SDK's
# PLANNER_OPS, one definition, no duplication.
ALLOWED_OPS = PLANNER_OPS

# Re-exported for compatibility: the protocol now lives in the SDK
# (forge.validate_proposal) — one definition, no duplication.
__all__ = ["ReferencePlanner", "ProposalError", "validate_proposal",
           "ALLOWED_OPS"]

_DEFAULT_MILESTONES = ("Foundation", "Core", "Acceptance")


class ReferencePlanner:
    """Deterministic, stdlib-only planner. Goal in, proposal out.

    Takes an optional ForgeClient for the commit path (client.propose).
    Planning itself needs no client — the proposal is a pure function
    of the goal — which is why plan() works without one. commit() is
    the only method that touches Forge, and it goes through the SDK.

    Decomposes a goal into a root task with three milestone children
    (Foundation -> Core -> Acceptance) joined by a dependency chain.
    The decomposition is a skeleton: it is structurally correct by
    construction, and domain intelligence belongs to a smarter planner
    behind the same protocol.
    """

    def __init__(self, client: ForgeClient | None = None) -> None:
        self.client = client

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

    def commit(self, proposal: dict) -> dict:
        """Commit through the SDK — atomic, whole or nothing. The
        planner never touches the kernel directly; ForgeClient does."""
        if self.client is None:
            raise ProposalError("no client: construct ReferencePlanner(client) to commit")
        return self.client.propose(proposal)
