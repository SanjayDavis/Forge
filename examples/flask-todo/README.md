# Proof #1 — Flask Todo

## 1. What was built

A minimal Flask task manager — add, complete, and delete tasks, backed by SQLite —
built end-to-end by Forge: every task was planned, executed, verified, and recorded
in the event log that ships with this directory.

## 2. Why this proof exists

This is the first entry in the Proof of Forge corpus and the proof that exercised the
Proof Standard into existence. It demonstrates:

- **C6 — "It's just a fancy todo list."** The run has real development history: one
  genuine verification failure, a reopened task, a retry, and a plan amended mid-run
  — all visible in `replay.md` and verifiable against `events.log`.
- **C7 — "It can't handle structured complexity."** A clean subsystem DAG (core →
  web → qa → docs) with a single root and a depth of 6; see `graph.png`.

It is deliberately *not* claiming C1/C2/C3: it is a small Python web app. Those
claims belong to later proofs.

## 3. Final architecture

```
core    app-factory (create_app, config, /health)
core    db-schema   (idempotent SQLite schema)
core    models      (data-access layer: add/get_all/mark_done/delete)
web     routes      (/, /add, /done/<id>, /delete/<id>)
web     templates   (base.html + index.html)
web     static-css  (style.css)
qa      tests       (7 unittest cases over the Flask test client)
docs    readme      (setup/run/test instructions)
```

Dependencies: `app-factory → db-schema → models → routes → templates → static-css`,
with `tests` depending on `routes` and `templates`, and `readme` on `tests`.

## 4. Commands

```
pip install flask
flask --app app init-db          # initialize the SQLite schema (first run only)
python run.py                    # http://127.0.0.1:5000
python -m unittest discover -s tests
```

All 7 tests pass. The `init-db` step is required on a fresh checkout — the schema is
deliberately not auto-created at import time; it is created explicitly (see
Behavior notes).

## 5. Reproduce

- Forge version: `0.1.0a1` (from `forge/__init__.py`)
- Planner / executor / verifier: **not recorded** for this run
- Seed: `proposal.json` (`prop_flask_001`)
- Raw history: `events.log` (46 events, contiguous seq 1–46)

Derived artifacts regenerate from the log alone:

```
python tools/proof-derive.py examples/flask-todo --forge-version 0.1.0a1
python tools/proof-render-graph.py examples/flask-todo
```

(`graph.json` subsystem labels and `metrics.json` claims are human enrichment
applied after derivation; all counts and edges are log-derived.)

## 6. Artifact index

| Artifact | What it is |
|----------|------------|
| `events.log` | raw Forge history — the source of truth |
| `proposal.json` | the seed proposal (8 tasks + dependencies) |
| `graph.json` | final dependency graph, machine-readable |
| `graph.png` | final dependency graph, rendered |
| `replay.md` | narrative timeline with seq citations |
| `metrics.json` | comparable metrics per the Proof Standard §5 |
| `screenshots/` | runtime and test evidence |
| `demo.mp4` | 2-minute run-through |

## 7. Behavior notes

- Completing an already-done task is **idempotent** (redirects, does not 404) —
  the fix that came out of the run's only verification failure.
- Unknown task ids return 404.
- The schema is idempotent; `init_db()` can be called repeatedly.
- The schema is **not** auto-created at import time — a fresh checkout needs
  `flask --app app init-db` once. This surfaced during the backfill: `POST /add`
  returns 500 (`no such table: tasks`) on a clean checkout without it, so the
  original run's README (which omitted the step) was corrected as part of this
  proof.
- `events.log` seq 35: the `tests → templates` dependency was added *during*
  execution, after `tests` had already started — the graph evolved mid-run.

## 8. Lessons learned

- **Verification catches what tests encode.** The routes failure (seq 27) was a
  semantic conflation — "not found" vs "already done" — that a test suite written
  against the original API would have *encoded* as the expected behavior. Forge's
  acceptance-criteria verification acts as a second pair of eyes *before* tests are
  written, and it changed the API design (bool → tri-state return).
- **The plan is a living artifact.** The mid-run edge addition (seq 35) shows the
  dependency graph is updated as understanding grows, not frozen at proposal time.
- **Small proofs still set the format.** This run is only 8 tasks, but it
  established the artifact bundle, the metrics, and the honest-failure tone every
  later proof follows.
