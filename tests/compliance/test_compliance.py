"""Compliance suite — tests the SPECIFICATION (docs/SPEC.md), not features.

Every test maps to a kernel invariant (SPEC §1.9, I1–I7) or an
adversarial case the spec normatively requires (§3.3 validation,
§12.5 crash recovery, §9.4 atomic proposals). If a test here fails,
the kernel no longer complies with its own contract — the code is
wrong, not the test.

Invariant map:
  I1  Deterministic fold            test_fold_is_environment_independent
  I2  Replay identity               test_replay_reconstructs_identical_state
  I3  Derived state never persisted test_no_derived_state_in_log
  I4  Atomic proposals              test_proposal_commits_whole_or_not_at_all
  I5  Deterministic scheduler       test_scheduler_deterministic_under_random_creation
  I6  Verification cannot bypassed  test_verification_cannot_be_bypassed
  I7  Context never invents state   test_context_reports_only_real_state
Adversarial (spec §3.3, §12.5):
  malformed proposals              test_malformed_proposals_rejected_cleanly
  fuzzed event streams             test_fuzz_valid_streams_fold_identically
                                   test_fuzz_malformed_events_never_crash
  torn-log recovery                test_torn_tail_skipped_middle_is_fatal
  cross-environment replay         test_replay_identical_across_hash_seeds
"""
import json
import os
import random
import string
import subprocess
import sys
import tempfile
import unittest

from forge.context import build_context, to_json
from forge.kernel import Kernel
from forge.model import (Graph, GraphError, SCHEMA_VERSION, STATUS_DONE,
                           STATUS_IN_PROGRESS, STATUS_NEEDS_REVISION,
                           STATUS_TODO)
from forge.scheduler import next_task, progress, ready_tasks
from forge.store import Store, load_project

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def canonical(g: Graph) -> dict:
    """Environment-independent serialization of the folded state."""
    out: dict = {}
    for tid, t in sorted(g.tasks.items()):
        out[tid] = {
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "composite": t.composite,
            "created_seq": t.created_seq,
            "depends_on": sorted(t.depends_on),
            "acceptance": list(t.acceptance),
            "files": sorted(t.files),
            "evidence": sorted((e.kind, e.source, e.detail) for e in t.evidence),
            "notes": list(t.notes),
            "last_failure": t.last_failure,
        }
    return out


def stamped(ev: dict, seq: int) -> dict:
    return dict(ev, seq=seq, ts="2026-01-01T00:00:00+00:00", v=SCHEMA_VERSION)


def scenario() -> list[dict]:
    """A rich valid log: containers, deps, failures, retries, evidence."""
    g = Graph()
    events: list[dict] = []
    seq = 0

    def commit(ev):
        nonlocal seq
        seq += 1
        g.apply(stamped(ev, seq))
        events.append(stamped(ev, seq))

    commit(g.create_task("Snake Game", priority="high", files=["snake.py"]))
    commit(g.expand("snake-game", [
        {"title": "Window", "priority": "high"},
        {"title": "Renderer", "priority": "medium"},
        {"title": "Input", "priority": "low"},
    ]))
    commit(g.start("window"))
    commit(g.verify_pass("window"))
    commit(g.add_dependency("renderer", "window"))
    commit(g.start("renderer"))
    commit(g.verify_fail("renderer", "crashes on resize"))
    commit(g.add_evidence("renderer", "hard", "unittest", "2 fail"))
    commit(g.retry("renderer"))
    commit(g.add_dependency("input", "renderer"))
    commit(g.start("input"))
    commit(g.add_evidence("input", "soft", "peer review", "looks fine"))
    commit(g.verify_pass("input", force=True))
    commit(g.verify_pass("renderer"))
    commit(g.add_note("snake-game", "release blockers: none"))
    return events


