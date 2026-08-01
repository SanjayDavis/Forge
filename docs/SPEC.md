# Forge Specification v1.0

> **A deterministic project kernel for autonomous software development.**

> This document is the **contract**. The reference implementation
> (`forge/`, Python) is one implementation of it. Implementations can
> change; the spec does not. Anything not specified here is an
> implementation detail and must not be relied upon.
>
> Normative keywords: **MUST**, **MUST NOT**, **SHOULD**, **MAY**
> (RFC 2119).
>
> **The philosophy — one sentence, the decision rule for every design
> question:**
>
> > **The kernel owns the project state. Agents only propose changes.**
>
> When in doubt, ask which side of that sentence a feature belongs to.
> If it touches state or the rules for changing it, it is kernel work —
> frozen, tested, versioned. If it is judgment, intent, or capability,
> it is agent work — a plugin.

## 0. Positioning

> **Everything is a proposal until the kernel accepts it.**
>
> The kernel owns the project state. Agents only propose changes.
>
> Git is the source of truth for code. Forge is the deterministic
> source of truth for project state.

Forge is **not** an AI framework. It is a **deterministic project
kernel**. Planners, executors, reviewers, humans, and AI agents are all
clients of the kernel — interchangeable, fallible, replaceable. The
kernel owns project state and the rules for changing it; nothing else
does.

```
                 Humans   Claude Code   Codex   Gemini   Hermes
                    │          │          │        │        │
                    ▼          ▼          ▼        ▼        ▼
              ┌─────────────────────────────────────────────────┐
              │        Planner / Executor / Reviewer            │  INTELLIGENCE
              └─────────────────────────────────────────────────┘
                    │          │          │        │        │
                    ▼          ▼          ▼        ▼        ▼
              ┌─────────────────────────────────────────────────┐
              │             Proposal Layer (events)            │  TRUST BOUNDARY
              └─────────────────────────────────────────────────┘
                    │          │          │        │        │
                    ▼          ▼          ▼        ▼        ▼
              ╔═════════════════════════════════════════════════╗
              ║                   PROJECT KERNEL                 ║  DETERMINISM
              ║   Event Store   Graph   Scheduler   Context      ║
              ║   Query   Verification   Import/Export           ║
              ╚═════════════════════════════════════════════════╝
                    │          │          │        │        │
                    ▼          ▼          ▼        ▼        ▼
                    ─────────  Filesystem  ─────────
```

The thick line is the **trust boundary**. Above it: intelligence,
fallible, never trusted with state. Below it: deterministic computing,
tested, frozen. Every agent — no matter how capable or unreliable —
plays by the same rules: **it proposes; the kernel decides.**

## 1. Core Concepts

1.1. **Event.** An immutable, timestamped record of one state change.
     The only way state changes.

1.2. **Event log.** An append-only, line-delimited sequence of events.
     The single source of truth. Append-only means: never edited,
     never reordered, never deleted except by an explicit undo that
     truncates the tail.

1.3. **Graph.** The task graph is a *projection* of the event log: a
     deterministic fold of the events, oldest to newest. It is
     derived, rebuildable, and never persisted as a source of truth.
     If log and graph disagree, the log wins.

1.4. **Project.** A directory containing an event log plus any files
     produced by tasks. The kernel manages the log; tasks manage the
     files.

1.5. **Agent.** Any caller of the kernel: a human via CLI, an LLM
     planner, an executor, a reviewer, a CI job, an MCP server. All
     agents are equal; none owns the project.

1.6. **Proposal.** A structured, signed-free batch of proposed events
     from an agent (see §9). Proposals are validated; invalid ones are
     rejected whole.

1.7. **Derived state.** Anything computable from the log **MUST NOT** be
     stored: `blocked`, `ready`, completion, container `done`. Storing
     derivable state is a spec violation because it can diverge.

