# Forge

> **A deterministic project kernel for autonomous software engineering.**

Forge separates project state from AI. Instead of letting LLMs mutate
projects directly, Forge requires every change to be **proposed,
validated, and committed** through a deterministic kernel.

> **Everything is a proposal until the kernel accepts it.**

```
Most AI projects:          Forge:
Prompt                      LLM
   │                         │
   ▼                         ▼
  LLM                     Proposal        {proposal_id, reason, confidence, events}
   │                         │
   ▼                         ▼
 Code                      Kernel          validate → append → apply
                             │
                             ▼
                        Validated State    event-sourced · deterministic · auditable
```

The kernel owns project state as an event-sourced task graph. It is
pure, deterministic Python with zero dependencies — no AI anywhere in
the core. Humans, LLM planners, executors, verifiers, and MCP servers
are interchangeable **clients** of the same official API. The planner
proposes; the kernel decides. The executor never decides it's done.
Nobody touches state directly.

> **Git is the source of truth for code. Forge is the deterministic
> source of truth for project state.**

See **[WHY_FORGE.md](WHY_FORGE.md)** for the motivation: why
conversations and markdown plans are a bad place to keep state, and why
a frozen kernel with a proposal protocol is a better one.

## Current status

The **kernel is stable and frozen at v1**. The ecosystem around it is
under active development — this release is `0.1.0-alpha`.

- ✅ Kernel complete — event-sourced task graph, deterministic
  scheduler, verifier gates, query language, inspector
- ✅ Specification frozen — `docs/SPEC.md` v1.0 is the contract
- ✅ Compliance suite — 12 portable tests mapping one-to-one to the
  invariants I1–I7; pass without reading the implementation
- ✅ Planner protocol — SPEC §9: proposals, never mutations
- ✅ SDK — `forge.ForgeClient`, the one public surface every client uses
- ✅ Context API — the ~500-token context contract package every coding
  agent reads instead of the graph
- ✅ Executor — `plugins/executor/` ReferenceExecutor: task package in,
  artifacts + machine-verified hard evidence out, the kernel decides done
- ✅ Reviewer — `plugins/reviewer/` ReferenceReviewer: acceptance
  judgment as soft evidence, the kernel decides done
- ⬜ MCP server
- ⬜ VS Code / Web UI

## Architecture

```
                Human ─┐
                Planner │   (proposals only — never touch the graph)
                Executor├──► Proposal Layer ──► Kernel ──► events.log
                Reviewer│        (validate → append → apply)
                MCP     ─┘
                                 │
                                 ├── scheduler (ready/next/blockers, priority-ordered)
                                 ├── verifier gates (status/dependency/container)
                                 ├── context builder (the ~500-token contract package)
                                 ├── inspector (task dossier + history)
                                 └── query language (safe expression subset)
```

Above the line: intelligence. Below it: deterministic computing.

The SDK in five calls — the whole executor flow:

```python
from forge import ForgeClient

forge = ForgeClient("path/to/project")
task = forge.next()                        # next ready task
ctx  = forge.context(task["id"])           # the ~500-token contract
result = llm(ctx)                          # code, tests
forge.attach_evidence(task["id"], "hard", "unittest", detail)
forge.verify(task["id"])                   # Forge decides "done", not the LLM
```

One implementation. Many clients: Hermes, Claude Code, Codex, a human
with a terminal (`plugins/reference/`), an MCP server, a VS Code panel.

## The contract

