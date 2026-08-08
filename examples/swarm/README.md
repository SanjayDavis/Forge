# Proof #5 — `swarm`: a mini multi-service system built by 4 concurrent agents

Status: **completed — conforming** (`proof-check` → CONFORMING).
4 OS processes · 114 tasks · 612 events · 3 genuine failures · 1 minute.

## 1. What was built

`swarm` is a miniature multi-service system (a job-processing platform):
contract, storage, auth, gateway, worker, cli and observe subsystems, 114
tasks, implemented by **four independent OS processes (agents)** racing on one
Forge project through the public `Kernel` SDK. All runtime code is
stdlib-only (sqlite3, hmac, http.server, argparse, logging).

## 2. Why this proof exists

Proof #5 claims (PHASE2_DESIGN.md): **C4** ("can't handle long projects") and
**C5** ("only works with one agent") — answered together by a single
100+-task, 4-process run sharing one event log. The same log also exercises
C1 (cross-process integrity at scale) and C3 (dependency partial-order across
processes) quantitatively, though the proof formally claims C4 + C5.

## 3. Final architecture

```
4 OS processes ──public Kernel SDK──▶ one shared Forge project
agent-a: foundation + contract + gateway   (42 tasks)
agent-b: storage + auth                    (30 tasks)
agent-c: worker + cli                      (25 tasks)
agent-d: observe + integration             (17 tasks)
```

Ownership map: `subsystems.json`. Task graph: `proposal.json` (114 tasks,
153 dependency edges, 9 subsystems, DAG depth 11). Harness:
`run_agents.py` (orchestrator + workers).

## 4. Commands

```bash
python examples/swarm/run.py --smoke      # harness self-test, ~1s
python examples/swarm/run.py --check      # S1..S10 invariant checker
python examples/swarm/run.py --derive     # re-derive graph/metrics from log

# clean-checkout evidence capture (materialises a fresh tree, runs it,
# records real output into demo/record/ + screenshots/):
PYTHON=python bash examples/swarm/demo/record.sh
```

The full 4-agent orchestrated run (what produced `events.log`) is re-runnable
via `python examples/swarm/run_agents.py --workdir <dir>` — it is not part of
the default commands because the persisted run is the source of truth for
this proof bundle.

## 5. Reproduce

1. `python examples/swarm/run.py --check` → S1..S10 all pass (VERDICT PASS).
2. `python examples/swarm/demo/record.sh` → fresh materialisation, demo run,
   197-test suite, S-invariants, conformance — all real captures.
3. `python tools/proof-check.py examples/swarm` → **CONFORMING**.
4. Clean-clone checkouts: `run.py` and `record.sh` work from a fresh clone
   given a Python env with `pytest` (+ matplotlib/networkx for renders, same
   env as the proof tooling); nothing references `.proof-work/` (the
   execution's internal dir is only the historical run's scratch).

## 6. Measured results (all from `events.log`)

| Metric | Value |
|--------|-------|
| tasks 🅰 114 (9 subsystems, 4 owners) | events 612 (contiguous seq 1..612) |
| verification passes | 114 |
| verification failures | 3 (all genuine, see §9) |
| retries | 0 (failures fixed + re-verified inside the same claim) |
| max_ready_queue | **28** (at seq 408, `contract-validate` passed) — pre-flight predicted 26 |
| wall-clock duration | **1 min** (first ts 11:43:35Z → last ts 11:44:37Z) |
| final status | completed — 114/114 done |
| worktree test suite | **197 passed** (exit 0, measured) |
| S1..S10 invariants | all pass (see `screenshots/03-invariants.png`) |

## 7. Artifact index

| Artifact | Path | Status |
|---|---|---|
| Proposal (114 tasks, 153 edges) | `proposal.json` | committed |
| Ownership sidecar (4 agents) | `subsystems.json` | committed |
| DAG pre-flight gate | `preflight_dag.py` | PASSED |
| Harness (orchestrator + workers) | `run_agents.py` | smoke PASSED |
| Entry point (`--check --derive --smoke`) | `run.py` | PASSED |
| S1..S10 invariant checker | `check_invariants.py` | PASS (exit 0) |
| Event log (source of truth) | `events.log` | 612 events, md5 `7f2b2b23e9fb2900c56d7a23aa941501` |
| Graph (114 nodes) | `graph.json` + `graph.png` | derived, byte-stable |
| Replay | `replay.md` | 30 seq-citations, 4 milestones |
| Metrics | `metrics.json` | derived, byte-stable |
| Screenshots | `screenshots/` (4 PNGs) | real captures |
| Demo video | `demo.mp4` | ≤ 120 s, real run |