1.8. **Kernel determinism.** Given the same log, every implementation
     MUST produce the same graph, the same scheduler answers, and the
     same query results. No randomness, no wall-clock dependence in
     ordering, no hash-order iteration.

1.9. **Kernel invariants.** These hold always. A feature that would
     break one is not a feature; it is a redesign, and it requires a
     spec change and version bump like any other (§Appendix A). Every
     invariant has a compliance test (`tests/compliance/`).

     - **I1 — Deterministic fold.** Every event log folds to exactly
       one state. Environment (locale, hash seed, dict key order) does
       not change the result.
     - **I2 — Replay identity.** Replaying a log reconstructs
       byte-identical state, every time, on any machine.
     - **I3 — Derived state is never persisted.** Nothing computable
       from the log (`blocked`, `ready`, completion, container `done`)
       is ever written to it.
     - **I4 — Atomic proposals.** A proposal commits whole or not at
       all. No partially committed batch exists, even across a crash.
     - **I5 — Deterministic scheduler.** `ready()` / `next()` /
       `progress()` are pure functions of the log; randomized creation
       order cannot change their answers for the same final graph.
     - **I6 — Verification cannot be bypassed.** No event can move a
       task to `done` except a valid `verification_passed`; `force`
       bypasses only the dependency gate, never status or container
       rules.
     - **I7 — Context never invents state.** The Context Builder
       reports only ids, statuses, blockers, and evidence that exist
       in the graph. It is a projection, not a generator.

## 2. Task Model

2.1. A **task** is a unit of work. Fields:

| field        | type        | notes                                    |
|--------------|-------------|------------------------------------------|
| `id`         | string      | unique, immutable, URL-safe slug         |
| `title`      | string      | non-empty                                |
| `description`| string      | free text                                |
| `status`     | string      | one of §4 states                         |
| `parents`    | list[id]    | derived from dependency events           |
| `children`   | list[id]    | set by `task_expanded`                   |
| `acceptance` | list[str]   | criteria; completion is judged against them |
| `evidence`   | list        | typed evidence, see §6                   |
| `files`      | list[str]   | artifacts this task produces/owns        |
| `notes`      | list[str]   | free text                                |
| `priority`   | "low"\|"medium"\|"high" | scheduling hint               |
| `created_seq`| int         | log seq of the event that created it     |

2.2. **Container.** A task with children. Its `done` is *derived*: it
     is done iff all children are done. A container **MUST NOT** be
     verified directly (§6). Children MAY be added at any time via
     `task_expanded`, even after the parent has started — this is
     runtime expansion, the primary mechanism by which the graph
     evolves.

2.3. **Leaf.** A task with no children. Only leaves are verified
     directly.

2.4. **Slugs.** When an agent does not supply an id, the kernel derives
     one from the title: lowercase, non-alphanumeric runs collapse to
     `-`, whitespace stripped. Collisions are resolved by suffixing
     `-2`, `-3`, … An *explicit* duplicate id **MUST** be rejected.

2.5. **Deletion.** A task MAY be deleted only if nothing depends on it
     and it has no children. Deletion removes it from the graph but
     the events remain in the log (history is never rewritten).

## 3. Event Model (FROZEN)

3.1. **Envelope.** Every event is one JSON object, one line. Fields:

| field | type | meaning |
|-------|------|---------|
| `v`   | int  | schema version. Absent means 1. Currently **1**. |
| `seq` | int  | global sequence number. Unique across all processes and agents. Assigned by the kernel at append time under the write lock. |
| `ts`  | str  | UTC ISO-8601 timestamp. |
| `op`  | str  | event type, from the table below. |
| …    |      | op-specific fields. |

3.2. **Operations (v1).** SHAPE = required fields and their types;
     extra fields are permitted but MUST be ignored by the fold.

