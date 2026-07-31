"""ReferenceExecutor — M3, the executor plugin (SPEC §10).

Task package in, artifacts + hard evidence out; the kernel decides done.

The whole executor flow in five client calls:

    next -> start -> context -> work -> attach hard evidence -> verify
    (ForgeClient)              (worker: the llm slot)   (kernel decides)

The executor never decides it's done — `client.verify()` runs the
kernel's verifier gate (I6), and only the kernel can flip the task to
`done`. On failure the executor proposes `verification_failed` (§10.2)
and the task goes `needs_revision`. And it never attaches hard evidence
for a claim it did not machine-verify itself: a lying or buggy worker
is caught before any evidence lands.

Like the planner, this consumes ONLY the public SDK
(`forge.ForgeClient`) — no kernel internals, no graph, no replay. That
is the architectural proof: if a plugin can operate entirely through
the public interfaces, the kernel boundary is real.

This is a REFERENCE executor: deterministic, stdlib-only, no AI. The
default worker writes a stub artifact (title, description, acceptance
checklist) to prove the loop. Any LLM executor is a drop-in replacement
behind the same protocol — same flow, same evidence kinds, same verify.

Worker contract — worker(ctx_yaml: str) -> WorkResult:

    {"artifacts": [{"path": str, "bytes": int}, ...],   # claims to verify
     "expand":    [{"title": str, ...}, ...]}           # §10.3, optional

The executor machine-checks every artifact claim (path exists, size
byte-exact) and only then attaches hard evidence. `expand` takes
precedence: the task is re-split through the SDK's expand() — the
kernel derives the child ids and commits atomically (§10.3) — and the
children become the work.
"""
from __future__ import annotations

import os
from functools import partial
from typing import Any, Callable

from forge import ForgeClient, GraphError


class ExecutorError(Exception):
    """The context package is malformed or the worker violated the
    WorkResult contract. Nothing is attached or verified."""


