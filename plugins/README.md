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
  `next()`, `context()`, `propose()`, `start()`, `expand()`,
  `attach_evidence()`, `verify()`, `verify_fail()`, `retry()`,
  `query()`, `progress()`, `replay()`. Thin facade — no graph logic,
  no replay logic, no scheduler logic. The CLI itself speaks the SDK
  for proposal flows.
- **Reference (human) client is DONE.** `reference/reference_client.py`
  is a tiny loop — next, do, attach hard evidence, verify — proving the
  SDK is comfortable for a non-AI. If a human can't use the API
  comfortably, an AI won't either.
- **M3 (Executor) is DONE.** `plugins/executor/` ships a reference
  executor (`ReferenceExecutor`): the whole executor flow in five client
  calls — next, start, context, work, hard evidence, verify. The worker
  (the llm slot) reads exactly the context contract package and returns
  artifacts with byte-exact claims; the executor machine-verifies every
  claim itself **before** attaching hard evidence, so a lying or buggy
  worker is caught — no evidence, `verify_fail` → NeedsRevision (§10.2),
  `retry()` back to work. Too-large tasks are re-split through the
  SDK's new `expand()` (§10.3): the kernel derives child ids and commits
  atomically; the container completes when its children do. Tested by
  `tests/test_executor.py` (23 tests): the five-call flow, the
  self-check, expansion, recovery, the SDK-only boundary — plus an
  end-to-end run where a planner proposal is executed to done by the
  reference client script. An LLM executor is a drop-in worker behind
  the same protocol.
- **M4 (Reviewer) is DONE.** `plugins/reviewer/` ships a reference
  reviewer (`ReferenceReviewer`): the whole review flow in three client
  calls — context, judge, then approve (soft evidence + verify) or
  reject (soft evidence + verify_fail). The judge is the llm slot;
  the deterministic reference judge checks that every acceptance
  criterion is covered by the evidence or relevant files on record.
  The reviewer attaches **only soft evidence**, never writes files,
  and never overrides the dependency gate — if the kernel refuses
  (dependencies not done), it reports `blocked` and leaves the task
  untouched. `parse_context` (the Context Contract reader) now lives
  in the SDK, so every client parses the same canonical package.
  Tested by `tests/test_reviewer.py` (17 tests): the three-call flow,
  the judge slot (reference + drop-in), the blocked path, the SDK-only
  boundary — plus an end-to-end run where a planner proposal is worked
  (executor slot) and judged (reviewer slot) to done by the reference
  client script. An LLM reviewer is a drop-in judge behind the same
  protocol.

The reference planner is deliberately AI-free: it proves the boundary.
An LLM planner is a drop-in replacement behind the same protocol —
same proposal shape, same commit path, same distrust.
