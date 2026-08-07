# Proof #5 — `swarm`: a mini multi-service system built by 4 concurrent agents

Status: **scaffold / pre-flight complete — execution gated on review.**
DAG-simulation pre-flight gate: **PASSED** (see §5 and `preflight_dag.py`).

## 1. What was built

`swarm` is a miniature multi-service system (a job-processing platform):
contract, storage, auth, gateway, worker, cli and observe subsystems, ~114
tasks, implemented by **four independent OS processes (agents)** racing on one
Forge project through the public `Kernel` SDK.

> Execution note: this proof's *purpose* is the concurrent multi-process
> execution itself (claims, verification, dependency ordering, event-log
> integrity under N=4 writers). The per-task implementation is executed by
> the autonomous run that launches only after this checkpoint.

## 2. Why this proof exists

Proof #5 claims (PHASE2_DESIGN.md):

- **C1** — the kernel's cross-process integrity claim holds at scale
  (114 tasks, 4 concurrent writers, one event log).
- **C3** — dependency partial-order is preserved across processes: no agent
  starts a task before its deps are done, regardless of scheduling.
- **C5** — the public SDK surface is sufficient for realistic concurrent
  multi-agent workflows (no kernel/API changes required — kernel frozen).

## 3. Final architecture

(TBD by the run — placeholder)

```
4 OS processes ──public Kernel SDK──▶ one shared Forge project
agent-a: foundation + contract + gateway   (42 tasks)
agent-b: storage + auth                    (30 tasks)
agent-c: worker + cli                      (25 tasks)
agent-d: observe + integration             (17 tasks)
```

Ownership map: `subsystems.json`. Task graph: `proposal.json` (114 tasks,
153 dependency edges). Harness: `run_agents.py` (orchestrator + workers).

## 4. Commands

```bash
# pre-flight gate (must be green before any run)
python examples/swarm/preflight_dag.py

# import the proposal into a fresh project dir (no execution)
python examples/swarm/run_agents.py --init --workdir examples/swarm/.proof-work

# harness self-test (8 tasks, 2 agents, real files) — proves the machinery
python examples/swarm/run_agents.py --smoke

# THE FULL RUN (launched only after review checkpoint)
python examples/swarm/run_agents.py --workdir examples/swarm/.proof-work
```

## 5. Reproduce

1. `python examples/swarm/preflight_dag.py` → DAG gate green (all PASS).
2. `python examples/swarm/run_agents.py --smoke` → harness self-check green.
3. Full run per §4 (review-gated).

## 6. Artifact index

(TBD by the run — placeholder)

| Artifact | Path | Status |
|---|---|---|
| Proposal (114 tasks, 153 edges) | `proposal.json` | committed |
| Ownership sidecar (4 agents) | `subsystems.json` | committed |
| DAG pre-flight gate | `preflight_dag.py` | PASSED |
| Harness (orchestrator + workers) | `run_agents.py` | smoke PASSED |
| Event log | `.proof-work/events.log` (via export) | pending run |
| Graph render | `graph.png` | pending run |
| Replay | `replay.md` | pending run |
| Metrics | `metrics.json` | pending run |
| Screenshots | `screenshots/` | pending run |
| Demo video | `demo.mp4` | pending run |

## 7. Behavior notes

- Workers poll with `Kernel.replay()` before every `ready()` snapshot —
  cross-process readiness visibility is reloaded from the shared store.
- Claims race across processes; a lost claim backs off and re-polls
  (`_claim`, MAX_RETRIES).
- Evidence kind is `soft` (schema: `hard`/`soft` only).
- The `swarm` service code itself is stdlib-only (sqlite3, hmac,
  http.server, argparse, logging) — no third-party runtime deps.

## 8. Lessons learned

(TBD by the run — placeholder)

- `Kernel.ready()` reflects an in-memory graph loaded at construction; a
  multi-process worker MUST `replay()` before each poll or it never sees
  other agents' commits (found by the smoke test).
- Spawned workers re-import the harness module: configuration must travel
  via env vars (`SWARM_SUBSYSTEMS`, `SWARM_SMOKE_TREE`), not globals.
- Priority enum is `low|medium|high`; evidence kinds are `hard|soft`.
