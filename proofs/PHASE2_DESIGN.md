# PHASE2_DESIGN.md — Proof #5: 100+ task Multi-Agent Stress Proof (C4, C5)

**Status:** design (not yet executed)
**Claims:** C4 ("Can't handle long projects"), C5 ("Only works with one agent")
**Next release gate:** `0.1.0a4` (see `ROAD_TO_1.0.md`: "Does execution scale?")

The primary question this proof answers is **not** "can N agents each finish a
backend of tasks." It is:

> Does Forge remain a **reliable, correct, and inspectable source of truth** as
> the project grows past 100 tasks *and* agents work concurrently on the same
> state — or does coherence break (orphans, double-claims, lost events,
> corrupted graphs) exactly when you need it?

This document is the blueprint for that proof. It commits only to the **public
SDK/CLI** and the **standard proof bundle** (see `proofs/PROOF_SPEC.md`). **No
kernel and no public-API change** is permitted — the kernel is frozen at SPEC
v1; any discovery of a kernel defect during the run is recorded as a finding
and surfaced for a follow-up, not patched into this proof.

---

## 0. Why this proof is distinct — and why the executor is *not* touched

Phase 1 closed the language question (C1–C3) with C++ and Rust datapoints. The
Forge executor is deliberately kept serial/naive (see the proof workbench
policy: change it only when ≥2 proofs show the *same* limitation). Proof #5
does **not** make the executor smarter. Instead it launches **N independent
agent processes**, each driving the *same* Forge project directory through the
public SDK/CLI, and relies on Forge's shared state to arbitrate their work. This
tests the state model, not the executor.

Two properties of the state model are already documented in `forge/store.py`
and are exactly the claims under test:

- *"every write (append/undo) takes an OS file lock, so any number of
  processes can operate on the same project; sequence numbers are unique
  across processes"* — the store uses `msvcrt` on Windows / `fcntl` elsewhere,
  a per-process thread lock, a dedicated `events.lock` file, partial-line
  repair after a crash, and symlink refusal.
- Sequence numbers and graph topology are **derived**, not stored twice:
  `graph.json` / `metrics.json` regenerate from `events.log` alone
  (`tools/proof-derive.py`), which is what makes "replayability at scale" a
  testable property rather than a claim.

Proof #5 is the first orchestrated multi-process stress of those invariants.

---

## 1. Objective & success criteria

Demonstrate, with generated + verified evidence, that the shared Forge state
stays **correct and inspectable** as scope and concurrency both rise. Concretely,
the run must end with **all** of the following true (each is a checkpoint in §5):

| # | Invariant | How to check it |
|---|-----------|-----------------|
| S1 | Acyclic, fully-connected DAG | topological sort of the emitted dependency events is complete, no cycle, no task referencing a nonexistent id |
| S2 | No orphaned tasks | every `task_created` id is eventually claimed by an agent and terminates `passed` or `cancelled` with a reason — none silently dropped |
| S3 | Dependency correctness under concurrency | no task starts/verifies before a dependency is verified (partial order holds against real timestamps/precedences) |
| S4 | Unique ownership | each task is `started` by exactly **one** agent; no double-claim, no lost race that both claim |
| S5 | Atomic, contiguous, gap-free log | `seq` runs 1..N with no gaps/dupes despite N concurrent writers |
| S6 | Verification evidence per task | every `verification_passed`/`failed` has a matching `evidence_added`; failures are real and were fixed/re-verified (≥ 2 cycles) |
| S7 | Derived reproducibility at scale | `graph.json`/`metrics.json` regenerate byte-identical from `events.log` alone (double-derive hash match) |
| S8 | Replayability | a third party can reconstruct goal→plan→run→resolution purely from the log + replay.md |
| S9 | Context assembly at scale | the doc-assembly path (forge CLI/context) produces a coherent context doc at t=~50, ~100, ~full without error |
| S10 | No state corruption | no lost/duplicated/garbled lines in `events.log`; SDK `load` matches line count of the file |

Non-goals: adding another language (three is enough), touching the kernel, and
over-optimizing the executor. If a failure appears, it is preserved as a first
class verification `failed` event and its fix / workaround recorded — not hidden.

---

## 2. Concurrency model (how "multiple agents" is honest)

Agents are **independent OS processes**, each a fresh interpreter running the
public `forge` SDK (or CLI). There is no shared agent object and no
inter-process messaging between agents other than the shared event log.