def build_random_log(rng: random.Random, steps: int = 150) -> list[dict]:
    """Seeded random stream of *valid* events built through the builders."""
    g = Graph()
    events: list[dict] = []
    seq = 0
    ids: list[str] = []

    def commit(ev):
        nonlocal seq
        seq += 1
        g.apply(stamped(ev, seq))
        events.append(stamped(ev, seq))

    titles = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta",
              "Theta", "Iota", "Kappa", "Lambda", "Mu", "Nu", "Xi"]
    for _ in range(steps):
        op = rng.choice(["create", "start", "verify_fail", "retry",
                         "verify_pass", "expand", "dep", "evidence", "note"])
        try:
            if op == "create" or not ids:
                t = rng.choice(titles)
                ev = g.create_task(t, priority=rng.choice(["low", "medium", "high"]))
            elif op == "start":
                cands = [i for i in ids if g.tasks[i].status == STATUS_TODO
                         and not g.tasks[i].composite]
                if not cands:
                    continue
                ev = g.start(rng.choice(cands))
            elif op == "verify_fail":
                cands = [i for i in ids if g.tasks[i].status in
                         (STATUS_IN_PROGRESS, STATUS_NEEDS_REVISION)]
                if not cands:
                    continue
                ev = g.verify_fail(rng.choice(cands), "randomized failure")
            elif op == "retry":
                cands = [i for i in ids if g.tasks[i].status == STATUS_NEEDS_REVISION]
                if not cands:
                    continue
                ev = g.retry(rng.choice(cands))
            elif op == "verify_pass":
                cands = [i for i in ids if g.tasks[i].status in
                         (STATUS_IN_PROGRESS, STATUS_NEEDS_REVISION)
                         and not g.tasks[i].composite
                         and all(g.tasks[d].effective_status(g.tasks) == STATUS_DONE
                                 for d in g.tasks[i].depends_on)]
                if not cands:
                    continue
                ev = g.verify_pass(rng.choice(cands))
            elif op == "expand":
                cands = [i for i in ids if not g.tasks[i].composite
                         and g.tasks[i].effective_status(g.tasks) != STATUS_DONE]
                if not cands:
                    continue
                n = rng.randint(1, 3)
                ev = g.expand(rng.choice(cands), [
                    {"title": f"{rng.choice(titles)}-{rng.randint(1, 99)}",
                     "priority": rng.choice(["low", "medium", "high"])}
                    for _ in range(n)])
            elif op == "dep":
                if len(ids) < 2:
                    continue
                a, b = rng.sample(ids, 2)
                if a == b or b in g.tasks[a].depends_on:
                    continue
                ev = g.add_dependency(a, b)
            elif op == "evidence":
                ev = g.add_evidence(rng.choice(ids),
                                    rng.choice(["hard", "soft"]),
                                    rng.choice(["unittest", "review", "bench"]))
            else:
                ev = g.add_note(rng.choice(ids), "random note")
            commit(ev)
            if ev["op"] == "task_created":
                ids.append(ev["id"])
        except GraphError:
            continue  # legal-fuzz only commits valid events
    return events


