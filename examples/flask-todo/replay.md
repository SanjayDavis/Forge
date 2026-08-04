# Replay — flask-todo

**Goal.** Build a minimal Flask task manager — add, complete, delete tasks —
entirely planned, executed, and verified through Forge, as the first demonstration
proof for the Proof of Forge corpus.

**Outcome.** 8 tasks · 46 events · 9 verification passes · 1 failure · 1 retry ·
5 minutes wall-clock. Failure rate 10% (1 of 10 verification attempts). All tasks
completed; status: `completed`.

---

## Timeline

### Proposal

A proposal (`proposal.json`, id `prop_flask_001`, confidence 0.9) decomposed the
project into eight tasks: app factory → schema → models → routes → templates →
stylesheet → tests → README.

### Planning (seq 1–15)

All eight tasks created (seq 1–8). Dependency edges added (seq 9–15), forming a
single chain:

```
app-factory → db-schema → models → routes → templates → static-css
                                                 ↘ tests → readme
```

### Execution and verification, phase 1 (seq 16–26)

| seq | event |
|-----|-------|
| 16–18 | `app-factory` started, evidence added (app factory + `/health` 200), verification passed |
| 19–21 | `db-schema` started, idempotent schema verified, passed |
| 22–24 | `models` started, CRUD verified, passed |
| 25–26 | `routes` started, first evidence round added (add→302, done→302, unknown→404) |

### Turning point 1 — verification failure (seq 27)

`routes` **failed verification** (seq 27): completing an already-done task returned
404. `mark_done` returned `False` for both "task not found" and "task already done",
so the route could not distinguish them — completion was not idempotent.

How it was resolved:

- `models` reopened (seq 28) and reworked: `mark_done` now returns a tri-state
  (`ok` / `already` / `missing`) instead of a bool (seq 29, verified seq 30).
- `routes` retried (seq 31), re-verified against the new semantics (seq 32–33):
  done-twice now redirects, unknown ids still 404. Passed.

The acceptance criteria caught a real design ambiguity that a test suite written
against the original API would have encoded, not exposed.

### Execution and verification, phase 2 (seq 34–46)

| seq | event |
|-----|-------|
| 35 | **Plan amended mid-run:** `tests` gains a dependency on `templates` — the planner expanded the graph during execution, not just upfront |
| 36–38 | `templates` verified (render + empty state) |
| 39–41 | `static-css` verified (stylesheet served, strikethrough rule present) |
| 42–43 | `tests` verified: 7/7 unittest pass |
| 44–46 | `readme` verified (setup/run/test documented) |

### Completion (seq 46)

All 8 tasks done. Project state: `completed`.

---

## Turning points

1. **Idempotency bug (seq 27–33).** The only failure of the run — and the most
   valuable event in it. Verification forced a semantic decision (missing vs
   already-done) that the original design had silently conflated.
2. **Mid-run graph amendment (seq 35).** The `tests → templates` edge was added
   during execution, after `tests` had already started. The dependency graph is a
   living artifact, not a fixed plan.
