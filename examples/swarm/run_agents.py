#!/usr/bin/env python3
"""Proof #5 `swarm` multi-agent harness (examples/swarm/run_agents.py).

Co-ordinates N=4 independent OS processes, each an "agent" that owns a subset
of the swarm proposal (subsystems.json) and drives the Forge project through
the PUBLIC Kernel SDK only. The kernel and its public API are frozen — this
file never touches forge internals.

Modes:
  python examples/swarm/run_agents.py                  orchestrator (real run)
  python examples/swarm/run_agents.py --init           import proposal only
  python examples/swarm/run_agents.py --worker agent-a worker process
  python examples/swarm/run_agents.py --smoke          harness self-test
                                                       (8 tasks, 2 agents,
                                                        real files, ~seconds)

The per-task IMPLEMENTATION seam is `Implementable`/`implementer_factory()`.
The scaffold ships DefaultImplementer (no-op) — the expensive autonomous
implementation is launched only after the DAG gate + review checkpoint.
The lifecycle machinery (claim / verify / evidence / retry, ownership
scoping, cross-process backoff, S-invariant meta-checks) is fully functional
and proven by --smoke.
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import tempfile
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, REPO)
from forge import Kernel  # noqa: E402  public SDK only

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = ("agent-a", "agent-b", "agent-c", "agent-d")
MAX_RETRIES = 3
BACKOFF_S = 0.05
POLL_S = 0.2
IDLE_TIMEOUT_S = 60.0
STATUS_DONE = "done"

# ---------------------------------------------------------------------------
# Implementation seam
# ---------------------------------------------------------------------------
class Implementable:
    """Implement a task so its acceptance criteria hold (write real code +
    tests). Raise on failure; the harness will verify_fail + retry."""

    def run(self, task_id, task):
        raise NotImplementedError

class DefaultImplementer(Implementable):
    """Scaffold stub: no-op. Replaced by the real executor in the full run."""

    def run(self, task_id, task):
        return

def implementer_factory():
    """Build the per-worker implementation seam. When SWARM_SMOKE_TREE is set
    (harness self-test), workers get the file-writing smoke implementer."""
    tree = os.environ.get("SWARM_SMOKE_TREE")
    if tree:
        return _SmokeImplementer(tree)
    return DefaultImplementer()

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def subsystems():
    """Ownership sidecar. Path overridable via SWARM_SUBSYSTEMS so the smoke
    self-test can point spawned workers at a tiny sidecar."""
    path = os.environ.get("SWARM_SUBSYSTEMS", os.path.join(HERE, "subsystems.json"))
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def owned_task_ids(agent):
    return set(subsystems()["agents"][agent]["tasks"])

def init_project(workdir, proposal_path=None):
    os.makedirs(workdir, exist_ok=True)
    k = Kernel(workdir)
    if proposal_path and not k.export_events():
        with open(proposal_path, encoding="utf-8") as f:
            k.import_events(json.load(f)["events"])
    return k

def _claim(k, task_id):
    """Claim a ready task. Returns True on success; backoff+retry on races
    (another agent's process may have claimed the same snapshot)."""
    for attempt in range(1 + MAX_RETRIES):
        try:
            k.start(task_id)
            return True
        except Exception:
            if attempt == MAX_RETRIES:
                return False
            time.sleep(BACKOFF_S * (attempt + 1))
    return False

def implement_with_retry(k, task_id, impl):
    """Run the implementation seam; on failure record verify_fail + retry().
    Returns (ok, reason)."""
    task = k.inspect(task_id)
    for attempt in range(1 + MAX_RETRIES):
        try:
            impl.run(task_id, task)
            return True, ""
        except Exception as e:
            reason = f"{type(e).__name__}: {e}"
            if attempt == MAX_RETRIES:
                try:
                    k.verify_fail(task_id, reason[:2000])
                except Exception:
                    pass
                return False, reason
            try:
                k.verify_fail(task_id, reason[:2000])
                k.retry(task_id)
                k.start(task_id)
            except Exception:
                return False, reason
    return False, "unreachable"

# ---------------------------------------------------------------------------
# Worker process
# ---------------------------------------------------------------------------
def run_agent_process(workdir, agent, queue):
    k = Kernel(workdir)
    owned = owned_task_ids(agent)
    impl = implementer_factory()
    summary = {"agent": agent, "claimed": 0, "passed": 0, "failed": 0,
               "retries": 0, "done": 0, "error": None}
    try:
        idle_since = time.time()
        while True:
            k.replay()  # reload cross-process state before we look
            ready = [t for t in k.ready() if t in owned]
            if ready:
                idle_since = time.time()
                for task_id in ready:
                    if not _claim(k, task_id):
                        summary["failed"] += 1
                        continue
                    summary["claimed"] += 1
                    ok, _reason = implement_with_retry(k, task_id, impl)
                    if ok:
                        try:
                            k.verify_pass(task_id)
                            k.add_evidence(task_id, kind="soft", source="run_agents.py",
                                           detail=f"agent={agent} verified {task_id}")
                            summary["passed"] += 1
                        except Exception as e:
                            summary["failed"] += 1
                            summary["error"] = summary["error"] or f"evidence error: {e}"
                    else:
                        summary["failed"] += 1
                continue
            # nothing ready for us: exit only when every owned task is done;
            # otherwise upstream agents are still working — keep polling.
            if all(k.inspect(t).get("status") == STATUS_DONE for t in owned):
                break
            if time.time() - idle_since > IDLE_TIMEOUT_S:
                summary["error"] = summary["error"] or "idle timeout (upstream stalled?)"
                break
            time.sleep(POLL_S)
        summary["done"] = len([t for t in owned
                               if k.inspect(t).get("status") == STATUS_DONE])
    except Exception as e:  # never die silently — report the failure
        summary["error"] = f"{type(e).__name__}: {e}"
    finally:
        queue.put(summary)
    return summary

# ---------------------------------------------------------------------------
# S-invariant meta-checks (S1..S10 style) on the final event log
# ---------------------------------------------------------------------------
def assert_project_invariants(workdir, expected_ids, label):
    k = Kernel(workdir)
    problems = []
    evs = k.export_events()
    seqs = [e.get("seq") for e in evs]
    if seqs != list(range(1, len(seqs) + 1)):
        problems.append(f"seq not contiguous 1..{len(seqs)}")
    starts = {}
    passes = 0
    for e in evs:
        tid = e.get("task") or e.get("task_id") or e.get("id")
        op = e.get("op")
        if op == "task_started" and tid:
            starts[tid] = starts.get(tid, 0) + 1
        if op == "verification_passed":
            passes += 1
    multi = {t: c for t, c in starts.items() if c > 1}
    if multi:
        problems.append(f"double-claim: {multi}")
    for tid in expected_ids:
        st = k.inspect(tid).get("status")
        if st != STATUS_DONE:
            problems.append(f"{tid} status={st}")
    if passes < len(expected_ids):
        problems.append(f"verification_passed {passes} < {len(expected_ids)}")
    status = "PASS" if not problems else "FAIL"
    print(f"[{status}] S-invariants ({label}): {len(evs)} events, "
          f"{len(expected_ids)} tasks, {passes} verified"
          + ("" if not problems else f" — {problems[:6]}"))
    return not problems

# ---------------------------------------------------------------------------
# Smoke self-test: 8 tasks / 2 agents / real files, proves the machinery
# ---------------------------------------------------------------------------
def _smoke_proposal():
    events = [
        {"op": "task_created", "id": "s-a1", "title": "smoke A1",
         "description": "write smoke/src/s-a1.py", "acceptance": ["file exists"],
         "files": ["smoke/src/s-a1.py"], "priority": "medium"},
        {"op": "task_created", "id": "s-a2", "title": "smoke A2",
         "description": "write smoke/src/s-a2.py", "acceptance": ["file exists"],
         "files": ["smoke/src/s-a2.py"], "priority": "medium"},
        {"op": "task_created", "id": "s-b1", "title": "smoke B1",
         "description": "write smoke/src/s-b1.py", "acceptance": ["file exists"],
         "files": ["smoke/src/s-b1.py"], "priority": "medium"},
        {"op": "task_created", "id": "s-b2", "title": "smoke B2",
         "description": "write smoke/src/s-b2.py", "acceptance": ["file exists"],
         "files": ["smoke/src/s-b2.py"], "priority": "medium"},
        {"op": "dependency_added", "task": "s-a2", "depends_on": "s-a1"},
        {"op": "dependency_added", "task": "s-b1", "depends_on": "s-a1"},
        {"op": "dependency_added", "task": "s-b2", "depends_on": "s-b1"},
    ]
    return {"proposal_id": "prop_smoke_001", "reason": "harness self-test",
            "confidence": 1.0, "events": events}

class _SmokeImplementer(Implementable):
    """Writes real files; asserts dependency markers exist first (ordering on
    the shared filesystem across processes)."""

    def __init__(self, tree):
        self.tree = tree
        self.src = os.path.join(tree, "smoke", "src")
        self.done = os.path.join(tree, "smoke", "done")

    def run(self, task_id, task):
        os.makedirs(self.src, exist_ok=True)
        os.makedirs(self.done, exist_ok=True)
        for dep in (task or {}).get("dependencies", []):
            marker = os.path.join(self.done, dep + ".ok")
            if not os.path.exists(marker):
                raise RuntimeError(f"dependency {dep} not done yet")
        path = os.path.join(self.src, task_id + ".py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"def ok(): return True  # {task_id}\n")
        with open(os.path.join(self.done, task_id + ".ok"), "w", encoding="utf-8") as f:
            f.write("done\n")

def run_smoke():
    import shutil
    workdir = tempfile.mkdtemp(prefix="swarm-smoke-")
    tree = os.path.join(workdir, "tree")
    os.makedirs(tree, exist_ok=True)
    fake_sidecar = {
        "agents": {"agent-a": {"tasks": ["s-a1", "s-a2"]},
                   "agent-b": {"tasks": ["s-b1", "s-b2"]}}
    }
    side_path = os.path.join(workdir, "subsystems.json")
    with open(side_path, "w", encoding="utf-8") as f:
        json.dump(fake_sidecar, f)
    old_env = {k: os.environ.get(k) for k in ("SWARM_SUBSYSTEMS", "SWARM_SMOKE_TREE")}
    os.environ["SWARM_SUBSYSTEMS"] = side_path
    os.environ["SWARM_SMOKE_TREE"] = tree
    try:
        k = init_project(workdir, None)
        k.import_events(_smoke_proposal()["events"])
        ids = {e["id"] for e in k.export_events() if e.get("op") == "task_created"}
        ctx = mp.get_context("spawn")
        queue = ctx.Queue()
        procs = [ctx.Process(target=run_agent_process, args=(workdir, a, queue))
                 for a in ("agent-a", "agent-b")]
        t0 = time.time()
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=120)
        dt = time.time() - t0
        summaries = [queue.get(timeout=5) for _ in procs]
        for s in summaries:
            print(f"  worker {s['agent']}: claimed={s['claimed']} "
                  f"passed={s['passed']} failed={s['failed']}")
        ok = all(p.exitcode == 0 for p in procs)
        ok = assert_project_invariants(workdir, ids, "smoke") and ok
        print(f"[{'PASS' if ok else 'FAIL'}] smoke run: {len(ids)} tasks, "
              f"{dt:.1f}s, exitcodes={'/'.join(str(p.exitcode) for p in procs)}")
        sys.exit(0 if ok else 1)
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(workdir, ignore_errors=True)

# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Proof #5 swarm harness")
    ap.add_argument("--workdir", default=os.path.join(HERE, ".proof-work"))
    ap.add_argument("--init", action="store_true",
                    help="import the proposal into the project dir and exit")
    ap.add_argument("--worker", choices=AGENTS,
                    help="run as a worker process for this agent")
    ap.add_argument("--smoke", action="store_true", help="run the harness self-test")
    args = ap.parse_args()

    if args.smoke:
        run_smoke()
        return
    if args.worker:
        queue = mp.Queue()
        res = run_agent_process(args.workdir, args.worker, queue)
        print(json.dumps({"worker": args.worker, "summary": res}))
        sys.exit(0)

    # orchestrator
    for var in ("SWARM_SUBSYSTEMS", "SWARM_SMOKE_TREE"):
        os.environ.pop(var, None)  # a stray smoke env must never leak into a real run
    k = init_project(args.workdir, os.path.join(HERE, "proposal.json"))
    ids = {e["id"] for e in k.export_events() if e.get("op") == "task_created"}
    print(f"project ready: {len(ids)} tasks @ {args.workdir}")
    if args.init:
        sys.exit(0)

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    procs = [ctx.Process(target=run_agent_process, args=(args.workdir, a, queue))
             for a in AGENTS]
    t0 = time.time()
    for p in procs:
        p.start()
        print(f"  started {p.pid}")
    for p in procs:
        p.join(timeout=7200)
    dt = time.time() - t0
    summaries = []
    for _ in procs:
        try:
            summaries.append(queue.get(timeout=10))
        except Exception:
            pass
    for s in summaries:
        print(f"  agent {s['agent']}: claimed={s['claimed']} passed={s['passed']} "
              f"failed={s['failed']} done={s['done']}")
    ok = all(p.exitcode == 0 for p in procs)
    ok = assert_project_invariants(args.workdir, ids, "swarm") and ok
    print(f"swarm run: {dt:.0f}s wall | {'ALL AGENTS CLEAN' if ok else 'PROBLEMS'}")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()