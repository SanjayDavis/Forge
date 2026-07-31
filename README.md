# Forge

> **Forge is a deterministic project kernel.** Planners, executors,
> reviewers, humans, and AI agents are all clients of the kernel.

```
Forge
├── Forge Specification   docs/SPEC.md — the contract
├── Forge Kernel          forge/ — the deterministic core
├── Forge CLI             the `forge` command
├── Forge Planner / Executor / Reviewer   plugins/ (spec §9–§11)
└── Forge MCP / Forge UI  wire protocol and surfaces (M4, last)
```

**A deterministic project kernel for autonomous software development.**

> **Everything is a proposal until the kernel accepts it.**

The kernel owns project state as an event-sourced task graph. It is
pure, deterministic Python with zero dependencies — no AI anywhere in
the core. Humans, LLM planners, executors, verifiers, and MCP servers
are interchangeable **plugins** of the same official API.

```
LLM ──┐
      ├──► Forge Kernel ──► events.log (source of truth)
Human ─┘        │
                ├── scheduler (ready/next/blockers, priority-ordered)
                ├── verifier gates (hard: tests/lint, soft: review)
                ├── context builder (focused package per task)
                ├── inspector (task dossier + history)
                └── query language (safe expression subset)
```

The graph is the **shared memory and execution state**: LLM ↓ Graph ↓
Algorithms ↓ LLM. Deterministic code handles scheduling, dependency
resolution, verification, and progress; the LLM is used only where it's
strongest — planning, writing code, reviewing. It never owns the graph;
it proposes, the kernel decides.

> **The kernel owns the project state. Agents only propose changes.**
> Git is the source of truth for code. Forge is the deterministic
> source of truth for project state.

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
  implementation claiming to be Forge v1.0 must pass it. 105 tests,
  all green.

Then the clients — each a plugin, each a separate product on top of
the kernel:

- **M2B — Planner plugin (done).** The first AI client. `plugins/planner/`
  ships a reference planner: goal in, `{proposal_id, reason, confidence,
  events}` out — a proposal, never a mutation. The kernel commits it
  atomically or rejects it whole (`import_events`). The planner test
  suite (23 tests) feeds the kernel both valid and intentionally
  invalid proposals and asserts its verdicts. It also flushed out a
  fourth real kernel bug — a byte/char mismatch in torn-tail recovery
  that truncated valid events after multi-byte titles (fixed, with
  regression tests; 105 tests, all green). An LLM planner is a drop-in
  behind the same protocol.
- **M3 — Executor plugin (next).** `forge show` output in, code out, hard
  evidence attached (SPEC §10).
- **M4 — Reviewer plugin.** Acceptance judgment gates soft
  verification (SPEC §11).
- **M5 — MCP server.** A wire protocol exposing the kernel API — the
  last layer, never the architecture.
- **M6 — VS Code extension.** The CLI with a panel.
- **M7 — Web UI.** `forge ui`: project, graph, history, replay,
  evidence.
- **M8 — Multi-agent orchestrator.** Many agents, one kernel, one
  source of truth.
- **v2 — Discussion.** Hypergraph semantics (Appendix B) and anything
  else the clients teach us. Additive, spec-amended, version-bumped.

Nobody owns the project; the kernel does. Git stores source code.
Forge stores project state.

## Test

```
python -m unittest discover -s tests
```

Zero dependencies, Python 3.10+.
