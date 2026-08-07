#!/usr/bin/env python3
"""Proof #5 pre-flight DAG-simulation gate (PHASE2_DESIGN.md §7, gate 1).

Validates the `swarm` proposal against the Proof #5 requirements and predicts
the max-ready-queue before any expensive execution. Uses only the public
Forge SDK (validate_proposal, Kernel.import_events) plus pure graph math.

Checks (each prints PASS/FAIL):
  - envelope: validate_proposal() accepts the proposal (SPEC §9)
  - kernel accepts it: Kernel.import_events builds a full task graph
  - task count >= 110
  - every task id unique
  - dependency partial-order valid: every edge refs an existing task, no
    self-edge, no duplicate edge
  - acyclic (Kahn topological sort completes over all tasks)
  - ownership covers every task exactly once: per-agent task lists are
    disjoint and their union == the full task set
  - no orphaned tasks: every task is reachable from a root via successors
  - predicted max-ready-queue: unbounded-frontier wave sim (peak frontier),
    plus the N=4-constrained schedule and its depth.

Usage: python examples/swarm/preflight_dag.py
Exit 0 = DAG gate green. Exit 1 = a check failed.
"""
import json
import os
import sys
import tempfile
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
MIN_TASKS = 110
AGENTS = 4

sys.path.insert(0, REPO)
from forge import Kernel              # noqa: E402  public SDK
from forge.sdk import validate_proposal  # noqa: E402

fails = []

def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""))
    if not cond:
        fails.append(name)

def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)

proposal = load("proposal.json")
subsystems = load("subsystems.json")

# ---- 0. envelope: public protocol validator
try:
    validate_proposal(proposal)
    check("proposal passes validate_proposal (SPEC §9)", True)
except Exception as e:
    check(f"proposal passes validate_proposal (SPEC §9): {e}", False)

created = [e for e in proposal["events"] if e["op"] == "task_created"]
edges = [(e["task"], e["depends_on"])
         for e in proposal["events"] if e["op"] == "dependency_added"]
task_ids = {e["id"] for e in created}

# ---- 1b. kernel accepts it (real dry-run import)
try:
    tmp = tempfile.mkdtemp(prefix="swarm-gate-")
    k = Kernel(tmp)
    k.import_events(proposal["events"])
    import shutil
    check("kernel imports proposal without error", True)
    check("kernel graph task count == proposal", len(k.graph.tasks) == len(task_ids),
          f"{len(k.graph.tasks)}/{len(task_ids)}")
    shutil.rmtree(tmp, ignore_errors=True)
except Exception as e:
    check(f"kernel imports proposal without error: {e}", False)

check("task count >= 110", len(task_ids) >= MIN_TASKS, f"{len(task_ids)}")
check("task ids unique", len(created) == len(task_ids),
      f"{len(created)} created events, {len(task_ids)} unique ids")

# ---- 2. dependency partial order: refs exist, no self, no dup
bad_ref = [(t, d) for (t, d) in edges if d not in task_ids or t not in task_ids]
self_dep = [t for (t, d) in edges if t == d]
uniq = set(edges)
check("every dep references an existing task", not bad_ref, str(bad_ref[:5]))
check("no self-dependencies", not self_dep, str(self_dep))
check("no duplicate dependency edges", len(uniq) == len(edges),
      f"{len(edges)} edges, {len(uniq)} unique")

# ---- 3. acyclicity via Kahn
succ = {i: set() for i in task_ids}
indeg = {i: 0 for i in task_ids}
for (t, d) in uniq:
    if t in succ and d in succ and t != d:
        succ[d].add(t)
        indeg[t] += 1
roots = sorted(i for i in task_ids if indeg[i] == 0)
order = []
q = deque(roots)
while q:
    n = q.popleft()
    order.append(n)
    for m in sorted(succ[n]):
        indeg[m] -= 1
        if indeg[m] == 0:
            q.append(m)
acyclic = len(order) == len(task_ids)
check("acyclic (topological order covers all tasks)", acyclic,
      "DAG OK" if acyclic else f"sorted {len(order)}/{len(task_ids)}")

# ---- 4. no orphaned tasks (reachability from roots)
reach = set()
seen = set(roots)
dq = deque(roots)
while dq:
    n = dq.popleft()
    reach.add(n)
    for m in succ[n]:
        if m not in seen:
            seen.add(m)
            dq.append(m)
orphaned = sorted(task_ids - reach)
orphan_detail = (f"{len(orphaned)} orphan(s): {orphaned[:6]}" if orphaned
                 else f"{len(roots)} root(s), {len(reach)} reachable")
check("no orphaned tasks (all reachable from root(s))", not orphaned, orphan_detail)

# ---- 3. subsystems -> agent ownership covers every task exactly once
agent_tasks = [info["tasks"] for info in subsystems["agents"].values()]
flat_agent = [x for lst in agent_tasks for x in lst]
check("exactly 4 agents", len(agent_tasks) == AGENTS, f"{len(agent_tasks)}")
check("agent ownership is disjoint",
      len(set(flat_agent)) == len(flat_agent),
      f"{len(flat_agent)} assignments, {len(set(flat_agent))} unique")
check("agent ownership covers every task", set(flat_agent) == task_ids,
      f"coverage {len(set(flat_agent))}/{len(task_ids)}")
not_owned = sorted(task_ids - set(flat_agent))
double = [x for x in set(flat_agent) if flat_agent.count(x) > 1]
check("no task without an owner", not not_owned, str(not_owned[:5]))
check("no task with multiple owners", not double, str(double[:5]))
sub_known = all(sid in task_ids
                for info in subsystems["subsystems"].values()
                for sid in info["tasks"])
check("every subsystem task is a known task", sub_known)

# ---- 5. predicted max-ready-queue (simulation)
# Correct wave model: indeg2[t] = number of t's deps NOT yet done; a task is
# ready when it reaches 0. Each wave captures the full ready frontier.
indeg2 = {i: len([d for (t, d) in uniq if t == i]) for i in task_ids}
done = set()
frontier = [i for i in task_ids if indeg2[i] == 0]
waves_4 = 0
longest_wave4 = 0
waves_intrinsic = 0
max_q = 0
while frontier:
    max_q = max(max_q, len(frontier))
    waves_intrinsic += 1
    waves_4 += (len(frontier) + AGENTS - 1) // AGENTS
    longest_wave4 = max(longest_wave4, min(AGENTS, len(frontier)))
    done |= set(frontier)
    indeg2 = {i: len([d for (t, d) in uniq if t == i and d not in done])
              for i in task_ids if i not in done}
    frontier = [i for i in indeg2 if indeg2[i] == 0]

check("predicted max-ready-queue (intrinsic frontier)", max_q >= 1, f"peak = {max_q}")
check("predicted max-ready-queue broad (>= 5)", max_q >= 5, f"peak = {max_q} ready at once")
check("N=4 frontier persists (>= 4 waves)", waves_4 >= 4, f"{waves_4} waves under N=4")
print(f"        simulated: roots={len(roots)} | intrinsic frontier peak={max_q} "
      f"| intrinsic waves={waves_intrinsic} | N={AGENTS} waves={waves_4} "
      f"| longest N=4 wave={longest_wave4}")

print("\nDAG SIMULATION GATE:", "PASSED" if not fails else f"FAILED: {fails}")
sys.exit(0 if not fails else 1)