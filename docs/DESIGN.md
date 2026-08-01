# Forge Design Decisions

Forge is a deterministic project kernel for autonomous software
engineering. This document records the decisions that shape it.

## The boundary

The kernel owns project state as an event-sourced task graph. It is
pure, deterministic Python with zero dependencies. Humans, LLM
planners, executors, verifiers, and MCP servers are interchangeable
clients of one official API.

- The planner proposes; the kernel decides.
- The executor never decides it is done.
- Nobody touches state directly.

`forge.kernel.Kernel` is the ONLY mutation path (`docs/API.md`).
Planners return proposals; the kernel validates, persists, applies.
The LLM is never trusted with the graph.

## Decisions

- **Event sourcing.** The only state is an append-only `events.log`
  (JSONL, schema frozen in `docs/EVENTS.md`). The graph is a fold over
  the log. Undo = truncate, replay = refold, crash recovery = skip torn
  line, audit = the log itself.
- **One official API.** Planners return *proposals*; the kernel
  validates, persists, applies. The LLM is never trusted with the
  graph.
- **Derived states.** `blocked`/`ready`/completion are never stored —
  computed from dependencies. A container's `done` derives from its
  children.
- **Runtime expansion.** A task mid-work can be expanded into children;
  the parent completes when its children do. The graph evolves instead
  of the executor guessing.
- **Hard vs soft evidence.** `hard` = tests/compile/benchmark (machine
  verifiable). `soft` = LLM/human review (asserted). Verification gates
  reject until the evidence holds.
- **Context Builder.** `forge show TASK` produces the exact package an
  LLM client needs. No context reconstruction, no state guessing.
- **Concurrency by construction.** Writes are serialized by an OS file
  lock (`events.lock`); `seq` is unique across processes. N agents can
  emit events simultaneously.

## State machine

```
todo ──start──► in_progress ──verify-fail──► needs_revision
                  │  ▲                            │
                  │  └─────────retry──────────────┘
                  └──────verify-pass──────► done ──reopen──► in_progress
```

`verify-pass` is rejected while dependencies are incomplete (`--force`
overrides — humans can break rules, machines shouldn't). Containers
cannot be verified directly; they complete when all children complete.