All derived artifacts regenerate byte-identically from `events.log` alone
(S7 double-derive, verified by `check_invariants.py`).

## 8. Two genuine engineering findings

1. **MSYS `/c/...` path behavior on Windows.** The run's worker processes
   spawn OS processes with paths passed through the shell. Under git-bash,
   an MSYS-style path (`/c/Users/...` or `/tmp/...`) looks absolute to bash
   but is *opaque* to native Windows Python: `Path("/c/Users/...")` resolves
   to a drive-relative `\c\Users\...` on the *current* drive, so config,
   logs and lock files silently land in the wrong place (or the wrong
   drive). Rule adopted: harness/evidence invocations always convert paths
   with `cygpath -w` (or keep them native `C:/...`) before handing them to
   a native interpreter; MSYS-form paths only survive inside bash itself.
   Symptom observed in the actual run: `events.log` opened by alias
   `/tmp/...` would be created as `\tmp\...` on the worktree drive.
2. **DAG ordering vs. import-closure/probe bootstrap.** The DAG orders
   *tasks*, not *import closures*: an executor test for `worker.decode`
   imports `swarm.storage.jobs`, but nothing in the dependency graph models
   the package-layout requirement. In the real run the first pytest probes
   raced ahead of the foundation tasks that create `swarm/`'s `__init__.py`
   — collection failed against an absent package. The fix (in the verified
   run): the harness performs an idempotent `probe_bootstrap` (68 files) of
   the package skeleton into the worktree before the first probe; the owning
   tasks still write every file themselves at claim time (no verified file
   is pre-written), so the bootstrap only guarantees *importability*, and
   the DAG's verification semantics are untouched. It is a probe-environment
   concern, correctly NOT a DAG edge; the DAG's order claims (S3) were
   proven unaffected by the invariant checker.

## 9. The three genuine `verification_failed` events (NOT normalized away)

Preserved verbatim in `events.log`; each is a real red→green cycle inside a
single claim loop (no `task_retried` op; the executor re-verifies the same
claim after fixing the code — matches the corpus convention):

| seq | task | what the probe really caught |
|-----|------|------------------------------|
| 368→369 | `storage-repo-jobs` | `JobRepo.claim()` on the seeded v1 is **not atomic**: two connections received the same job (`double-claim: both connections received the same job (j1)`). Review probe `tests/test_review_atomicity.py`; canonical (atomic, `BEGIN IMMEDIATE`) restored → pass 369. |
| 423→424 | `worker-exec` | The worker dispatched the raw payload instead of **decoding the JSON-string `payload` column** written by storage (`test_executor_decodes_json_string_payload`: expected `done`, got `failed`). Cross-subsystem seam violation — exactly the bug class multi-agent autonomy is supposed to surface. |
| 492→493 | `contract-tests-codec` | The *probe itself* was wrong: it asserted lenient mode **rejects** unknown fields, but the documented contract ignores them. Verification was wrong, not the code; the reviewer corrected the test assertion and re-passed. Same shape as the CHIP-8 "wrong test" lesson. |

These are the proof that verification failures are real events, not
placeholders: each has its `evidence_added` after the pass, and S6
(`missing_evidence=0`, `fail_cycles=3`) locks them into the record.

## 10. Behavior notes

- Workers `Kernel.replay()` before every `ready()` snapshot — cross-process
  readiness visibility reloaded from the shared store; a claim race backs
  off and re-polls (`_claim`, MAX_RETRIES).
- Evidence kind is `soft` (schema: `hard`/`soft` only).
- `demo_drain.py` is **not idempotent across db reuse**: the demo user is
  inserted unconditionally, so a second run against the same `.db` fails the
  UNIQUE constraint (`duplicate user id: demo-user`). Demo runs always use a
  fresh session db (see `demo/record.sh`).

## 11. Lessons learned

(replay.md + check_invariants.py are the living record; here the durable
ones)

- `Kernel.ready()` reflects an in-memory graph loaded at construction; a
  multi-process worker MUST `replay()` before each poll or it never sees
  other agents' commits (found by the smoke test).
- Spawned workers re-import the harness module: configuration must travel
  via env vars (`SWARM_SUBSYSTEMS`, `SWARM_SMOKE_TREE`), not globals.
- Priority enum is `low|medium|high`; evidence kinds are `hard|soft`.
- MSYS path opacity (§8.1) applies to *every* cross-tool invocation on this
  repo, not just swarm — see Proof #4's cargo-line lesson for the sibling
  Windows toolchain trap.