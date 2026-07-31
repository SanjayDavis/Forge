import unittest

from forge.model import Graph
from forge.query import QueryError, run_query


class QueryTest(unittest.TestCase):
    def commit(self, g, ev):
        g.seq += 1
        ev = dict(ev)
        ev["seq"] = g.seq
        ev.setdefault("ts", "2026-07-31T12:00:00+00:00")
        g.apply(ev)
        return ev

    def make(self):
        g = Graph()
        self.commit(g, g.create_task("Renderer", priority="high", files=["render.py"]))
        self.commit(g, g.expand("renderer", [
            {"title": "Camera", "priority": "high"},
            {"title": "UI", "priority": "medium"},
            {"title": "Lighting", "priority": "low"},
        ]))
        self.commit(g, g.create_task("Input", priority="medium"))
        self.commit(g, g.start("camera"))
        self.commit(g, g.verify_pass("camera"))
        self.commit(g, g.start("ui"))
        self.commit(g, g.verify_fail("ui", "flickers"))
        self.commit(g, g.add_evidence("ui", "hard", "unittest", "2 fail"))
        return g

    def q(self, g, expr):
        return run_query(g, expr)

    def test_status_filter(self):
        g = self.make()
        self.assertEqual(self.q(g, "status == done"), ["camera"])
        self.assertEqual(self.q(g, "status == needs_revision"), ["ui"])

    def test_priority_compare(self):
        g = self.make()
        self.assertEqual(set(self.q(g, "priority == high")), {"renderer", "camera"})
        self.assertEqual(set(self.q(g, "priority > medium")), {"renderer", "camera"})
        self.assertEqual(self.q(g, "priority == low"), ["lighting"])

    def test_title_contains(self):
        g = self.make()
        self.assertEqual(self.q(g, '"render" in title'), ["renderer"])
        self.assertEqual(self.q(g, '"e" in id and not container'), ["camera"])

    def test_boolean_composition(self):
        g = self.make()
        self.assertEqual(self.q(g, "status == needs_revision and evidence_count >= 1"), ["ui"])
        self.assertEqual(self.q(g, "status == todo or status == needs_revision"),
                         ["ui", "lighting", "input"])

    def test_derived_blocked(self):
        g = self.make()
        self.assertEqual(self.q(g, "blocked"), ["renderer"])  # ui unfinished blocks container
        self.assertNotIn("ui", self.q(g, "blocked"))  # ui has no deps

    def test_membership_with_functions(self):
        g = self.make()
        self.assertEqual(self.q(g, "id in children(renderer)"), ["camera", "ui", "lighting"])
        self.assertEqual(self.q(g, "id in parents(camera)"), ["renderer"])

    def test_call_forms(self):
        g = self.make()
        self.assertEqual(self.q(g, "blockers(renderer)"), ["ui", "lighting"])
        self.assertEqual(self.q(g, "children(renderer)"), ["camera", "ui", "lighting"])
        self.assertEqual(self.q(g, "parents(renderer)"), [])
        self.assertEqual(len(self.q(g, "evidence(ui)")), 1)
        self.assertTrue(self.q(g, "evidence(ui)")[0].startswith("[hard]"))
        self.assertEqual(self.q(g, "ready()"), ["input", "lighting"])

    def test_bare_words_are_strings(self):
        g = self.make()
        self.assertEqual(self.q(g, "status == needs_revision"), ["ui"])

    def test_no_matches(self):
        g = self.make()
        self.assertEqual(self.q(g, "status == done and priority == low"), [])

    def test_safety_rejects_escapes(self):
        g = self.make()
        bad = [
            "t.__class__",
            "title.__class__",
            "len(acceptance)",
            "acceptance[0]",
            "lambda: 1",
            "open('x')",
            "id if id else 1",
            "1 + 1",
        ]
        for expr in bad:
            with self.assertRaises(QueryError, msg=expr):
                self.q(g, expr)

    def test_unknown_function_rejected(self):
        g = self.make()
        with self.assertRaises(QueryError):
            self.q(g, "explode(renderer)")
        with self.assertRaises(QueryError):
            self.q(g, "blockers(ghost)")


if __name__ == "__main__":
    unittest.main()
