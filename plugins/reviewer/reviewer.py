"""ReferenceReviewer — M4, the reviewer plugin (SPEC §11).

The semantic layer on top of hard evidence: deterministic checks
(tests, build, lint) are the executor's job and land as hard evidence;
the reviewer judges only what tooling cannot — whether the acceptance
criteria are actually met by the files and evidence on record. Review
is soft evidence (§6.1) and it never replaces hard evidence.

The whole review flow in three client calls:

    context -> judge -> approve (soft evidence + verify)
                     -> reject (soft evidence + verify_fail)
    (ForgeClient)      (llm slot)              (kernel decides)

The reviewer never decides it's done — `client.verify()` runs the
kernel's verifier gate (I6), and only the kernel can flip the task to
`done`. On rejection the reviewer proposes `verification_failed`
(§11.2) and the task goes `needs_revision`. If the structural gate
blocks (a dependency is not done, or the task is not started), the
reviewer reports `blocked` — it MUST NOT override the dependency gate
(§11.2: only a human reviewer may; a machine reviewer must not, and the
SDK's `verify()` does not even expose that option).

Boundaries, asserted by tests:
  - soft evidence only: the reviewer never attaches hard evidence;
  - no file writes: the reviewer never touches the filesystem — it
    reads the context package and nothing else;
  - no gate overrides: the dependency gate is the kernel's alone; the
    SDK's verify() does not even expose a bypass option.

Like the planner and executor, this consumes ONLY the public SDK
(`forge.ForgeClient`, `forge.parse_context` — the canonical Context
Contract reader). The context parser lives in the SDK because the SDK
owns the Context Contract; the reviewer reads the same package every
other client reads. No kernel internals, no graph, no replay.

Judge contract — judge(ctx_yaml: str) -> ReviewResult:

    {"verdict": "approve" | "reject",
     "gaps":    [str, ...],   # reject: what the evidence fails to address
     "notes":   [str, ...]}   # approve: why it passed

The reference judge is deterministic and stdlib-only: it checks that
every acceptance criterion is covered by the evidence or relevant files
on record. An LLM reviewer is a drop-in behind the same protocol —
same flow, same evidence kinds, same verify.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from forge import ForgeClient, GraphError, parse_context

# SPEC §11.2: approve attaches soft evidence with source "review:<agent>".
REVIEW_SOURCE = "review:reference"

_STOPWORDS = frozenset("""
    a an and are as at be but by for from have has had he her his i in
    is it its of on or our she so that the their them they this to we
    was were will with you your not can all any one two new make made
    also into over under more most other some such than then there
    these those when where which while who whom why how what what's