| op | shape | guards |
|----|-------|--------|
| `task_created` | `id, title`; optional `description, acceptance[], files[], notes[], priority` | id unique, title non-empty, priority in set |
| `task_updated` | `id` + at least one of `title, description, acceptance, files, priority` | task exists; list fields replace |
| `task_expanded` | `task`; `children[]` each `{id, title, description, acceptance[], files[], priority}` | parent exists; child ids new; parent becomes a container |
| `dependency_added` | `task, depends_on` | both exist; no self-edge; no cycle |
| `dependency_removed` | `task, depends_on` | edge exists |
| `task_started` | `id` | status is `todo` |
| `verification_failed` | `id, reason` | status is `in_progress` or `needs_revision`; reason non-empty |
| `task_retried` | `id` | status is `needs_revision` |
| `verification_passed` | `id`; optional `force` | status is `in_progress` or `needs_revision`; not a container; deps done unless `force` |
| `evidence_added` | `id, kind, source`; optional `detail` | kind is `hard` or `soft` |
| `note_added` | `id, text` | |
| `task_deleted` | `id` | no dependents, no children |
| `task_reopened` | `id` | status is `done` |

3.3. **Validation.** Every event — at proposal time, at append time,
     and at load time — MUST pass shape validation and guard
     validation. A log that fails to fold **MUST** fail loudly
     (never silently skipped except the torn-tail case, §12.5).
     Unknown `op` values are errors, as are unknown fields on a known
     op, wrong-typed fields (including optional fields), and task ids
     outside the slug charset `[a-zA-Z0-9][a-zA-Z0-9._-]*` (this keeps
     ids safe as filesystem path components and blocks path traversal
     through plugin artifact writes). Single-line contract fields
     (title, notes, acceptance items, files, evidence source/detail)
     MUST NOT contain line breaks, so the line-based context package
     (§7) can never be injected with fake sections.

3.4. **Flexibility (hypergraph readiness).** v1 is a DAG, but the
     envelope is deliberately open:

     - One task can already gate many dependents (fan-out via
       `dependency_added`): a shared artifact appears as one task that
       many tasks depend on.
     - `task_expanded` makes the structure a tree *of* tasks, but
       dependencies can cross branches, so the graph is a DAG, not a
       tree. The fold never assumes tree-ness.
     - Extension points reserved for v2, without breaking v1:
       **multi-target verification** (`verification_passed` on several
       ids at once), **artifact nodes** (non-task entities that tasks
       produce and consume), **shared outputs** (one task's `files`
       satisfying many goals). These are additive ops with a `v:2`
       stamp and a migration; v1 logs MUST still fold under v2.

## 4. State Machine

4.1. States: `todo`, `in_progress`, `needs_revision`, `done`.

```
todo ──start──────────► in_progress ──verify-fail──► needs_revision
                          │  ▲                          │  ▲
                          │  └────────retry─────────────┘  │
                          │                                │
                          └───────verify-pass──────────────┘
                                   │
                                   ▼
                                 done ──reopen──► in_progress
```

4.2. Transitions are atomic, validated events (§3.3). An illegal
     transition is a rejected proposal, never a silent no-op.

4.3. **Verification gates** (see also §6):

     - `verify-pass` **MUST** be rejected while any dependency is not
       `done`. `force: true` bypasses *only* the dependency gate —
       never the status gate, never the container rule.
     - `verify-pass` on a container **MUST** be rejected.
     - A task's *effective* status is its own status, except a
       container with all children done is `done` regardless of its
       stored status.

4.4. **Retry budget.** `verification_failed` records a failure; the
     kernel tracks failure count and last failure reason per task.
     `needs_revision` tasks are not done; they return to work via
     `task_retried`. Budgets are advisory: an agent SHOULD stop
     retrying after repeated failures, but only a human (or a policy
     set by a human) MAY hard-stop a task.

## 5. Scheduler

5.1. **Ready.** A task is ready iff: status is `todo`, it is not a
     container, and all dependencies are `done`.

5.2. **Blocked.** A task is blocked iff: status is `todo` and at least
     one dependency is not `done`. Blocked is always derived (§1.7).
     `blockers(id)` returns the incomplete dependencies; with
     `chain`, the root-cause incomplete leaves beneath them.