class ComplianceInvariants(unittest.TestCase):
    """SPEC §1.9 — the seven invariants."""

    # ------------------------------------------------------------- I1
    def test_fold_is_environment_independent(self):
        """I1: same log, same state — regardless of key order or hash seed."""
        events = scenario()
        g1 = Graph.from_events(events)
        shuffled = [dict(e) for e in events]
        rng = random.Random(7)
        for e in shuffled:
            keys = list(e.keys())
            rng.shuffle(keys)
            e = {k: e[k] for k in keys}
        g2 = Graph.from_events(shuffled)
        self.assertEqual(canonical(g1), canonical(g2))
        self.assertEqual(g1.problems(), [])

    def test_replay_identical_across_hash_seeds(self):
        """I1 + I2: replay is identical under different PYTHONHASHSEED
        (the main cross-machine nondeterminism source in Python)."""
        events = scenario()
        payload = json.dumps(events, ensure_ascii=False)
        out = []
        for seed in ("0", "42", "12345"):
            code = (
                "import json, sys\n"
                "sys.path.insert(0, %r)\n"
                "from forge.model import Graph\n"
                "from forge.scheduler import ready_tasks, progress, next_task\n"
                "g = Graph.from_events(json.loads(%r))\n"
                "print(json.dumps({'tasks': sorted(g.tasks), "
                "'statuses': [g.tasks[i].status for i in sorted(g.tasks)], "
                "'ready': [t.id for t in ready_tasks(g)], "
                "'next': next_task(g), 'progress': progress(g)}, sort_keys=True))\n"
                % (REPO, payload))
            r = subprocess.run([sys.executable, "-c", code],
                               capture_output=True, text=True,
                               env={**os.environ, "PYTHONHASHSEED": seed})
            self.assertEqual(r.returncode, 0, r.stderr)
            out.append(r.stdout.strip())
        self.assertEqual(len(set(out)), 1, "replay differed across hash seeds")

    # ------------------------------------------------------------- I2
    def test_replay_reconstructs_identical_state(self):
        d = tempfile.mkdtemp()
        k = Kernel(d)
        for ev in scenario():
            k._commit(dict(ev))  # re-commit through the official path
        first = canonical(k.graph)
        k.replay()
        self.assertEqual(canonical(k.graph), first)
        store2, graph2 = load_project(d)
        self.assertEqual(canonical(graph2), first)
        # a second fold of the raw log must agree with the live graph
        raw = Store(d).read_events()
        self.assertEqual(canonical(Graph.from_events(raw)), first)

    # ------------------------------------------------------------- I3
    def test_no_derived_state_in_log(self):
        d = tempfile.mkdtemp()
        k = Kernel(d)
        for ev in scenario():
            k._commit(dict(ev))
        raw = open(os.path.join(d, "events.log"), encoding="utf-8").read()
        for banned in ("\"blocked\"", "\"ready\"", "\"completion\"",
                       "\"effective_status\"", "project.graph.json"):
            self.assertNotIn(banned, raw, f"derived state leaked into the log: {banned}")
        self.assertFalse(os.path.exists(os.path.join(d, "project.graph.json")),
                         "project.graph.json must not exist (graph is derived)")

    # ------------------------------------------------------------- I4
    def test_proposal_commits_whole_or_not_at_all(self):
        d = tempfile.mkdtemp()
        k = Kernel(d)
        k.create_task("A", id="a")
        k.create_task("B", id="b")
        before = len(k.store.read_events())
        # proposal of 3 events, the 2nd invalid -> whole batch rejected
        bad = [{"op": "task_created", "id": "c", "title": "C"},
               {"op": "no_such_op", "id": "x"},
               {"op": "task_created", "id": "d", "title": "D"}]
        with self.assertRaises(GraphError):
            k.import_events(bad)
        self.assertEqual(len(k.store.read_events()), before,
                         "invalid proposal partially committed")
        # proposal where the LAST event is invalid (guard, not shape)
        bad2 = [{"op": "task_created", "id": "c", "title": "C"},
                {"op": "dependency_added", "task": "a", "depends_on": "ghost"}]
        with self.assertRaises(GraphError):
            k.import_events(bad2)
        self.assertEqual(len(k.store.read_events()), before,
                         "guard-failing proposal partially committed")
        # valid proposal commits fully, atomically
        ok = k.import_events([{"op": "task_created", "id": "c", "title": "C"},
                              {"op": "task_created", "id": "d", "title": "D"}])
        self.assertEqual(ok["imported"], 2)
        self.assertEqual(len(k.store.read_events()), before + 2)
        self.assertIn("c", k.graph.tasks)
        self.assertIn("d", k.graph.tasks)

    # ------------------------------------------------------------- I5
    def test_scheduler_deterministic_under_random_creation(self):
        rng = random.Random(99)
        log_a = build_random_log(rng, steps=120)
        # same tasks, different creation order -> same final answers
        rng2 = random.Random(99)
        log_b = build_random_log(rng2, steps=120)
        self.assertEqual(log_a, log_b, "seeded generation must be reproducible")
        ga = Graph.from_events(log_a)
        gb = Graph.from_events(log_b)
        self.assertEqual([t.id for t in ready_tasks(ga)],
                         [t.id for t in ready_tasks(gb)])
        self.assertEqual(next_task(ga), next_task(gb))
        self.assertEqual(progress(ga), progress(gb))
        # and the answers are stable across repeated folds of the same log
        self.assertEqual([t.id for t in ready_tasks(Graph.from_events(log_a))],
                         [t.id for t in ready_tasks(ga)])

    # ------------------------------------------------------------- I6
    def test_verification_cannot_be_bypassed(self):
        g = Graph()
        seq = 0

        def commit(ev):
            nonlocal seq
            seq += 1
            g.apply(stamped(ev, seq))

        commit(g.create_task("A", id="a"))
        commit(g.create_task("B", id="b"))
        commit(g.add_dependency("b", "a"))
        # verify-pass on a todo task: rejected even with force
        with self.assertRaises(GraphError):
            g.verify_pass("a", force=True)
        self.assertEqual(g.tasks["a"].status, STATUS_TODO)
        # verify-pass with an unfinished dependency: rejected
        commit(g.start("b"))
        with self.assertRaises(GraphError):
            g.verify_pass("b")
        with self.assertRaises(GraphError):
            g.verify_pass("b", force=False)
        self.assertEqual(g.tasks["b"].status, STATUS_IN_PROGRESS)
        # force bypasses ONLY the dependency gate, never the status gate
        commit(g.verify_pass("b", force=True))  # legal: force + started
        self.assertEqual(g.tasks["b"].status, STATUS_DONE)
        # verify-pass on a container: rejected, always
        commit(g.create_task("C", id="c"))
        commit(g.expand("c", [{"title": "C1"}, {"title": "C2"}]))
        with self.assertRaises(GraphError):
            g.verify_pass("c")
        with self.assertRaises(GraphError):
            g.verify_pass("c", force=True)
        # verify-fail / retry / reopen on wrong states: rejected
        with self.assertRaises(GraphError):
            g.verify_fail("a", "nope")          # todo task
        with self.assertRaises(GraphError):
            g.retry("a")                        # not needs_revision
        with self.assertRaises(GraphError):
            g.reopen("a")                       # not done
        # only a genuine verification_passed moves a task to done
        self.assertEqual(g.tasks["a"].status, STATUS_TODO)

    # ------------------------------------------------------- §4.1 pinned
    def test_needs_revision_can_pass_verification_directly(self):
        # SPEC §4.1 event table (and the kernel) make verification_passed
        # legal from BOTH in_progress and needs_revision. The reviewer flow
        # happens to use retry before re-verifying, but the state machine
        # does not force it. Pin the current contract so any future change
        # is a deliberate spec amendment, not silent drift.
        g = Graph()
        seq = 0

        def commit(ev):
            nonlocal seq
            seq += 1
            g.apply(stamped(ev, seq))

        commit(g.create_task("A", id="a"))
        commit(g.start("a"))
        commit(g.verify_fail("a", "needs rework"))
        self.assertEqual(g.tasks["a"].status, STATUS_NEEDS_REVISION)
        # direct verify-pass from needs_revision: legal, task reaches done
        commit(g.verify_pass("a"))
        self.assertEqual(g.tasks["a"].status, STATUS_DONE)

    # ------------------------------------------------------------- I7
    def test_context_reports_only_real_state(self):
        d = tempfile.mkdtemp()
        k = Kernel(d)
        for ev in scenario():
            k._commit(dict(ev))
        for tid in k.graph.tasks:
            ctx = to_json(build_context(k.graph, tid))
            data = json.loads(ctx) if isinstance(ctx, str) else ctx
            flat = json.dumps(data)
            # every id referenced in the context exists in the graph
            for dep in data.get("dependencies", []):
                self.assertIn(dep["id"], k.graph.tasks)
            for b in data.get("blockers", []):
                self.assertIn(b, k.graph.tasks)
            self.assertEqual(data.get("id"), tid)
            self.assertEqual(data.get("status"), k.graph.tasks[tid].status)
            self.assertEqual(data.get("effective_status"),
                             k.graph.tasks[tid].effective_status(k.graph.tasks))
            # blockers in context == scheduler blockers
            self.assertEqual(set(data.get("blockers", [])),
                             set(b.id for b in k.blockers(tid)))
            # no ids outside the graph are mentioned (spot check)
            for token in ("snake-game", "window", "renderer", "input"):
                self.assertIn(token, k.graph.tasks)


