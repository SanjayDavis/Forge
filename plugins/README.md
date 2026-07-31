# Plugins

Everything that is not the kernel lives here. The kernel is frozen
(docs/SPEC.md Appendix A); this directory is where it grows.

Each plugin is a client of the public SDK (`forge.ForgeClient`) and the
protocols in the spec. A plugin never touches `events.log` directly and
never mutates the graph except through the kernel. The rule that keeps
this honest: **if a plugin needs a private shortcut into the kernel,
that is a missing kernel API, not a plugin bug.**

| directory    | role                                          | spec     |
|--------------|-----------------------------------------------|----------|
| `planner/`   | goal -> Proposal; emits events only          | §9 (Planner Protocol) |
| `reference/` | the human: next -> do -> evidence -> verify  | SDK usage |
| `executor/`  | task package -> artifacts + hard evidence    | §10 (Executor Protocol) |
| `reviewer/`  | acceptance judgment -> soft evidence         | §11 (Reviewer Protocol) |
| `mcp/`       | wire protocol exposing the SDK               | (M5, last) |

Status:
- M2A (Planner Protocol) is specified (SPEC §9) and enforced by the
  compliance suite (`tests/compliance/`).
- **M2B (Planner Plugin) is DONE.** `planner/` ships a reference planner
  (`ReferencePlanner`) that consumes **only the public SDK**
  (`forge.ForgeClient`, `forge.validate_proposal`, `forge.slugify`) —
  never kernel internals. It emits only proposals (SPEC §9.1); the
  kernel decides. Tested by `tests/test_planner.py` (26 tests): valid
  proposals commit atomically, intentionally invalid ones are rejected
  by the protocol check or by the kernel on commit — whole or nothing.
- **Context API is DONE.** `forge context <task>` / `ForgeClient.context()`
  emits the standard context contract package (Task / Description /
  Acceptance / Dependencies / Knowledge / Relevant Files / Evidence /
  Constraints) — the ~500-token package every coding agent reads
  instead of the graph. Tested in `tests/test_sdk.py`.
- **SDK is DONE.** `forge.ForgeClient` is the one public surface:
  `next()`, `context()`, `propose()`, `start()`, `attach_evidence()`,
  `verify()`, `verify_fail()`, `query()`, `progress()`, `replay()`.
  Thin facade — no graph logic, no replay logic, no scheduler logic.
  The CLI itself speaks the SDK for proposal flows.
- **Reference (human) client is DONE.** `reference/reference_client.py`
  is a tiny loop — next, do, attach hard evidence, verify — proving the
  SDK is comfortable for a non-AI. If a human can't use the API
  comfortably, an AI won't either.
- M3 (Executor) is next — and now thin: five client calls.

The reference planner is deliberately AI-free: it proves the boundary.
An LLM planner is a drop-in replacement behind the same protocol —
same proposal shape, same commit path, same distrust.
