# Event Schema v1 (FROZEN)

The event log is the single source of truth. The graph is a projection:
fold the log, oldest to newest. This document freezes the schema — like
Git's object model, it should not change in breaking ways. Any new event
type is a major version bump (event `v` field) with a migration path.

## Format

One JSON object per line in `events.log` (JSONL). Every event carries:

| field | type  | meaning                                          |
|-------|-------|--------------------------------------------------|
| `v`   | int   | schema version (currently `1`; absent = 1)       |
| `seq` | int   | global sequence number, unique, assigned by Store|
| `ts`  | str   | UTC ISO-8601 timestamp                           |
| `op`  | str   | one of the 14 ops below                          |
| ...   |       | op-specific fields                               |

`seq` is assigned under the file lock at append time, so it is unique
across all processes and agents. A torn final line (crash during append)
is skipped on load; corruption anywhere else raises.

## Operations

### task_created
`id` (str), `title` (str, non-empty), `description` (str), `acceptance`
(list[str]), `files` (list[str]), `notes` (list[str]), `priority`
("low"|"medium"|"high", default "medium"). Ids must be whitespace-free
and unique.

### task_updated
`id`, plus any of: `title`, `description`, `acceptance`, `files`,
`priority`. At least one field must change. List fields REPLACE the list.

### task_expanded
`task` (str, the container), `children` (list of child dicts, each:
`id`, `title`, `description`, `acceptance`, `files`, `priority`).
Makes the parent a container: it completes when all children complete.
Child ids must not pre-exist. Children may themselves be expanded later.

### dependency_added / dependency_removed
`task` (str), `depends_on` (str). No self-dependencies, no cycles
(validated at proposal time). `task` cannot complete until `depends_on`
is done.

### task_started
`id`. Only `todo` tasks start.

### verification_failed
`id`, `reason` (str, required). Only `in_progress` /
`needs_revision` tasks. Sets status to `needs_revision` and records
`last_failure` with a retry budget.

### task_retried
`id`. Only `needs_revision` tasks. Returns to `in_progress`.

### verification_passed
`id`, optional `force` (bool). Only `in_progress` / `needs_revision`
tasks. Containers reject direct verification (they complete when their
children do). Normal tasks additionally require all dependencies done.
`force` bypasses only the dependency gate, never the status gate.

### evidence_added
`id`, `kind` ("hard"|"soft"), `source` (str), `detail` (str).
Hard = machine evidence (tests, compile, benchmark, static analysis).
Soft = asserted (LLM review, human approval, architecture review).

### note_added
`id`, `text` (str).

### task_deleted
`id`. Rejected if the task has dependents or children.

### task_reopened
`id`. Only `done` tasks. Returns to `in_progress`.

## Invariants (enforced at validation)

1. Every event references existing tasks (except `task_created` /
   `task_expanded`'s own children).
2. Unknown ops, missing fields, and wrong field types are rejected at
   load — a corrupt log fails loudly, never silently.
3. `seq` is monotonic; the graph state is a pure fold, so replay is
   deterministic and undo = truncate + refold.
4. Blocked/Ready/completion are DERIVED from dependencies, never stored.
   Effective status of a container = "done" iff all children are done.

## Adding an event type

Never mutate this list in place for a running project. Add the op with
a `v: 2` bump, provide a `v1 -> v2` fold migration, and document both.
The kernel must always be able to replay any historical log.
