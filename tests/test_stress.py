"""Stress tests: try to break the kernel. No AI anywhere."""

import tempfile
import threading
import time
import unittest

from forge.kernel import Kernel
from forge.model import Graph, GraphError, STATUS_DONE
from forge.scheduler import progress
from forge.store import Store, load_project


def commit(g, ev, seq):
    ev = dict(ev)
    ev["seq"] = seq
    ev.setdefault("ts", "2026-07-31T12:00:00+00:00")
    g.apply(ev)
    return ev


class StressTest(unittest.TestCase):
    def test_deep_expansion_five_levels(self):
        """Expand 5 levels deep; only the deepest leaf is real work —
        every container derives done when its children complete."""
        g = Graph()
        seq = 0
        commit(g, g.create_task("L0"), seq := seq + 1)
        parent = "l0"
        for level in range(1, 6):  # l1..l5
            commit(g, g.expand(parent, [{"title": f"L{level}"}]), seq := seq + 1)
            parent = f"l{level}"
        # containers reject direct verification by design
        with self.assertRaises(GraphError):
            g.verify_pass("l4")
        # verify the single leaf
        commit(g, g.start("l5"), seq := seq + 1)
        commit(g, g.verify_pass("l5"), seq := seq + 1)
        # every ancestor derives done
        for level in range(4, -1, -1):
            self.assertEqual(g.tasks[f"l{level}"].effective_status(g.tasks), STATUS_DONE)
        self.assertEqual(progress(g)["done"], 6)

    def test_expansion_cycle_attempts_rejected(self):
        g = Graph()
        commit(g, g.create_task("A"), 1)
        commit(g, g.expand("a", [{"title": "B"}]), 2)
        commit(g, g.expand("b", [{"title": "C"}]), 3)
        # b depends on a (a -> b); adding b -> a would create a cycle
        with self.assertRaises(GraphError):
            g.add_dependency("b", "a")
        # a task cannot be its own dependency
        with self.assertRaises(GraphError):
            g.add_dependency("c", "c")

    def test_replay_100k_events(self):
        n = 100_000
        events = []
        # 50k tasks in dependency chains + 50k transitions
        for i in range(1, 50_001):
            events.append({"op": "task_created", "seq": 2 * i - 1, "ts": "t",
                           "id": f"t{i}", "title": f"Task {i}",
                           "description": "", "acceptance": [], "files": [], "notes": [],
                           "priority": "medium"})
            events.append({"op": "task_started", "seq": 2 * i, "ts": "t", "id": f"t{i}"})
        t0 = time.perf_counter()
        g = Graph.from_events(events)
        fold_s = time.perf_counter() - t0
        self.assertEqual(len(g.tasks), 50_000)
        self.assertEqual(g.tasks["t50000"].status, "in_progress")
        self.assertLess(fold_s, 30, f"fold took {fold_s:.1f}s — suspiciously slow")
        print(f"\n[stress] folded {n} events in {fold_s:.2f}s")

        # store-level: write + read + fold
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            store.init()
            store.append(events[:50_000])
            store.append(events[50_000:])
            t0 = time.perf_counter()
            store2, g2 = load_project(tmp)
            load_s = time.perf_counter() - t0
            self.assertEqual(len(g2.tasks), 50_000)
            self.assertLess(load_s, 30, f"disk load took {load_s:.1f}s")
            print(f"[stress] disk round-trip of {n} events in {load_s:.2f}s")

    def test_concurrent_agents_append_atomically(self):
        """5 agents x 100 events each, interleaved through the shared log."""
        n_agents, per_agent = 5, 100
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            store.init()
            errors: list[Exception] = []

            def agent(aid: int):
                try:
                    g = Graph()
                    for i in range(per_agent):
                        tid = f"a{aid}_t{i}"
                        ev = g.create_task(f"Agent {aid} Task {i}", id=tid)
                        g.apply(store.append([ev])[0])
                        if i > 0:
                            ev = g.add_dependency(tid, f"a{aid}_t{i - 1}")
                            g.apply(store.append([ev])[0])
                except Exception as e:  # pragma: no cover
                    errors.append(e)

            threads = [threading.Thread(target=agent, args=(a,)) for a in range(n_agents)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])

            events = store.read_events()
            # per agent: 100 creates + 99 deps (first task has no predecessor)
            self.assertEqual(len(events), n_agents * (per_agent * 2 - 1))
            seqs = [e["seq"] for e in events]
            self.assertEqual(len(set(seqs)), len(seqs), "duplicate seqs under concurrency")
            self.assertEqual(sorted(seqs), list(range(1, len(seqs) + 1)))
            g = Graph.from_events(events)
            self.assertEqual(len(g.tasks), n_agents * per_agent)
            self.assertEqual(g.problems(), [])

    def test_merge_two_independent_projects(self):
        k1 = Kernel(tempfile.mkdtemp())
        k2 = Kernel(tempfile.mkdtemp())
        k1.create_task("Alpha")
        k1.create_task("Beta")
        k1.add_dependency("beta", "alpha")
        k2.create_task("Gamma")
        stats = k1.import_events(k2.export_events())
        self.assertEqual(stats["tasks"], 3)
        self.assertEqual(set(k1.graph.tasks), {"alpha", "beta", "gamma"})
        self.assertEqual(k1.graph.problems(), [])

    def test_overlapping_planner_work_conflicts(self):
        """Two planners propose the same task id: second proposal rejected."""
        k1 = Kernel(tempfile.mkdtemp())
        k1.create_task("Renderer")            # renderer
        k1.create_task("Renderer")            # slug deduped -> renderer-2, no conflict
        self.assertEqual(len(k1.graph.tasks), 2)
        with self.assertRaises(GraphError):
            k1.create_task("Renderer", id="renderer")  # explicit duplicate id -> conflict
        self.assertEqual(len(k1.graph.tasks), 2)      # rejected proposal wrote nothing


if __name__ == "__main__":
    unittest.main()