# --------------------------------------------------------------------------- the context package (frozen YAML subset, SPEC Appendix C)
def parse_context(text: str) -> dict[str, Any]:
    """Parse the frozen Context Contract YAML subset emitted by
    `forge show` / `ForgeClient.context()`. Strictly bound to the
    contract's fixed shape (section order, indented items, single-quoted
    scalars) — not a general YAML parser. An LLM worker reads the same
    package natively; this is what the reference worker needs."""
    lines = text.splitlines()
    if not lines or not lines[0].startswith("Task: "):
        raise ExecutorError(
            "context package must open with 'Task: <id> — <title>'")
    rest = lines[0][len("Task: "):]
    if " — " not in rest:
        raise ExecutorError("context header must be 'Task: <id> — <title>'")
    task_id, title = rest.split(" — ", 1)  # id is first; title may contain ' — ' itself
    pkg: dict[str, Any] = {
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


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s.startswith("'") and s.endswith("'"):
        return s[1:-1].replace("''", "'")
    return s


def render_artifact(pkg: dict[str, Any]) -> str:
    """The stub document the reference worker produces: title,
    description, acceptance checklist, constraints. Deterministic — no
    timestamps, no randomness. An LLM executor replaces this with real
    code; this proves the loop."""
    out = [f"# {pkg['task']} — {pkg['title']}", ""]
    if pkg["description"]:
        out.append(pkg["description"])
        out.append("")
    out.append("## Acceptance")
    out.append("")
    if pkg["acceptance"]:
        out.extend(f"- [ ] {a}" for a in pkg["acceptance"])
    else:
        out.append("- [ ] (none stated)")
    if pkg["constraints"]:
        out.append("")
        out.append("## Constraints")
        out.append("")
        out.extend(f"- {c}" for c in pkg["constraints"])
    out.append("")
    out.append("_Reference stub produced by ReferenceExecutor — "
               "deterministic, no AI. An LLM executor writes real code here._")
    return "\n".join(out)


def default_worker(ctx_yaml: str, artifact_dir: str = "artifacts") -> dict[str, Any]:
    """Deterministic worker: write a stub artifact for the task package
    and claim it byte-exact. The executor re-checks the claim itself
    before any evidence is attached — the worker is never trusted."""
    pkg = parse_context(ctx_yaml)
    path = os.path.join(artifact_dir, f"{pkg['task']}.md")
    os.makedirs(artifact_dir, exist_ok=True)
    content = render_artifact(pkg)
    # newline="" disables \n -> \r\n translation so the claimed byte
    # count is exactly what lands on disk on every platform.
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    return {"artifacts": [{"path": path, "bytes": len(content.encode("utf-8"))}]}


# --------------------------------------------------------------------------- the executor
class ReferenceExecutor:
    """SPEC §10 executor. Task package in, artifacts + hard evidence
    out; the kernel decides done. Five client calls per task — next,
    start, context, attach_evidence, verify — with the worker sitting in
    the llm slot. Never touches the graph; ForgeClient is the only
    surface, exactly like the planner."""

    def __init__(self, client: ForgeClient, worker: Callable[[str], dict] | None = None,
                 artifact_dir: str = "artifacts") -> None:
        self.client = client
        self.worker: Callable[[str], dict] = worker or partial(
            default_worker, artifact_dir=artifact_dir)
        self.artifact_dir = artifact_dir

    # ---- the loop
    def run(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Walk ready tasks until none are left (or `limit` are done).
        Each task: claim, read the contract package, work, attach
        machine-verified hard evidence, let the kernel verify. Tasks
        the executor expanded become the next ready work (§10.3)."""
        results = []
        while limit is None or len(results) < limit:
            task = self.client.next()
            if task is None:
                break
            results.append(self.execute(task["id"]))
        return results

    # ---- one task: the five client calls
    def execute(self, task_id: str) -> dict[str, Any]:
        """The whole executor flow for one task. Returns
        {task, status: done|needs_revision|expanded, ...}. A rejected
        expansion or verify propagates — kernel atomicity means nothing
        partial happened; the caller decides how to continue."""
        # 1. claim — an in_progress task is a resume (retry path, §10.2):
        # same executor, same claim. The kernel's gates still decide
        # everything downstream, so a real error (unknown task, already
        # done, container) surfaces at context/verify.
        try:
            self.client.start(task_id)
        except GraphError:
            pass
        # 2. the contract package — what the worker reads, not the graph
        ctx = self.client.context(task_id)
        # 3. work — the llm slot; any exception is an honest failure
        try:
            result = self.worker(ctx)
        except Exception as exc:
            return self._fail(task_id, f"worker raised {type(exc).__name__}: {exc}")
        if not isinstance(result, dict):
            return self._fail(
                task_id, f"worker returned {type(result).__name__}, not a WorkResult dict")
        if result.get("expand"):
            return self._expand(task_id, result["expand"])
        # 4. machine-verify every claim BEFORE any evidence is attached
        failures = self._check_artifacts(result)
        if failures:
            return self._fail(task_id, "; ".join(failures))
        for a in result["artifacts"]:
            self.client.attach_evidence(
                task_id, "hard", "executor:artifact-check",
                f"{a['path']} exists ({a['bytes']} bytes)")
        # 5. the kernel decides done — never the executor
        verdict = self.client.verify(task_id)
        return {"task": task_id, "status": "done",
                "artifacts": [a["path"] for a in result["artifacts"]],
                "evidence": len(result["artifacts"]), "verdict": verdict}

    # ---- the self-check: hard evidence only for machine-verified claims
    def _check_artifacts(self, result: dict[str, Any]) -> list[str]:
        """Verify every artifact claim: the path must exist and its size
        must match the worker's claim byte-exact. A lying or buggy
        worker is caught here — the executor never trusts it."""
        artifacts = result.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            return ["worker returned no valid artifacts"]
        failures = []
        for a in artifacts:
            if not isinstance(a, dict) or "path" not in a or "bytes" not in a:
                failures.append(f"malformed artifact claim: {a!r}")
                continue
            if not os.path.exists(a["path"]):
                failures.append(f"artifact missing: {a['path']}")
            elif os.path.getsize(a["path"]) != a["bytes"]:
                failures.append(
                    f"artifact size mismatch: {a['path']} "
                    f"({os.path.getsize(a['path'])} != {a['bytes']} bytes)")
        return failures

    # ---- §10.2 failure path: soft evidence for the gap, then verify_fail
    def _fail(self, task_id: str, reason: str) -> dict[str, Any]:
        """Soft evidence records why, then `verification_failed` sends
        the task to needs_revision. The executor never decides done; the
        kernel records the rejection."""
        self.client.attach_evidence(task_id, "soft", "executor:self-check", reason)
        self.client.verify_fail(task_id, reason)
        return {"task": task_id, "status": "needs_revision", "reason": reason}

    # ---- §10.3 expansion: too large for one pass -> SDK expand
    def _expand(self, task_id: str, children: list[dict]) -> dict[str, Any]:
        """Re-split the task: the executor requests task_expanded through
        the SDK; the kernel validates (task exists, not completed, child
        ids derived and unique), commits atomically, and makes the task
        a container. Rejected whole on any violation — the kernel's
        verdict, not ours to paper over. run() then works the children.

        (Expansion cannot ride the §9 proposal envelope: the merge
        path validates incoming logs in isolation for merge semantics,
        and an expansion references an already-existing task. The SDK
        method is the executor's path — same kernel authority, same
        atomicity.)"""
        event = self.client.expand(task_id, children)
        return {"task": task_id, "status": "expanded",
                "children": [c["id"] for c in event["children"]]}


__all__ = ["ExecutorError", "ReferenceExecutor", "default_worker",
           "parse_context", "render_artifact"]
