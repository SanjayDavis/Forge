import unittest

from pkernel.model import Graph, GraphError, STATUS_DONE, STATUS_IN_PROGRESS, STATUS_NEEDS_REVISION, STATUS_TODO

T = "2026-07-31T12:00:00+00:00"


class GraphTest(unittest.TestCase):
    def commit(self, g, ev):
        g.seq += 1
        ev = dict(ev)
        ev["seq"] = g.seq
        ev.setdefault("ts", T)
        g.apply(ev)
        return ev

    def test_create_and_fold(self):
        g = Graph()
        evs = []
        evs.append(self.commit(g, g.create_task("A")))
        evs.append(self.commit(g, g.create_task("B", id="b")))
        evs.append(self.commit(g, g.add_dependency("b", "a")))
        self.assertEqual(set(g.tasks), {"a", "b"})
        self.assertEqual(g.tasks["b"].depends_on, ["a"])
        # fold from events reproduces the same graph
        g2 = Graph.from_events(evs)
        self.assertEqual(g2.tasks["b"].depends_on, ["a"])
        self.assertEqual(g2.tasks["b"].created_seq, 2)

    def test_id_slug_and_dedupe(self):
        g = Graph()
        self.commit(g, g.create_task("Renderer"))
        self.commit(g, g.create_task("Renderer"))
        self.commit(g, g.create_task("Renderer"))
        self.assertEqual(list(g.tasks), ["renderer", "renderer-2", "renderer-3"])

    def test_reject_duplicate_id(self):
        g = Graph()
        self.commit(g, g.create_task("A", id="a"))
        with self.assertRaises(GraphError):
            g.create_task("B", id="a")

    def test_lifecycle_transitions(self):
        g = Graph()
        self.commit(g, g.create_task("A"))
        self.commit(g, g.start("a"))
        self.assertEqual(g.tasks["a"].status, STATUS_IN_PROGRESS)
        self.commit(g, g.verify_fail("a", "tests broken"))
        self.assertEqual(g.tasks["a"].status, STATUS_NEEDS_REVISION)
        self.assertEqual(g.tasks["a"].last_failure, "tests broken")
        self.commit(g, g.retry("a"))
        self.assertEqual(g.tasks["a"].status, STATUS_IN_PROGRESS)
        self.assertIsNone(g.tasks["a"].last_failure)
        self.commit(g, g.verify_pass("a"))
        self.assertEqual(g.tasks["a"].status, STATUS_DONE)
        self.commit(g, g.reopen("a"))
        self.assertEqual(g.tasks["a"].status, STATUS_IN_PROGRESS)

    def test_illegal_transitions_raise(self):
        g = Graph()
        self.commit(g, g.create_task("A"))
        self.commit(g, g.start("a"))
        with self.assertRaises(GraphError):  # start twice
            g.start("a")
        with self.assertRaises(GraphError):  # retry without failure
            g.retry("a")
        with self.assertRaises(GraphError):  # verify-fail without reason
            g.verify_fail("a", "")
        self.commit(g, g.verify_pass("a"))
        with self.assertRaises(GraphError):  # start a done task
            g.start("a")
        with self.assertRaises(GraphError):  # fail a done task
            g.verify_fail("a", "nope")
        self.commit(g, g.reopen("a"))
        with self.assertRaises(GraphError):  # reopen a non-done task
            g.reopen("a")

    def test_unknown_task_raises(self):
        g = Graph()
        with self.assertRaises(GraphError):
            g.start("ghost")

    def test_cycle_rejected(self):
        g = Graph()
        self.commit(g, g.create_task("A"))
        self.commit(g, g.create_task("B"))
        self.commit(g, g.create_task("C"))
        self.commit(g, g.add_dependency("b", "a"))
        self.commit(g, g.add_dependency("c", "b"))
        with self.assertRaises(GraphError):
            g.add_dependency("a", "c")
        with self.assertRaises(GraphError):
            g.add_dependency("a", "a")

    def test_verify_requires_deps_done(self):
        g = Graph()
        self.commit(g, g.create_task("A"))
        self.commit(g, g.create_task("B"))
        self.commit(g, g.add_dependency("b", "a"))
        self.commit(g, g.start("a"))
        self.commit(g, g.start("b"))
        with self.assertRaises(GraphError):
            g.verify_pass("b")
        self.commit(g, g.verify_pass("a"))
        self.commit(g, g.verify_pass("b"))  # now fine

    def test_verify_force_bypasses_deps(self):
        g = Graph()
        self.commit(g, g.create_task("A"))
        self.commit(g, g.create_task("B"))
        self.commit(g, g.add_dependency("b", "a"))
        self.commit(g, g.start("a"))
        self.commit(g, g.start("b"))
        self.commit(g, g.verify_pass("b", force=True))
        self.assertEqual(g.tasks["b"].status, STATUS_DONE)

    def test_expand_makes_container(self):
        g = Graph()
        self.commit(g, g.create_task("Renderer"))
        self.commit(g, g.expand("renderer", [{"title": "Camera"}, {"title": "UI"}, {"title": "Lighting"}]))
        r = g.tasks["renderer"]
        self.assertTrue(r.composite)
        self.assertEqual(set(r.depends_on), {"camera", "ui", "lighting"})
        self.assertEqual(r.status, STATUS_IN_PROGRESS)  # expansion = work started
        # children are ready immediately (no deps) and container is not a work item
        from pkernel.scheduler import ready_tasks, is_container
        self.assertTrue(is_container(r))
        self.assertEqual({t.id for t in ready_tasks(g)}, {"camera", "ui", "lighting"})

    def test_container_completes_when_children_done(self):
        g = Graph()
        self.commit(g, g.create_task("Renderer"))
        self.commit(g, g.expand("renderer", [{"title": "Camera"}, {"title": "UI"}]))
        for cid in ("camera", "ui"):
            self.commit(g, g.start(cid))
            self.commit(g, g.verify_pass(cid))
        self.assertEqual(g.tasks["renderer"].effective_status(g.tasks), STATUS_DONE)
        # cannot verify a container directly
        with self.assertRaises(GraphError):
            g.verify_pass("renderer")

    def test_expand_rejected_on_done_task(self):
        g = Graph()
        self.commit(g, g.create_task("A"))
        self.commit(g, g.start("a"))
        self.commit(g, g.verify_pass("a"))
        with self.assertRaises(GraphError):
            g.expand("a", [{"title": "B"}])

    def test_delete_strips_edges_and_rejects_dependents(self):
        g = Graph()
        self.commit(g, g.create_task("A"))
        self.commit(g, g.create_task("B"))
        self.commit(g, g.add_dependency("b", "a"))
        with self.assertRaises(GraphError):
            g.delete("a")
        self.commit(g, g.delete("b"))
        self.assertNotIn("b", g.tasks)
        self.assertEqual(g.tasks["a"].depends_on, [])
        # delete with children rejected
        g2 = Graph()
        self.commit(g2, g2.create_task("P"))
        self.commit(g2, g2.expand("p", [{"title": "C"}]))
        with self.assertRaises(GraphError):
            g2.delete("p")

    def test_evidence_kinds_and_notes(self):
        g = Graph()
        self.commit(g, g.create_task("A"))
        self.commit(g, g.add_evidence("a", "hard", "unittest", "14 passed"))
        self.commit(g, g.add_evidence("a", "soft", "peer review", "looks good"))
        self.commit(g, g.add_note("a", "remember to profile"))
        self.assertEqual([e.kind for e in g.tasks["a"].evidence], ["hard", "soft"])
        self.assertEqual(g.tasks["a"].notes, ["remember to profile"])
        with self.assertRaises(GraphError):
            g.add_evidence("a", "meh", "x")
        with self.assertRaises(GraphError):
            g.add_evidence("a", "hard", "")

    def test_update_replaces_lists(self):
        g = Graph()
        self.commit(g, g.create_task("A", acceptance=["one"], files=["a.py"]))
        self.commit(g, g.update_task("a", title="A2", acceptance=["two"]))
        self.assertEqual(g.tasks["a"].title, "A2")
        self.assertEqual(g.tasks["a"].acceptance, ["two"])
        self.assertEqual(g.tasks["a"].files, ["a.py"])  # untouched

    def test_remove_dependency(self):
        g = Graph()
        self.commit(g, g.create_task("A"))
        self.commit(g, g.create_task("B"))
        self.commit(g, g.add_dependency("b", "a"))
        self.commit(g, g.remove_dependency("b", "a"))
        self.assertEqual(g.tasks["b"].depends_on, [])
        with self.assertRaises(GraphError):
            g.remove_dependency("b", "a")

    def test_validate_graph_finds_problems(self):
        g = Graph()
        self.commit(g, g.create_task("A"))
        self.commit(g, g.create_task("B"))
        self.commit(g, g.add_dependency("b", "a"))
        self.assertEqual(g.problems(), [])
        # corrupt: dangling dep + self-dep
        g.tasks["b"].depends_on.append("ghost")
        g.tasks["a"].depends_on.append("a")
        probs = g.problems()
        self.assertTrue(any("ghost" in p for p in probs))
        self.assertTrue(any("self-dependency" in p for p in probs))


if __name__ == "__main__":
    unittest.main()