""".split())


def _keywords(text: str) -> set[str]:
    """Content words (>= 4 chars, lowercased, stopwords removed) — the
    coverage vocabulary for one acceptance criterion."""
    return {w for w in re.findall(r"[a-z0-9]+", text.lower())
            if len(w) >= 4 and w not in _STOPWORDS}


def default_judge(ctx_yaml: str) -> dict[str, Any]:
    """Deterministic reference judge. An acceptance criterion is
    covered if any of its content words appears in the task's evidence
    or relevant files. Verdicts:

      - no evidence at all            -> reject ("nothing to review");
      - criteria with no coverage    -> reject, gaps listed verbatim;
      - every criterion covered      -> approve;
      - no acceptance criteria       -> approve (vacuous, noted).

    This is the llm slot's deterministic stand-in: it proves the
    protocol with real judgment-shaped output. An LLM judge replaces
    the keyword heuristic with actual reading — same contract."""
    pkg = parse_context(ctx_yaml)
    if not pkg["evidence"]:
        return {"verdict": "reject",
                "gaps": ["no evidence attached — nothing to review"],
                "notes": []}
    corpus = " ".join(pkg["evidence"] + pkg["relevant_files"]).lower()
    gaps = []
    for a in pkg["acceptance"]:
        kws = _keywords(a)
        if kws and not any(k in corpus for k in kws):
            gaps.append(f"no evidence addresses: {a}")
    if gaps:
        return {"verdict": "reject", "gaps": gaps, "notes": []}
    if not pkg["acceptance"]:
        return {"verdict": "approve", "gaps": [],
                "notes": ["no acceptance criteria stated — vacuous approve"]}
    return {"verdict": "approve", "gaps": [],
            "notes": [f"{len(pkg['acceptance'])} acceptance criteria covered "
                      "by evidence/files"]}


class ReferenceReviewer:
    """SPEC §11 reviewer. Context in, soft evidence + verdict out; the
    kernel decides done. Three client calls per task — context, judge,
    approve (soft evidence + verify) or reject (soft evidence +
    verify_fail) — with the judge sitting in the llm slot. Never
    touches the graph; never writes files; never attaches hard
    evidence; never overrides the dependency gate."""

    def __init__(self, client: ForgeClient,
                 judge: Callable[[str], dict] | None = None) -> None:
        self.client = client
        self.judge = judge or default_judge

    # ---- the loop
    def run(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Review every in-progress task that has evidence on record
        (the executor has worked it, the reviewer judges it), until
        none are left (or `limit` are reviewed). Tasks that come back
        `blocked` are set aside, never re-reviewed in this pass — the
        structural gate is the kernel's, and the caller must resolve
        dependencies before asking again."""
        results = []
        seen: set[str] = set()
        while limit is None or len(results) < limit:
            ids = [i for i in self.client.query(
                "status == in_progress and evidence_count >= 1")
                if i not in seen]
            if not ids:
                break
            tid = ids[0]
            seen.add(tid)
            results.append(self.review(tid))
        return results

    # ---- one task: the three client calls
    def review(self, task_id: str) -> dict[str, Any]:
        """The whole review flow for one task. Returns
        {task, status: done|needs_revision|blocked, verdict, ...}."""
        ctx = self.client.context(task_id)
        try:
            verdict = self.judge(ctx)
        except Exception as exc:
            return self._reject(task_id, f"judge raised {type(exc).__name__}: {exc}")
        if not isinstance(verdict, dict) \
                or verdict.get("verdict") not in ("approve", "reject"):
            return self._reject(task_id, f"judge returned an invalid verdict: {verdict!r}")
        if verdict["verdict"] == "reject":
            gaps = [g for g in (verdict.get("gaps") or []) if isinstance(g, str) and g]
            return self._reject(task_id, "; ".join(gaps) if gaps else "rejected by reviewer")
        # approve: soft evidence, then the kernel's structural gate decides
        notes = verdict.get("notes") or []
        detail = "approved — " + ("; ".join(notes) if notes else "acceptance criteria met")
        self.client.attach_evidence(task_id, "soft", REVIEW_SOURCE, detail)
        try:
            self.client.verify(task_id)
        except GraphError as exc:
            # structural gate refused (deps not done / not started /
            # container). A machine reviewer MUST NOT override it.
            return {"task": task_id, "status": "blocked",
                    "verdict": "approve", "reason": str(exc)}
        return {"task": task_id, "status": "done", "verdict": "approve",
                "gaps": [], "notes": notes}

    # ---- §11.2 rejection: soft evidence with the gap, then verify_fail
    def _reject(self, task_id: str, reason: str) -> dict[str, Any]:
        """Soft evidence records why, then `verification_failed` sends
        the task to needs_revision. The reviewer never decides done;
        the kernel records the rejection."""
        self.client.attach_evidence(task_id, "soft", REVIEW_SOURCE,
                                    f"rejected — {reason}")
        self.client.verify_fail(task_id, reason)
        return {"task": task_id, "status": "needs_revision",
                "verdict": "reject", "reason": reason}


__all__ = ["REVIEW_SOURCE", "ReferenceReviewer", "default_judge", "_keywords"]