- **N = 4 agents** initially (tunable 2…6). Each agent is bound to a
  *subsystem* (its ownership scope) plus the shared foundation.
- **Ready-set computation.** Each agent repeatedly asks the SDK for the set of
  **ready** (dependencies finished, all deps passed) tasks in its scope.
  an agent may start a ready task `T` iff no peer has already claimed `T` — made
  atomic by the SDK's own cross‑process locking; the harness never trusts a
  pre‑computed snapshot without rechecking.
- **Claim → build → verify → evidence.** One agent, the claim owner, does the
  start, the real test run, the evidence write, and the verification. Two peers
  may *start* the same ready task during a ready‑queue recompute exactly when
  the store's lock arbitrates the second one as a re‑claim; the harness treats a
  rejected claim as a **no‑op back‑off**, and a genuine double‑claim (both
  accepted) as a **corruption finding** to record.
- **Retry/revision loop.** A failing task keeps its owner; the owner edits and
  re‑verifies under the same task id (modeled per the proof standard as
  `verification_failed` then a later `verification_passed`, no `task_retried`
  op). Cross‑agent review: a task built by agent X may be independently
  re‑verified by agent Y of a downstream subsystem that consumes it — this
  produces the "reviewer loop" handoff evidence (C4/C5).
- **Snapshots.** After each milestone the harness re‑derives so the graph is
  snapshotted evolving (01-foundation → 02-contract/storage → 03-gateway/auth → 04-worker → 05-cli/observe → 06-e2e/readme).

The concurrency harness lives under `examples/<name>/` (proof tooling, same as a
`demo.sh`) and is itself submitted-provable code; it does **not** modify the
public forge package.

---

## 3. Subject project — `swarm`, a miniature multi-processing system

Any subject with genuinely separable subsystems works; `swarm` is chosen
because each subsystem is a unit of work an agent can own end‑to‑end, and the
cross‑subsystem dependencies (contract → everything) force real contention on
the shared start.

```
swarm/                        # ONE repo, ~120–140 tasks
  contract/    …1             # wire:schema, wire:codec, wire:validation  (agent A)
  storage/     …2             # repos: users, jobs, events; migrations      (agent B)
  auth/        …3             # token issue/verify middleware               (agent B)
  gateway/     …4             # HTTP routes: users, jobs, events            (agent A)
  worker/      …5             # queue pool consuming storage,jobs           (agent C)
  cli/         …6             # admin tooling                                (agent C)
  observe/     …7             # structured logging + /metrics                (agent D)
  tests/       …8             # per‑subsystem + end‑to‑end integration       (D shared)
  docs/        …9             # README (8 sections), run guide               (shared)
```

Each `…` is a **named agent owner**. Foundation tasks (skeleton, Makefile/pyproject,
fixtures, test scaffolding) are shared ready at the base so all peers ramps up
concurrently at launch — this is what manufactures a wide `max_ready_queue`
early, proving true frontier parallelism on the *graph* (consistent with the
existing MaxQ metric, not executor heroics).

Target size: **≥ 110 tasks** (above the 100+ bar), organized into **7
agent-owned subsystems** (storage, network, auth, queue, CLI, observability,
contract). A diagram of the DAG and a predicted MaxQ (derived by a pre-flight
simulate over `proposal.json`) go in the plan so the run can be judged against
expectations.

---

## 4. Failure & revision plan (real engineering, recorded honestly)

The proof must preserve genuine `verification_failed` cycles. Planned-but-real
categories the proposal injects a few of — each gets a concrete trigger so the
defect is real, not staged:

1. **Contract drift:** `storage` repository returns a job row shape that
   `worker` reader consumes earlier than the schema field it reads is added
   (cross-subsystem bug). Expect the consumer's test to fail; fix = align the
   consumed field, re‑verify worker.
2. **Concurrency race (the headline):** two agents contend for the same ready
   leaf in a fan‑out wave. If the SDK's cross‑process lock yields a clean
   single claim, the race manifests as a benign back‑off in one agent and is
   recorded as evidence of correct arbitration (expected). If a genuine
   duplicate claim or a garbled line appears, that is a real defect finding to
   record + workaround, surfaced for follow‑up (kernel untouched).