5.3. **Ordering.** `ready()` and `next()` order ready tasks by:
     1. priority weight descending (`high`=2, `medium`=1, `low`=0);
     2. `created_seq` ascending (older first) as a deterministic
        tie-break.
     No other ordering influence is allowed — determinism §1.8.

5.4. **Progress.** `progress()` reports `total, done, in_progress,
     needs_revision, todo, percent`. `done` counts tasks whose
     *effective* status is done (containers included).

5.5. The scheduler never assigns work to an agent. It answers
     questions; agents ask.

## 6. Verification

6.1. **Evidence is typed.**

     - **Hard** — machine verifiable: test results, compilation,
       lint/static analysis, benchmarks, commit hashes. Produced by
       deterministic tooling.
     - **Soft** — asserted: LLM review, human approval, architecture
       review. Produced by judgment.

6.2. **Gates.** `verification_passed` is the claim "this task's
     acceptance criteria are met." The kernel checks the *structural*
     gates (§4.3). Whether the evidence actually justifies the claim is
     a policy question for the reviewer protocol (§11): hard evidence
     SHOULD be required for code-production tasks; soft evidence MAY
     suffice for design/research tasks.

6.3. **Failure loop.** An executor that cannot satisfy acceptance
     criteria emits `verification_failed` with a reason, then
     `task_retried` to continue. The graph never lies: a task is
     `done` only when verified, `needs_revision` only with a recorded
     reason.

## 7. Context Builder

7.1. **Purpose.** Agents receive *focused context*, never the whole
     project. The context builder composes the exact package a client
     needs to work on one task.

7.2. **Input.** A task id and the current graph.

7.3. **Output** (MUST contain, in this order):

     - the task: id, title, description, status, priority;
     - acceptance criteria;
     - dependencies with their statuses (done / in_progress / …);
     - blockers, if any, with root causes;
     - the task's evidence and notes;
     - files the task produces;
     - project progress summary;
     - child tasks, if it is a container.

     Two renderings: **markdown** (human/LLM reading) and **JSON**
     (machine parsing). Both MUST be derived from the same fold —
     no separate state.

7.4. The context builder MUST NOT include events or tasks unrelated to
     the target task beyond the progress summary.

## 8. Query Language

8.1. A read-only expression language over the graph. Filter form
     returns matching task ids; call form returns computed values.

8.2. **Grammar.** A safe subset of Python expressions:

     - constants (strings, numbers, booleans);
     - field access on the implicit task: `status`, `priority`,
       `blocked`, `container`, `evidence_count`, `files`, `notes`,
       `acceptance`, `depends_on`, `blocks`, `children`, `id`,
       `title`, `created_seq`;
     - comparisons: `==`, `!=`, `<`, `<=`, `>`, `>=`; priority
       compares as low < medium < high; strings compare with
       case-insensitive substring for `in` / `not in`;
     - boolean: `and`, `or`, `not`;
     - call form: registered functions — `blockers(id)`,
       `children(id)`, `deps(id)`, `parents(id)`, `evidence(id)`,
       `ready()`.

8.3. **Safety.** Expressions MUST be parsed with a real AST and walked
     — never `eval`'d. Attribute chains beyond the whitelist,
     subscripts, lambdas, and calls outside the registry are errors.
     The registry is per-graph and fixed at load.

8.4. **Errors.** Syntax or safety violations raise a query error with a
     message naming the construct; they never execute partially.

## 9. Planner Protocol (M2A)

9.1. **Role.** A planner decomposes a goal into a task graph. It is a
     *client*. It MUST NOT own, mutate, or write the graph. It has no
     handle to the log.

9.2. **Inputs** (immutable snapshot):

     - `goal` — the objective, free text;
     - `graph` — a snapshot of current tasks, statuses, dependencies
       (a context export, not a live handle);
     - `knowledge` — whatever the planner brings (docs, prior art,
       domain model);
     - `constraints` — policy: priority defaults, naming rules,
       max depth, max tasks, disallowed patterns.

