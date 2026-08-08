# Proof #5 — swarm: replay

Cross-checkable against `events.log` (612 events, contiguous `seq` 1..612) and
`demo/_replay_facts.md` (derived). Every milestone below cites `seq` numbers.

## Goal

Demonstrate that Forge's shared state stays correct and inspectable at
100+ tasks *and* four concurrent agents (claims C4 "long projects", C5
"multi-agent"). Four independent OS processes drive one project directory
through the public Kernel SDK; nothing but the shared event log arbitrates
them.

## Outcome

Same numbers as `metrics.json` (all log-derived):

- tasks: **114** (`task_created` count) · events: **612** · passes: **114** ·
  failures: **3** · retries: **0** (`task_retried` count — the three failures
  were fixed and re-verified inside the same claim, no retry op, per the
  Proof Standard)
- duration: **1 min** wall (first ts `11:43:35Z` seq 1 → last ts `11:44:37Z`
  seq 612)
- max_ready_queue: **28** (peaked at seq 408, `verification_passed`
  `contract-validate`) — a graph-parallelism property of the 114-task DAG,
  close to the pre-flight prediction of 26
- status: **completed** — every one of the 114 tasks ends `done`

## Timeline

### Proposal → Planning (seq 1..267)

- seq 1..114 — the planner's 114 `task_created` events land (proposal
  `prop_swarm_001`, 9 subsystems, 4 owners). First: `auth-claims` (seq 1);
  last: `int-verify-matrix` (seq 114).
- seq 115..267 — the planner closes the DAG: 153 `dependency_added` events.
  All edges are in place *before* any `task_started` — the run begins from a
  fully-specified graph, so the frontier is a property of the DAG, not of
  discovery. Last edge at seq 267.

### Execution (seq 268..612) — 4 agents, one shared log

- seq 268 — first `task_started` (`swarm-skeleton`). All four agents ramp
  concurrently on the shared ready-set.
- seq 269 — first `verification_passed` (`swarm-skeleton`), immediately
  followed by its `evidence_added` (seq 270). Every pass in the log is
  matched by an evidence write (S6: 114/114).
- Ownership split (from `subsystems.json`): agent-a 42 tasks (contract,
  gateway), agent-b 30 (storage, auth), agent-c 25 (worker, cli), agent-d 17
  (observe, integration) — 42+30+25+17 = 114, no overlap (S4: exactly one
  `task_started` per id).
- Probe bootstrap (engineering finding #2, see README §8): before the first
  pytest probe can run, the harness prefetches the `swarm` package skeleton
  (68 files, `probe_bootstrap` in the manifest) into the worktree. The DAG
  orders *tasks*, not *import closures* — a test file can only import
  `swarm.storage.jobs` once the package layout exists, and the dependency
  graph does not model that. The prefetch is idempotent and the owning tasks
  still write every file themselves at claim time, so no claim is bypassed.
- seq 368 — **first genuine failure cycle** `storage-repo-jobs`: the review
  probe `tests/test_review_atomicity.py` asserts `JobRepo.claim()` is atomic
  (`BEGIN IMMEDIATE`) — the injected v1 returns the same job to two
  connections ("double-claim: both connections received the same job (j1)").
  Failure recorded with the real reason, canonical (atomic) implementation
  restored, probe re-run → `verification_passed` at seq 369.
- seq 408 — `max_ready_queue` peaks at **28** as `contract-validate` passes
  and the gateway fan-out wave becomes simultaneously executable.
- seq 423 — **second genuine failure cycle** `worker-exec`: the worker's v1
  dispatches the raw payload instead of decoding the JSON-string `payload`
  column written by storage (`test_executor_decodes_json_string_payload`:
  expected `done`, got `failed`). Cross-subsystem seam failure — the 
  contract between storage's write format and worker's read format was
  exercised by the integration review probe. Pass at seq 424.
- seq 492 — **third genuine failure cycle** `contract-tests-codec`: the
  codec test itself asserted the wrong contract ("lenient mode must reject
  unknown fields") — the *test* was wrong, not the code (the lenient
  contract deliberately ignores unknown fields). Reviewer-agent corrected
  the assertion; pass at seq 493. Same shape as the CHIP-8 "wrong test"
  lesson — verification being wrong is a real failure class.
- seq 606..611 — final integration passes (`int-repro` seq 606,
  `int-verify-matrix` seq 609, `gw-docs` seq 611); the log closes with the
  last `evidence_added` at seq 612.

### Verification (whole-log)

- S1..S10 invariant run over the finished bundle — see
  `check_invariants.py` and `screenshots/03-invariants.png`:
  S1 acyclic/complete DAG (114/114 covered), S2 no orphans, S3 partial order
  holds (0 seq and 0 ts violations), S4 unique ownership (0 double-starts),
  S5 contiguous seq 1..612, S6 evidence 114/114 + 3 fail cycles, S7
  double-derive byte-identical + shipped-match, S8 replayability (this
  file), S9 context assembly at ~50/~100/full via the public SDK, S10
  line-integrity (612 lines, SDK export == 612).
- 197-test suite in the swarm-built worktree: `197 passed` (exit 0).
- `tools/proof-check.py examples/swarm` → **CONFORMING**.

## Turning points

1. **seq 115 — planning closes before execution.** All 153 edges precede the
   first `task_started`; the run's parallelism is measurable up front
   (pre-flight predicted MaxQ 26, measured 28).
2. **seq 268 — the four agents go live on one shared log.** First start,
   first pass (269), first evidence (270); from here the store's
   cross-process lock arbitrates every claim.
3. **seq 368 — first genuine failure: storage atomicity.** The review probe
   proves the injected non-atomic `claim()` really is unsafe — a real
   defect caught by a real test, then fixed and re-verified (369).
4. **seq 423 — cross-subsystem seam failure: worker payload decode.** The
   storage→worker format contract is enforced by an integration probe, not
   by the DAG — exactly the class of bug multi-agent autonomy is supposed
   to surface.
5. **seq 492 — verification itself was wrong.** The codec test asserted
   strict rejection; the lenient contract is the documented behavior. The
   test, not the code, was corrected — preserving the failure as evidence.

## Artifacts cross-check

- `events.log` — raw, unmodified (md5 `7f2b2b23e9fb2900c56d7a23aa941501`),
  copied from `.proof-work/events.log` of the verified run.
- `graph.json` / `metrics.json` — byte-identical double-derive (S7).
- `graph.png` — 114 nodes, depth 11, status + 9-subsystem coloring.
- `demo.mp4` — real run footage, ≤ 120 s.
- `screenshots/` — real captures of the worktree test run, the S-invariant
  verdict, and the conformance check.