3. **Verification being wrong** (test attributed a wrong fast assertion) — a
   reviewer‑agent catches it and re‑flips verification_failed→passed after the
   *test*, not the code, is corrected — mirroring the CHIP‑8 "wrong test" lesson.
4. **Out-of-order evidence**: an agent claims verification of a task whose dep
   is still open (harness lets violations through to exercise the guard), the
   guard rejects it, recorded.

Target health: ≥ 2 genuine failure+retry cycles, ending fully green (every task
passes). If any injected failure discloses an SDK robustness gap, that gap
becomes a highlighted finding **plus** the run still reaches a conforming green.

---

## 5. Verification duties the harness performs

Beyond the SDK's own verifications, the harness runs the S10 check list from
§1 as a script that reads the finished `events.log` plus `graph.json` and
emits a boolean per invariant (S1–S10). These checks are submitted into the
proof's own `screenshots`/replay as evidence, i.e. the proof's *meta‑verification*
is itself part of the reproducible bundle.

A **byte-identical double-derive** (delete golden graph/metics, re‑derive,
compare) is mandatory at the end.

---

## 6. Deliverables (standard Proof #5 bundle)

See PROOF_SPEC: `examples/swarm/` with README (8 sections, incl. Lessons +
claim IDs C4/C5), `events.log` (contiguous, shipped), `graph.json`,
`graph.png` (subsystem + status colored), stacked `graph snapshots`,
`replay.md` (goal/outcome/timeline/turning‑points), `metrics.json` (log‑derived;
`max_ready_queue` from a real large frontier), ≥ 2 screenshots, `demo.mp4`
(≤120s, ≤720p, real concurrent run + final tests), `proposal.json`.

Proof‑check must print `CONFORMING`. `proofs/INDEX.md` gains the #5 row,
claims C4/C5 checked, and `ROAD_TO_1.0.md` evidence box flipped only on a
**conforming** run.

---

## 7. Pre-flight gate (before any run), to keep the run honest

- [ ] Confirm `forge` SDK is importable and `forge --help` works from a clean
      venv (public CLI only, no private calls).
- [x] **DAG simulation over `proposal.json` (2026-08-07): PASSED.** 114 tasks,
      153 dependency edges, 9 subsystems, 4 agents; `examples/swarm/preflight_dag.py`
      validates: count ≥110 ✓, ids unique ✓, every dep references an existing
      task ✓, no self/duplicate edges ✓, acyclic (Kahn covers all 114) ✓,
      subsystem→agent ownership disjoint and covers 114/114 ✓, no orphaned
      tasks (1 root, all 114 reachable) ✓, proposal passes `validate_proposal`
      and `Kernel.import_events` ✓. Predicted MaxQ (intrinsic frontier peak) =
      **26**; 12 intrinsic waves; under the N=4 constraint: **34 waves**, longest
      wave 4; longest dependency chain depth 11. First gate run surfaced and
      fixed a gate-internal wave-simulation bug (indegree recompute inverted —
      reported peak 111/waves 2); corrected to 26/12 and cross-checked by an
      independent simulation (waves [1,2,4,14,19,23,26,11,5,5,3,1] sum 114).
      Harness scaffolded (`examples/swarm/`), smoke self-test PASSED (2
      processes, 8 tasks, real files, S-invariants green in 0.6s).
- [x] **Lung gate (2026-08-07): PASSED.** 4 independent OS processes × 50
      benign `create_task` appends (200 `task_created` events) to one scratch
      project via the public `Kernel` SDK, started simultaneously: all workers
      rc=0 in 8.4s; `seq` contiguous 1..200 (no gaps/dupes); exported events ==
      raw log lines == 200; every line valid JSON (no garbled interleave); all
      200 ids present in the replayed graph. The store's documented
      cross-process lock claim (`forge/store.py`) holds under contention —
      proceed to scaffolding. (Scratch project under `%TEMP%`, removed after.)
- [ ] `proof-check` baseline passes on the newest conforming proof (regression
      the tool itself).

---

*Authored: 2026-08-07. Sources of truth: `proofs/PROOF_SPEC.md`,
`proofs/INDEX.md` (Milestones), `ROAD_TO_1.0.md`, `examples/*` corpus. Updated
alongside the index; a mismatch with `INDEX.md`/`ROAD_TO_1.0.md` fails the
compliance suite (`test_road_to_1_0_checklist_matches_index`).*