9.3. **Output — the Proposal.** One structured object:

```json
{
  "proposal_id": "prop_8f3a...",
  "reason": "Decompose Renderer; Camera and UI are independent",
  "confidence": 0.92,
  "events": [
    {"op": "task_expanded", "task": "renderer", "children": [
      {"title": "Camera", "priority": "high"},
      {"title": "UI"}
    ]},
    {"op": "dependency_added", "task": "ui", "depends_on": "camera"}
  ]
}
```

     - `proposal_id`: unique per planner, for auditability;
     - `reason`: why this shape was chosen (audit trail);
     - `confidence`: planner's self-assessment, advisory only;
     - `events`: the proposed events, in dependency order.

     The planner proposes **events**, never graph state. It does not
     say "renderer should have children camera and ui"; it emits the
     events that make it so.

9.4. **Commit path.** The kernel processes a proposal as one unit:

```
proposal ──► validate envelope
           ──► fold events in isolation (any invalid event ⇒ reject whole proposal)
           ──► check id collisions with current project
           ──► append all events atomically (one lock acquisition)
           ──► replay / re-derive graph
           ──► return {proposal_id, committed: [stamped events]}
```

     Atomicity is total: either every event is committed or none is.
     A rejected proposal returns a structured error: which event,
     which guard, and why.

9.5. **Kernel-side enforcement** is the existing import path (§12.6):
     the proposal's `events` array is validated as a batch and appended
     under the write lock. There is no per-event partial commit for a
     proposal.

9.6. **Planner constraints.**

     - MUST NOT mutate the graph directly (no kernel mutation calls
       from planner code paths);
     - MUST NOT emit events referencing tasks it did not create or
       that do not exist in its snapshot;
     - SHOULD emit `task_expanded` for decomposition rather than flat
       lists (runtime evolution, §2.2);
     - MAY include `task_created`, `dependency_added`,
       `task_updated`, `task_expanded` only. Verification and
       execution events are the executor's domain (§10).

9.7. **Determinism of acceptance.** Given the same project state and
     the same proposal, the kernel's accept/reject decision is
     deterministic. Planner behavior is NOT kernel behavior.

## 10. Executor Protocol

10.1. **Role.** An executor works on exactly one task package: the
      context output (§7) for one task id. It produces artifacts and
      evidence.

10.2. **Contract.**

      - Works only on the assigned task (plus anything it expands via
        `task_expanded`, which becomes its responsibility);
      - on completion: attaches **hard** evidence for machine-
        verifiable claims, then proposes `verification_passed`;
      - on failure: proposes `verification_failed` with a reason, then
        (optionally) `task_retried` to continue;
      - may attach soft evidence for design decisions;
      - MUST NOT verify-pass a task whose acceptance criteria it did
        not satisfy, and MUST NOT verify-pass on behalf of another
        agent's task.

10.3. **Expansion is allowed.** An executor that discovers a task is
      too large may propose `task_expanded`; the parent then derives
      done from the children it works.

## 11. Reviewer Protocol

11.1. **Role.** A reviewer (human or LLM) judges whether acceptance
      criteria are met. Review is *soft* evidence (§6.1).

11.2. **Contract.**

      - reviews a task's acceptance criteria against its files,
        evidence, and history;
      - approve: attach soft evidence (`source: "review:<agent>"`) and
        propose `verification_passed` if the structural gates allow;
      - reject: attach soft evidence with the gap, propose
        `verification_failed` (and `task_retried`);
      - MUST NOT produce hard evidence; MUST NOT modify files outside
        the reviewed task's scope;
      - a human reviewer MAY use `force: true` to override the
        dependency gate — a machine reviewer MUST NOT.

## 12. Persistence

