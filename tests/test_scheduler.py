import unittest

from pkernel.model import Graph
from pkernel.scheduler import blockers, next_task, progress, ready_tasks


class SchedulerTest(unittest.TestCase):
    def commit(self, g, ev):
        g.seq += 1
        ev = dict(ev)
        ev["seq"] = g.seq
        ev.setdefault("ts", "2026-07-31T12:00:00+00:00")
        g.apply(ev)
        return ev

    def test_ready_excludes_blocked_and_containers(self):
        g = Graph()
        self.commit(g, g.create_task("A"))
        self.commit(g, g.create_task("B"))
        self.commit(g, g.create_task("C"))
        self.commit(g, g.add_dependency("b", "a"))
        self.commit(g, g.expand("c", [{"title": "C1"}]))
        ready = {t.id for t in ready_tasks(g)}
        self.assertEqual(ready, {"a", "c1"})  # b blocked by a; c is a container

    def test_ready_after_dep_done(self):
        g = Graph()
        self.commit(g, g.create_task("A"))
        self.commit(g, g.create_task("B"))
        self.commit(g, g.add_dependency("b", "a"))
        self.commit(g, g.start("a"))
        self.commit(g, g.verify_pass("a"))
        self.assertEqual(next_task(g).id, "b")
        self.commit(g, g.start("b"))
        self.assertEqual(next_task(g), None)

    def test_ready_ordering_by_creation(self):
        g = Graph()
        self.commit(g, g.create_task("Z"))
        self.commit(g, g.create_task("A"))
        self.commit(g, g.create_task("M"))
        self.assertEqual([t.id for t in ready_tasks(g)], ["z", "a", "m"])

    def test_blockers_direct_and_chain(self):
        g = Graph()
        self.commit(g, g.create_task("A"))
        self.commit(g, g.create_task("B"))
        self.commit(g, g.create_task("C"))
        self.commit(g, g.add_dependency("b", "a"))
        self.commit(g, g.add_dependency("c", "b"))
        self.assertEqual(blockers(g, "c"), ["b"])
        chains = blockers(g, "c", chain=True)
        self.assertEqual(chains, [["c", "b"], ["c", "b", "a"]])
        self.assertEqual(blockers(g, "a"), [])

    def test_blockers_only_incomplete(self):
        g = Graph()
        self.commit(g, g.create_task("A"))
        self.commit(g, g.create_task("B"))
        self.commit(g, g.add_dependency("b", "a"))
        self.commit(g, g.start("a"))
        self.commit(g, g.verify_pass("a"))
        self.assertEqual(blockers(g, "b"), [])

    def test_progress_uses_effective_status(self):
        g = Graph()
        self.commit(g, g.create_task("Root"))
        self.commit(g, g.expand("root", [{"title": "X"}, {"title": "Y"}]))
        self.commit(g, g.start("x"))
        self.commit(g, g.verify_pass("x"))
        p = progress(g)
        # root derives done? no — y still todo. done: x only (1/3)
        self.assertEqual(p["done"], 1)
        self.assertEqual(p["total"], 3)
        # complete y -> root effectively done
        self.commit(g, g.start("y"))
        self.commit(g, g.verify_pass("y"))
        p = progress(g)
        self.assertEqual(p["done"], 3)
        self.assertEqual(p["percent"], 100.0)


if __name__ == "__main__":
    unittest.main()