`docs/SPEC.md` is the Forge Specification v1.0 — the normative
contract: task model, frozen event schema, state machine, scheduler,
verification, context builder, query language, and the Planner /
Executor / Reviewer protocols. The kernel is **frozen at v1** (like
Git's object model): implementations and plugins change; the spec and
the event schema don't. Anything new lives in a plugin, not the core.

## Design decisions

- **Event sourcing.** The only state is an append-only `events.log`
  (JSONL, schema frozen in `docs/EVENTS.md`). The graph is a fold over
  the log. Undo = truncate, replay = refold, crash recovery = skip torn
  line, audit = the log itself.
- **One official API.** `forge.kernel.Kernel` is the ONLY mutation
  path (`docs/API.md`). Planners return *proposals*; the kernel
  validates, persists, applies. The LLM is never trusted with the graph.
- **Derived states.** `blocked`/`ready`/completion are never stored —
  computed from dependencies. A container's `done` derives from its
  children.
- **Runtime expansion.** A task mid-work can be expanded into children;
  the parent completes when its children do. The graph evolves instead
  of the executor guessing.
- **Hard vs soft evidence.** `hard` = tests/compile/benchmark (machine
  verifiable). `soft` = LLM/human review (asserted). Verification gates
  reject until the evidence holds.
- **Context Builder.** `forge show TASK` produces the exact package an LLM
  client needs. No context reconstruction, no state guessing.
- **Concurrency by construction.** Writes are serialized by an OS file
  lock (`events.lock`); `seq` is unique across processes. N agents can
  emit events simultaneously.

## Install

```
python -m pip install -e .
forge --help
```

(Works without install too: `python -m forge.cli ...`)

## Quickstart

```
forge -d myproject init
cd myproject

forge create "Snake Game" --desc "A terminal snake game" -a "game runs" --priority high
forge expand snake-game \
    -c "Window::terminal window" \
    -c "Renderer::draws the board::renders;tests pass" \
    -c "Input::keyboard controls"
forge graph                       # see the tree
forge next                        # what to work on (priority order)
forge start window
forge evidence window --kind hard --source unittest --detail "14 passed"
forge verify-pass window          # hard gate: deps must be done first
forge verify-fail input --reason "edge cases missing"
forge retry input
forge show input                  # context package for an LLM client
forge inspect renderer            # dossier: children, evidence, history
forge query "status == needs_revision and priority == high"
forge query blockers(renderer)
forge blockers snake-game --chain # root-cause paths
forge progress
forge undo                        # truncate the last event
forge replay                      # rebuild the graph from the log
```

## States

```
todo ──start──► in_progress ──verify-fail──► needs_revision
                  │  ▲                            │
                  │  └─────────retry──────────────┘
                  └──────verify-pass──────► done ──reopen──► in_progress
```

`verify-pass` is rejected while dependencies are incomplete (`--force`
overrides — humans can break rules, machines shouldn't). Containers can't
be verified directly; they complete when all children complete.

## Commands

```
init          create events.log in DIR
create        add a task (--id, --desc, -a acceptance, -f file, --priority)
update        change title/desc/acceptance/files/priority
dep           add/remove a dependency (--remove)
expand        turn a task into a container; children become its work
start         todo -> in_progress
verify-pass   in_progress -> done (requires deps done; --force bypasses)
verify-fail   in_progress -> needs_revision (--reason required)
retry         needs_revision -> in_progress
reopen        done -> in_progress
evidence      attach hard/soft evidence (--kind, --source, --detail)
note          append a note
delete        remove a task (no dependents, no children)
show          context package (--json for machine format)
inspect       full dossier: status, completion, children, evidence, history
query         expression filter / function call (--json)
export        event log as portable JSON (FILE or stdout)
import        merge an exported log; id collisions rejected
graph         render the task tree (optional root TASK)
ready         list tasks ready to work on
next          the single next task
blockers      incomplete deps (--chain for root-cause paths)
progress      done/total + per-status counts
validate      consistency check (cycles, dangling refs)
log           view events (--tail N)
undo [N]      truncate the last N events
replay        reconstruct the graph from the log
demo          seed the Snake Game example (empty project only)
```

## Query examples

```
forge query "status == needs_revision"
forge query "priority > medium"                    # low < medium < high
forge query '"snake" in title and not blocked'
forge query "evidence_count >= 2 and status == done"
forge query "id in children(renderer)"
forge query blockers(renderer)
forge query evidence(input)
forge query ready()
```

## Roadmap

The kernel is **complete at v1.0 and frozen**. Everything after this
line is a client of the kernel, not the kernel.

- **M1 — Core kernel (done).** Graph, event log, scheduler, context
  builder, CLI, verification flow. Zero deps, no AI.
- **M1.5 — Stress + freeze (done).** Schema v1 frozen, official Kernel
  API, inspector, query language, priority, cross-process locking,
  merge/export/import. Verified: 100k events replay in <1s, 5-thread
  and 4-process concurrent writers, 5-level expansion, cycle rejection.
- **v1.0 — Kernel complete (done).** `docs/SPEC.md` is the contract:
  task model, event schema, state machine, scheduler, verification,
  context builder, query language, Planner/Executor/Reviewer protocols
  (M2A included — SPEC §9), invariants I1–I7, freeze policy
  (Appendix A). No new kernel features without a spec change and
  version bump.
- **Compliance — the kernel passes its own spec (done).**
  `tests/compliance/` is the Specification Compliance Suite: it maps
  one-to-one to invariants I1–I7 — malformed proposals, fuzzed event
  streams, torn-log crash recovery, atomic proposal commits, replay
  identity across hash seeds, scheduler determinism. It found and
  fixed four real gaps before freeze (un-stamped proposal events,
  torn-tail line merging, torn-tail seq duplication, byte/char drift in
  tail recovery). Every
  implementation claiming to be Forge v1.0 must pass it. 124 tests,
  all green.

Then the clients — each a plugin, each a separate product on top of
the kernel:

- **M2B — Planner plugin (done).** The first AI client. `plugins/planner/`
  ships a reference planner: goal in, `{proposal_id, reason, confidence,
  events}` out — a proposal, never a mutation. The kernel commits it
  atomically or rejects it whole (`import_events`). The planner test
  suite feeds the kernel both valid and intentionally invalid proposals
  and asserts its verdicts. It also flushed out a fourth real kernel
  bug — a byte/char mismatch in torn-tail recovery that truncated valid
  events after multi-byte titles (fixed, with regression tests). An LLM
  planner is a drop-in behind the same protocol.
- **Context API — the contract between Forge and every coding agent
  (done).** `forge context <task>` (and `ForgeClient.context(task_id)`)
  returns the standard context package: Task / Description / Acceptance /
  Dependencies (with status) / Knowledge / Relevant Files / Evidence /
  Constraints — roughly 500 tokens instead of a repo's worth of
  conversation. Agents never read the graph; they read this. The SDK
  also ships the reader: `forge.parse_context()` parses a package back
  into the same sections (the canonical reader every client uses).
- **SDK — ForgeClient (done).** `forge/sdk.py` is the one public surface
  every client is allowed to touch: `next()`, `context()`, `propose()`,
  `start()`, `expand()`, `attach_evidence()`, `verify()`, `verify_fail()`,
  `retry()`, `query()`, `progress()`, `replay()`.
  scheduler logic — those stay in the kernel; the SDK is a thin facade.
  **The planner now consumes the SDK instead of kernel internals** — the
  architectural proof that the boundary is real: a plugin operating
  entirely through the public interfaces needs nothing else. The human
  client (`plugins/reference/`, a tiny "next → do → evidence → verify"
  loop) proves the SDK is comfortable for non-AIs too. The CLI itself
  speaks the SDK for all proposal flows.
- **M3 — Executor plugin (done).** `plugins/executor/` ships a reference
  executor (`ReferenceExecutor`): the whole executor flow in five client
  calls — next, start, context, work, hard evidence, verify. The worker
  (the llm slot) reads exactly the context contract package and returns
  artifacts with byte-exact claims; the executor machine-verifies every
  claim itself *before* attaching hard evidence, so a lying or buggy
  worker is caught — no evidence, `verify_fail` → NeedsRevision (§10.2),
  `retry()` back to work. Too-large tasks are re-split through the SDK's
  new `expand()` (§10.3): the kernel derives child ids and commits
  atomically; the container completes when its children do. The suite
  (`tests/test_executor.py`, 23 tests) proves the five-call flow, the
  self-check, expansion, recovery, and the SDK-only boundary — plus an
  end-to-end run where a planner proposal is executed to done by the
  reference client script. An LLM executor is a drop-in worker behind
  the same protocol.
- **M4 — Reviewer plugin (done).** Deterministic checks (tests, build,
  lint) are the executor's hard evidence; the reviewer handles only the
  semantic layer (architecture, readability, design) and emits **soft
  evidence** or `verify_fail` → NeedsRevision. `plugins/reviewer/` ships
  a reference reviewer (`ReferenceReviewer`): three client calls per
  task — context, judge, then approve (soft evidence + verify) or
  reject (soft evidence + verify_fail). The judge is the llm slot
  (`judge(ctx_yaml)`); the reference judge is deterministic and
  stdlib-only — every acceptance criterion must be covered by the
  evidence or relevant files on record, an uncovered criterion is a
  gap. A machine reviewer never overrides the dependency gate: if the
  kernel's structural gate refuses (dependencies not done), it reports
  `blocked` and leaves the task untouched — and the SDK's `verify()`
  doesn't even expose a bypass. The Context Contract reader
  (`parse_context`) moved into the SDK so the reviewer consumes the
  same canonical package every client reads. The suite
  (`tests/test_reviewer.py`, 17 tests) proves the three-call flow, the
  judge slot, the blocked path, and the SDK-only boundary (soft
  evidence only, no file writes, no gate overrides) — plus an
  end-to-end run where a planner proposal is worked (executor slot) and
  judged (reviewer slot) to done by the reference client script. An LLM
  reviewer is a drop-in judge behind the same protocol.
- **M5 — MCP server.** A thin transport over the SDK — `forge_next()`,
  `forge_context()`, `forge_propose()`, `forge_verify()`,
  `forge_query()`, `forge_replay()`. No business logic; it should be
  almost boring.
- **M6 — VS Code extension.** The CLI with a panel.
- **M7 — Web UI.** `forge ui`: project, graph, history, replay,
  evidence.
- **M8 — Multi-agent orchestrator.** Many agents, one kernel, one
  source of truth.
- **v2 — Discussion.** Hypergraph semantics (Appendix B) and anything
  else the clients teach us. Additive, spec-amended, version-bumped.

Repository separation (conceptual, from M2B on): `forge/` holds the
kernel, CLI, SDK, and specification; `forge-hermes/`, `forge-mcp/`,
`forge-vscode/` are separate clients. If a client ever needs a private
shortcut into the kernel, that is a signal the kernel API is missing
something — the SDK boundary is what makes the split safe.

Nobody owns the project; the kernel does. Git stores source code.
Forge stores project state.

## Test

```
python -m unittest discover -s tests
```

Zero dependencies, Python 3.10+.
