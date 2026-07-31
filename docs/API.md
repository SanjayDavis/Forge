# Official Kernel API (v1)

> Normative extract of `docs/SPEC.md` (Task Model, State Machine,
> Persistence). The spec is the contract; this file is the quick
> reference.

`pkernel.kernel.Kernel` is the ONLY way anything may read or modify a
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
