"""BharatCodePlanner — an LLM-backed planner for Forge.

Implements the same protocol as ``forge_planner.ReferencePlanner``:
``plan(goal, ...) -> proposal dict`` and ``commit(proposal)``. The
difference is that the decomposition is produced by a BharatCode model
instead of a deterministic skeleton. The output is still validated by
``forge.validate_proposal`` and committed through the SDK, so the kernel
boundary is untouched.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional

from forge import ForgeClient, PLANNER_OPS, ProposalError, slugify, validate_proposal
from forge_bharatcode._http import (
    BharatCodeHTTPError,
    chat_completion,
    resolve_api_key,
)

# Re-export for callers that want the HTTP error type under one name.
BharatCodeError = BharatCodeHTTPError


_SYSTEM_PROMPT = """You are a planner for Forge, a deterministic project kernel.

Given a goal, produce a JSON proposal that decomposes it into a task graph.
Output ONLY a single JSON object. No markdown, no prose, no code fences.

The JSON shape (SPEC §9.1-§9.3):
{
  "proposal_id": "prop_<slug>_<8 hex>",
  "reason": "<one sentence why this decomposition>",
  "confidence": <number 0.0-1.0>,
  "events": [ ... ]
}

Allowed event ops (§9.6): task_created, task_expanded, task_updated,
dependency_added. Never include "seq" — the kernel stamps sequence numbers.

Rules:
- First event: task_created for the root, id = slugified goal (lowercase,
  a-z0-9 and hyphens). Include title, description, acceptance (list),
  files (list), notes (list), priority.
- Second event: task_expanded on the root with 3-6 children. Each child
  has id, title, description, acceptance (list), files (list), priority.
  Child ids must be unique slugs derived from their titles.
- Add dependency_added events to chain children in execution order
  (child[i] depends_on child[i-1]).
- acceptance criteria should be concrete and testable.
- priority is one of low, medium, high.

Return valid JSON only."""


def _slug(s: str) -> str:
    return slugify(s)


def _extract_json(text: str) -> Dict[str, Any]:
    """Pull a JSON object out of model output, tolerating fences/prose."""
    text = text.strip()
    # Strip markdown code fences.
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # Try direct parse.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back: find the first balanced-ish object.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise ProposalError(f"model did not return valid JSON: {text[:300]}")


class BharatCodePlanner:
    """LLM-backed planner using the BharatCode model API."""

    def __init__(
        self,
        client: Optional[ForgeClient] = None,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> None:
        self.client = client
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def plan(
        self,
        goal: str,
        children: Optional[List[Dict[str, Any]]] = None,
        priority: str = "medium",
        confidence: float = 0.9,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        goal = (goal or "").strip()
        if not goal:
            raise ProposalError("goal must be a non-empty string")
        if priority not in ("low", "medium", "high"):
            raise ProposalError(f"priority must be low/medium/high, got {priority!r}")

        # If the caller supplies children, fall back to deterministic skeleton
        # generation is NOT what we want; but to keep the LLM honest we still
        # ask it to plan. Children hint is folded into the user prompt.
        user_parts = [f"Goal: {goal}", f"Priority: {priority}"]
        if children is not None:
            user_parts.append(
                "Suggested milestone titles (use or adapt): " +
                ", ".join(c.get("title", "") for c in children))
        user_parts.append("Produce the proposal JSON now.")
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(user_parts)},
        ]

        raw = chat_completion(
            messages,
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )

        proposal = _extract_json(raw)

        # Normalize: ensure proposal_id exists.
        if not proposal.get("proposal_id"):
            proposal["proposal_id"] = f"prop_{_slug(goal)[:20]}_{uuid.uuid4().hex[:8]}"
        if not proposal.get("reason"):
            proposal["reason"] = reason or f"Decompose '{goal}' via BharatCode model"
        if "confidence" not in proposal:
            proposal["confidence"] = confidence

        # The model may omit priority on events; fill defaults.
        for ev in proposal.get("events", []):
            if ev.get("op") == "task_created" and "priority" not in ev:
                ev["priority"] = priority
            if ev.get("op") == "task_expanded":
                for c in ev.get("children", []):
                    if "priority" not in c:
                        c["priority"] = priority
                    if "acceptance" not in c:
                        c["acceptance"] = []
                    if "files" not in c:
                        c["files"] = []
                    if "description" not in c:
                        c["description"] = ""
            if ev.get("op") == "task_created":
                for f in ("description", "acceptance", "files", "notes"):
                    if f not in ev:
                        ev[f] = [] if f in ("acceptance", "files", "notes") else ""

        validate_proposal(proposal)
        return proposal

    def commit(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        if self.client is None:
            raise ProposalError(
                "no client: construct BharatCodePlanner(client) to commit")
        return self.client.propose(proposal)
