# Official Kernel API (v1)

> Normative extract of `docs/SPEC.md` (Task Model, State Machine,
> Persistence). The spec is the contract; this file is the quick
> reference.

`forge.kernel.Kernel` is the ONLY way anything may read or modify a
project. Planners, executors, verifiers, humans, and MCP servers are all
clients of this same surface. There is no back door: agents propose
events, the kernel validates, persists, and applies them.

    propose -> validate -> append to log -> apply to graph -> done

The LLM is never trusted with the graph; it is trusted only to propose.
Everything here is deterministic Python with zero dependencies.

## Lifecycle

    k = Kernel("path/to/project")   # creates if missing, replays log

## Mutations (validate -> append -> apply)

| method | event | notes |
|--------|-------|-------|
| `create_task(title, description="", acceptance=(), files=(), notes=(), id=None, priority="medium")` | task_created | id defaults to slug, deduped with `-2` |
| `update_task(task_id, **changes)` | task_updated | title/description/acceptance/files/priority |
| `expand(task_id, children)` | task_expanded | children: `{title, description, acceptance, files, priority}` |
| `add_dependency(task, depends_on)` | dependency_added | cycle-checked |
| `remove_dependency(task, depends_on)` | dependency_removed | |
| `start(task_id)` | task_started | todo -> in_progress |
| `verify_fail(task_id, reason)` | verification_failed | -> needs_revision |
| `retry(task_id)` | task_retried | -> in_progress |
| `verify_pass(task_id, force=False)` | verification_passed | -> done (deps gate; force bypasses it) |
| `reopen(task_id)` | task_reopened | done -> in_progress |
| `add_evidence(task_id, kind, source, detail="")` | evidence_added | kind: hard/soft |
| `add_note(task_id, text)` | note_added | |
| `delete(task_id)` | task_deleted | no dependents/children |
| `undo(n=1)` | — | truncate log, refold graph |
| `import_events(events)` | — | merge an export; id collisions rejected |
| `replay()` | — | refold from disk |

Every mutation returns the stamped event (with `seq`/`ts`/`v`).

## Reads (never mutate)

| method | returns |
|--------|---------|
| `task(task_id)` | TaskNode |
| `context(task_id, fmt="markdown"\|"json")` | the focused package an LLM client receives |
| `ready()` | ids ready to work (priority order) |
| `next()` | single next id or None |
| `blockers(task_id, chain=False)` | incomplete deps (or root-cause paths) |
| `progress()` | {total, done, in_progress, needs_revision, todo, percent} |
| `history(task_id)` | every event touching the task, oldest first |
| `inspect(task_id)` | full dossier: status, completion, children, produces, evidence, history |
| `query(expr)` | query-language results (see below) |
| `export_events()` | portable JSON snapshot (event log) |
| `to_export_json()` | same, pretty-printed string |

## Query language

A safe subset of Python expressions (parsed with `ast`, never `eval`).
Attribute access, subscripts, lambdas, and arbitrary calls are rejected.

Filter form (returns matching task ids):

    status == needs_revision and priority == high
    priority > medium                  # low < medium < high
    "snake" in title                   # case-insensitive substring
    evidence_count >= 2 and not blocked
    id in children(renderer)

Call form (returns the value):

    blockers(renderer)     incomplete deps
    children(renderer)     / deps(renderer)
    parents(renderer)      tasks waiting on it
    evidence(renderer)     evidence lines
    ready()                ready task ids

Fields: `id, title, status (effective), priority, blocked, container,
evidence_count, files, notes, acceptance, depends_on, blocks, created_seq`.
Bare words evaluate to strings.

## Concurrency contract

- Writes are serialized: an in-process threading lock plus an OS file
  lock (`events.lock`) covering all processes.
- `seq` assignment happens under the lock — unique across agents.
- Readers see a consistent snapshot; a process that wants fresh state
  calls `replay()` (or reopens the Kernel).
- Any number of planner/executor processes can emit events concurrently;
  validation happens against the writer's snapshot, so two agents
  proposing the same task id are resolved by the kernel (slug dedupe)
  or rejected (explicit duplicate id).

## Versioning

This API surface is v1 and stable. The event schema is frozen in
docs/EVENTS.md. New capabilities are additive; breaking changes bump
the schema version with a migration.

---

# Forge SDK (v1) — the client surface

`forge.ForgeClient` is the ONE interface every client is allowed to
touch: humans, planner agents, executors, reviewers, MCP servers. It is
a thin facade over the official Kernel API — no graph logic, no replay
logic, no scheduler logic lives in it. If a client needs something the
SDK does not offer, that is a missing SDK method (or kernel API), not a
reason to import kernel internals.

    from forge import ForgeClient, validate_proposal, slugify

    forge = ForgeClient("path/to/project")

| method | purpose |
|--------|---------|
| `next()` | next ready task as a snapshot `{id, title, description, status, priority}` or None |
| `context(task_id)` | the standard context contract package as YAML (below) |
| `propose(proposal)` | validate the proposal envelope (§9), then commit events atomically; returns `{proposal_id, committed, tasks}` |
| `start(task_id)` | claim a task (todo -> in_progress; blocks dependents) |
| `attach_evidence(task_id, kind, source, detail="")` | hard (tests/build/benchmark) or soft (review) evidence |
| `verify(task_id)` | run the verifier gate (I6); on pass the task is done — the client never decides this |
| `verify_fail(task_id, reason)` | reviewer verdict -> needs_revision |
| `query(expr)` | query-language results |
| `progress()` | `{total, done, in_progress, needs_revision, todo, percent}` |
| `replay()` | refold from disk |

The executor flow is five calls:

    task = forge.next()
    ctx  = forge.context(task["id"])     # the ~500-token contract
    result = llm(ctx)                    # code, tests
    forge.attach_evidence(task["id"], "hard", "unittest", detail)
    forge.verify(task["id"])             # Forge decides "done", not the LLM

The planner flow:

    proposal = planner(goal)             # {proposal_id, reason, confidence, events}
    validate_proposal(proposal)          # envelope only; the kernel enforces the rest
    forge.propose(proposal)              # atomic commit or whole rejection

## Context contract package

`forge context <task>` renders exactly this shape (YAML, ~500 tokens):

    Task: camera — Implement Camera
    Description: Viewport
    Acceptance:
      - smooth follow
      - zoom
      - tests
    Dependencies:
      - renderer ✓ (done)
    Knowledge:
      - camera API exists upstream
    Relevant Files:
      - camera.py
      - renderer.py
    Evidence:
      - [hard] unittest — renderer benchmark passed
    Constraints:
      - do not modify renderer API

Conventions: `Knowledge` = notes; `Constraints` = notes prefixed
`constraint:`; `Dependencies` carry a ✓ (done) / ○ (todo) status marker.
Agents read this package, never the graph. The canonical dict is
`forge.context_package(graph, task_id)`; `forge.slugify` is the public
id-derivation rule (child ids must be predicted by the planner).
