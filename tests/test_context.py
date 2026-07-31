import json
import unittest

from pkernel.context import build_context, to_json, to_markdown
from pkernel.model import Graph


class ContextTest(unittest.TestCase):
    def commit(self, g, ev):
        g.seq += 1
        ev = dict(ev)
        ev["seq"] = g.seq
        ev.setdefault("ts", "2026-07-31T12:00:00+00:00")
        g.apply(ev)
        return ev

    def make(self):
        g = Graph()
        self.commit(g, g.create_task("Renderer", "Draws the board", acceptance=["renders"],
                                    files=["render.py"]))
        self.commit(g, g.create_task("Camera", acceptance=["follows"]))
        self.commit(g, g.add_dependency("renderer", "camera"))
        self.commit(g, g.start("camera"))
        self.commit(g, g.verify_pass("camera"))
        self.commit(g, g.start("renderer"))
        self.commit(g, g.add_evidence("renderer", "hard", "unittest", "3 passed"))
        self.commit(g, g.add_evidence("renderer", "soft", "review", "ok"))
        self.commit(g, g.add_note("renderer", "profile later"))
        return g

    def test_context_fields(self):
        ctx = build_context(self.make(), "renderer")
        self.assertEqual(ctx["id"], "renderer")
        self.assertEqual(ctx["status"], "in_progress")
        self.assertEqual(ctx["acceptance"], ["renders"])
        self.assertEqual(ctx["files"], ["render.py"])
        self.assertEqual(ctx["dependencies"][0]["id"], "camera")
        self.assertTrue(ctx["dependencies"][0]["done"])
        self.assertEqual(ctx["blockers"], [])
        self.assertEqual([e["kind"] for e in ctx["evidence"]], ["hard", "soft"])
        self.assertEqual(ctx["notes"], ["profile later"])
        self.assertEqual(ctx["project"]["done"], 1)

    def test_markdown_sections(self):
        md = to_markdown(build_context(self.make(), "renderer"))
        for section in ("# renderer", "Acceptance criteria", "Files", "Dependencies",
                        "Blockers", "Evidence", "Project"):
            self.assertIn(section, md)
        self.assertIn("[HARD] unittest", md)
        self.assertIn("[soft] review", md)

    def test_json_roundtrip(self):
        raw = to_json(build_context(self.make(), "renderer"))
        data = json.loads(raw)
        self.assertEqual(data["title"], "Renderer")

    def test_context_blocks(self):
        ctx = build_context(self.make(), "camera")
        self.assertEqual(ctx["blocks"][0]["id"], "renderer")


if __name__ == "__main__":
    unittest.main()