12.1. **Layout.** A project is a directory containing:

      - `events.log` — the append-only JSONL log (§3);
      - `events.lock` — lock file for cross-process write serialization
        (may be absent in read-only usage).

      No other files are kernel-owned. `project.graph.json` is
      explicitly NOT part of the format: the graph is derived.

12.2. **Append.** Writers acquire the lock, read the tail `seq`,
      stamp new events (`seq` = tail+1, `ts` = now, `v` = 1), append
      lines, flush. `seq` uniqueness is guaranteed by the lock — it is
      the kernel's cross-process ordering.

12.3. **Locking.** Writes MUST be serialized by (a) an in-process
      mutex and (b) an OS-level file lock on `events.lock`. Windows
      byte-range locks are per-handle: all I/O for one append happens
      through one handle.

12.4. **Replay.** The graph is rebuilt by folding the log. Replay is
      cheap and MUST be exact: same log, same graph.

12.5. **Crash recovery.** A torn final line (partial write during a
      crash) is skipped on load. Corruption anywhere else — invalid
      JSON, unknown op, failed guards — is a hard error.

12.6. **Import/Export.** Export produces a portable JSON list of events
      (the log). Import merges a batch exactly as a proposal (§9.4):
      isolated fold, collision check, atomic append, re-stamp of
      `seq`/`ts`/`v`.

12.7. **Undo.** Undo truncates the tail of the log and refolds. It is
      a human safety valve. Undo of more events than exist is an
      error.

12.8. **Migration.** The schema version `v` gates migration. v1 logs
      MUST always fold under any implementation. New event types are
      additive with a `v:2` stamp and a migration path (§3.4). A log
      with a *higher* version than the implementation knows is a hard
      error, never a silent partial read.

---

## Appendix A — Versioning & Freeze Policy

- **The kernel is frozen at v1.** No new features in the core without
  a spec change and a version bump. This is deliberate: like Git's
  object model, stability is the product.
- **Kernel additions** (new ops, API methods, query functions) require:
  spec amendment → schema `v` bump or additive op → migration → tests.
- **Plugins** (planners, executors, reviewers, MCP servers, UIs,
  context renderers) are unrestricted: they are clients of the kernel
  API and the protocols above. Everything new lives there.
- **The user experience is NOT frozen.** CLI commands, planner prompts,
  MCP interfaces, and visualizations may evolve freely. Only the
  deterministic semantics — the invariants (I1–I7) and the event
  schema — are stable. Freezing the contract is good; freezing the UX
  is not.
- The official API surface and event schema in `docs/API.md` and
  `docs/EVENTS.md` are normative extracts of this spec.

## Appendix B — Hypergraph Roadmap (v2, not committed)

v1 is a DAG because it is simple and sufficient. The event envelope is
already shaped for the jump:

- **One artifact, many goals.** Today: a shared artifact is one task
  that many tasks depend on (fan-out). v2: first-class artifact nodes
  with producers/consumers.
- **One task, many outputs.** Today: `files` is a list. v2: file
  entities with typed roles.
- **One verification, many tasks.** Today: `verification_passed` names
  one id. v2: multi-target verification events.
- **Many-to-many dependencies.** Today: DAG only. v2: hyperedges
  (a group of tasks jointly satisfying a goal).

None of these require changing v1 events. They are new ops, stamped
`v:2`, with a fold that still accepts v1.

## Appendix C — What "Done" Means for This Spec

This specification is the contract when all three hold:

1. Every normative claim here has a test — either a unit test in the
   reference implementation or a compliance test in
   `tests/compliance/` that maps one-to-one to the
   invariants I1–I7 and the adversarial cases (§3.3, §12.5):
   malformed proposals, fuzzed event streams, torn-log recovery,
   cross-environment replay identity, randomized scheduler
   determinism. A claim without a test is a wish, not a contract.
2. A fresh implementation can be built from this document alone.
3. The kernel survives its own stress test: concurrent writers,
   100k-event replays, deep expansion, adversarial logs.