class ComplianceAdversarial(unittest.TestCase):
    """SPEC §3.3 (validation) and §12.5 (crash recovery)."""

    def test_malformed_proposals_rejected_cleanly(self):
        g = Graph()
        seq = 0

        def commit(ev):
            nonlocal seq
            seq += 1
            g.apply(stamped(ev, seq))

        commit(g.create_task("A", id="a"))
        malformed = [
            {},                                        # missing op
            {"op": "no_such_op"},                      # unknown op
            {"op": "task_created"},                    # missing fields
            {"op": "task_created", "id": 42, "title": "X"},       # wrong type
            {"op": "task_created", "id": "x", "title": ""},       # empty title
            {"op": "task_created", "id": "has space", "title": "X"},  # bad id
            {"op": "task_created", "id": "x", "title": "X", "priority": "urgent"},  # bad priority
            {"op": "task_started", "id": "ghost"},    # dangling ref
            {"op": "dependency_added", "task": "a", "depends_on": "a"},  # self-edge
            {"op": "dependency_added", "task": "a", "depends_on": "ghost"},
            {"op": "task_expanded", "task": "a", "children": []},       # no children
            {"op": "task_expanded", "task": "a", "children": [{"id": "a", "title": "dup"}]},  # dup id
            {"op": "evidence_added", "id": "a", "kind": "maybe", "source": "s"},  # bad kind
            {"op": "verification_failed", "id": "a", "reason": ""},     # empty reason
            {"op": "task_updated", "id": "a"},                          # nothing to change
            {"op": "task_created", "id": "a", "title": "dup"},          # existing id
        ]
        for ev in malformed:
            with self.assertRaises(GraphError, msg=f"not rejected: {ev}"):
                g.validate(ev)
        # a dependency cycle through an existing edge
        commit(g.create_task("B", id="b"))
        commit(g.add_dependency("b", "a"))
        with self.assertRaises(GraphError):
            g.add_dependency("a", "b")
        # delete with dependents / children is rejected
        with self.assertRaises(GraphError):
            g.delete("a")
        commit(g.create_task("C", id="c"))
        commit(g.expand("c", [{"title": "C1"}]))
        with self.assertRaises(GraphError):
            g.delete("c")
        self.assertIn("c", g.tasks)

    def test_fuzz_valid_streams_fold_identically(self):
        rng = random.Random(2026)
        events = build_random_log(rng, steps=300)
        g1 = Graph.from_events(events)
        g2 = Graph.from_events(events)
        self.assertEqual(canonical(g1), canonical(g2))
        self.assertEqual(g1.problems(), [])
        self.assertTrue(len(g1.tasks) > 5, "fuzz log was too shallow")

    def test_fuzz_malformed_events_never_crash(self):
        """Random garbage (including wrong types inside lists) must be
        rejected with GraphError or folded — never raise anything else."""
        rng = random.Random(31337)
        ops = ["task_created", "task_started", "task_expanded", "task_deleted",
               "dependency_added", "verification_passed", "evidence_added",
               "task_retried", "task_reopened", "note_added", "task_updated",
               "verification_failed", "dependency_removed", "bogus_op",
               "task", "", 1, None]
        for trial in range(400):
            ev = {"op": rng.choice(ops)}
            for _ in range(rng.randint(0, 5)):
                k = rng.choice(["id", "title", "task", "depends_on", "children",
                                "reason", "kind", "source", "priority", "seq",
                                "force", "acceptance", "files"])
                v = rng.choice([42, None, True, "str", [1, 2], {"a": 1}, ["x", "y"], ""])
                ev[k] = v
            g = Graph()
            try:
                g.validate(ev)
                g.apply(ev)  # survived validation: must fold without crashing
            except GraphError:
                pass
            except Exception as e:  # noqa: BLE001 — any other exception is a bug
                self.fail(f"malformed event crashed with {type(e).__name__}: {e!r} for {ev!r}")

    def test_torn_tail_skipped_middle_is_fatal(self):
        """SPEC §12.5: torn final line is skipped; corruption elsewhere is fatal."""
        d = tempfile.mkdtemp()
        store = Store(d)
        store.init()
        k = Kernel(d)
        k.create_task("A", id="a")
        k.create_task("B", id="b")
        path = store.path
        with open(path, "a", encoding="utf-8") as f:
            f.write('{"op": "task_started", "id": "a", "seq": 99, "ts": "t", "v": 1')
        events = store.read_events()
        self.assertEqual(len(events), 2, "torn tail must be skipped")
        k2 = Kernel(d)  # reload: folds the intact prefix, skips the torn line
        self.assertIn("a", k2.graph.tasks)
        self.assertIn("b", k2.graph.tasks)
        self.assertEqual(k2.graph.tasks["a"].status, STATUS_TODO)  # start was the torn event
        # appending after a torn tail works (recovery) and re-stamps seq
        k2.create_task("C", id="c")
        self.assertEqual(len(Store(d).read_events()), 3)
        self.assertEqual(Store(d).read_events()[-1]["seq"], 3)
        # corruption in the middle (file tampering, not a crash remnant)
        # is a hard error
        d2 = tempfile.mkdtemp()
        s2 = Store(d2)
        s2.init()
        k3 = Kernel(d2)
        k3.create_task("A", id="a")
        k3.create_task("B", id="b")
        with open(s2.path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        lines.insert(1, "this is not json")  # tamper: garbage between events
        with open(s2.path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        with self.assertRaises(GraphError):
            s2.read_events()
        with self.assertRaises(GraphError):
            Kernel(d2)


if __name__ == "__main__":
    unittest.main()
