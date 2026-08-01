# Forge Roadmap

The kernel is complete at v1.0 and frozen. Everything after this line
is a client of the kernel, not the kernel.

## Kernel milestones (done)

- **M1 — Core kernel.** Graph, event log, scheduler, context builder,
  CLI, verification flow. Zero deps, no AI.
- **M1.5 — Stress + freeze.** Schema v1 frozen, official Kernel API,
  inspector, query language, priority, cross-process locking,
  merge/export/import. Verified: 100k events replay in <1s, 5-thread
  and 4-process concurrent writers, 5-level expansion, cycle rejection.
- **v1.0 — Kernel complete.** `docs/SPEC.md` is the contract: task
  model, event schema, state machine, scheduler, verification, context
  builder, query language, Planner/Executor/Reviewer protocols (M2A
  included — SPEC §9), invariants I1–I7, freeze policy (Appendix A).
  No new kernel features without a spec change and version bump.
- **Compliance — the kernel passes its own spec.** `tests/compliance/`
  is the Specification Compliance Suite: it maps one-to-one to
  invariants I1–I7 — malformed proposals, fuzzed event streams,
  torn-log crash recovery, atomic proposal commits, replay identity
  across hash seeds, scheduler determinism. It found and fixed four
  real gaps before freeze (un-stamped proposal events, torn-tail line
  merging, torn-tail seq duplication, byte/char drift in tail
  recovery). Every implementation claiming to be Forge v1.0 must pass
  it. See `docs/verification.md` for results.

## Client milestones

Each plugin is a separate product on top of the kernel.

- **M2B — Planner plugin (done).** The first AI client.
  `plugins/planner/` ships a reference planner: goal in,
  `{proposal_id, reason, confidence, events}` out — a proposal, never a
  mutation. The kernel commits it atomically or rejects it whole
  (`import_events`). The planner test suite feeds the kernel both valid
  and intentionally invalid proposals and asserts its verdicts. It also
  flushed out a fourth real kernel bug — a byte/char mismatch in
  torn-tail recovery that truncated valid events after multi-byte
  titles (fixed, with regression tests). An LLM planner is a drop-in
  behind the same protocol.
- **Context API — the contract between Forge and every coding agent
  (done).** `forge context <task>` (and `ForgeClient.context(task_id)`)
  returns the standard context package: Task / Description / Acceptance /
  Dependencies (with status) / Knowledge / Relevant Files / Evidence /
  Constraints — roughly 500 tokens instead of a repo's worth of
  conversation. Agents never read the graph; they read this. The SDK
  also ships the reader: `forge.parse_context()` parses a package back
  into the same sections (the canonical reader every client uses).
- **SDK — ForgeClient (done).** `forge/sdk.py` is the one public
  surface every client is allowed to touch: `next()`, `context()`,
  `propose()`, `start()`, `expand()`, `attach_evidence()`, `verify()`,
  `verify_fail()`, `retry()`, `query()`, `progress()`, `replay()`.
  Scheduler logic stays in the kernel; the SDK is a thin facade.
  The planner now consumes the SDK instead of kernel internals — the
  architectural proof that the boundary is real: a plugin operating
  entirely through the public interfaces needs nothing else. The human
  client (`plugins/reference/`, a tiny "next → do → evidence → verify"
  loop) proves the SDK is comfortable for non-AIs too. The CLI itself
  speaks the SDK for all proposal flows.
- **M3 — Executor plugin (done).** `plugins/executor/` ships a
  reference executor (`ReferenceExecutor`): the whole executor flow in
  five client calls — next, start, context, work, hard evidence,
  verify. The worker (the llm slot) reads exactly the context contract
  package and returns artifacts with byte-exact claims; the executor
  machine-verifies every claim itself *before* attaching hard evidence,
  so a lying or buggy worker is caught — no evidence, `verify_fail` →
  NeedsRevision (§10.2), `retry()` back to work. Too-large tasks are
  re-split through the SDK's new `expand()` (§10.3): the kernel derives
  child ids and commits atomically; the container completes when its
  children do. The suite (`tests/test_executor.py`, 23 tests) proves
  the five-call flow, the self-check, expansion, recovery, and the
  SDK-only boundary — plus an end-to-end run where a planner proposal
  is executed to done by the reference client script. An LLM executor
  is a drop-in worker behind the same protocol.
- **M4 — Reviewer plugin (done).** Deterministic checks (tests, build,
  lint) are the executor's hard evidence; the reviewer handles only the
  semantic layer (architecture, readability, design) and emits **soft
  evidence** or `verify_fail` → NeedsRevision. `plugins/reviewer/`
  ships a reference reviewer (`ReferenceReviewer`): three client calls
  per task — context, judge, then approve (soft evidence + verify) or
  reject (soft evidence + verify_fail). The judge is the llm slot
  (`judge(ctx_yaml)`); the reference judge is deterministic and
  stdlib-only — every acceptance criterion must be covered by the
  evidence or relevant files on record, an uncovered criterion is a
  gap. A machine reviewer never overrides the dependency gate: if the
  kernel's structural gate refuses (dependencies not done), it reports
  `blocked` and leaves the task untouched — and the SDK's `verify()`
  does not even expose a bypass. The Context Contract reader
  (`parse_context`) moved into the SDK so the reviewer consumes the
  same canonical package every client reads. The suite
  (`tests/test_reviewer.py`, 17 tests) proves the three-call flow, the
  judge slot, the blocked path, and the SDK-only boundary (soft
  evidence only, no file writes, no gate overrides) — plus an
  end-to-end run where a planner proposal is worked (executor slot) and
  judged (reviewer slot) to done by the reference client script. An
  LLM reviewer is a drop-in judge behind the same protocol.
- **M5 — MCP server (done).** A thin transport over the SDK —
  `forge_next()`, `forge_context()`, `forge_propose()`,
  `forge_verify()`, `forge_query()`, `forge_replay()`. No business
  logic. `plugins/mcp/` ships `ForgeMCPServer` (JSON-RPC 2.0 over
  stdio, stdlib-only, six tools, one SDK call each) plus a reference
  MCP client. The test suite drives it both with a minimal wire client
  and with the official `mcp` Python SDK client (skipped when not
  installed — the canonical suite stays dependency-free).
- **M6 — VS Code extension.** The CLI with a panel.
- **M7 — Web UI.** `forge ui`: project, graph, history, replay,
  evidence.
- **M8 — Multi-agent orchestrator.** Many agents, one kernel, one
  source of truth.
- **v2 — Discussion.** Hypergraph semantics (Appendix B) and anything
  else the clients teach us. Additive, spec-amended, version-bumped.

## Repository separation

Conceptual, from M2B on: `forge/` holds the kernel, CLI, SDK, and
specification; `forge-hermes/`, `forge-mcp/`, `forge-vscode/` are
separate clients. If a client ever needs a private shortcut into the
kernel, that is a signal the kernel API is missing something — the SDK
boundary is what makes the split safe.
