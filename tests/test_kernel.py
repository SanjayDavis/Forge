import json
import tempfile
import unittest

from forge.kernel import Kernel
from forge.model import GraphError, STATUS_DONE, STATUS_IN_PROGRESS, STATUS_TODO


class KernelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.k = Kernel(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_official_api_lifecycle(self):
        self.k.create_task("A", priority="high")
        self.k.create_task("B")
        self.k.add_dependency("b", "a")
        self.k.start("a")
        self.k.add_evidence("a", "hard", "unittest", "3 passed")
        self.k.verify_pass("a")
        self.assertEqual(self.k.task("a").status, STATUS_DONE)
        self.assertEqual(self.k.task("b").status, STATUS_TODO)
        self.assertEqual(self.k.next(), "b")
        # every mutation went through the log
        self.assertEqual(len(self.k.store.read_events()), 6)

    def test_kernel_rejects_invalid_proposals(self):
        self.k.create_task("A")
        with self.assertRaises(GraphError):
            self.k.start("ghost")
        self.k.start("a")
        with self.assertRaises(GraphError):
            self.k.start("a")  # already started
        # nothing was written for rejected proposals
        self.assertEqual(len(self.k.store.read_events()), 2)

    def test_priority_roundtrip_and_update(self):
        self.k.create_task("A", priority="low")
        self.assertEqual(self.k.task("a").priority, "low")
        self.k.update_task("a", priority="high")
        self.assertEqual(self.k.task("a").priority, "high")
        with self.assertRaises(GraphError):
            self.k.create_task("B", priority="urgent")

    def test_history_tracks_task_timeline(self):
        self.k.create_task("A")
        self.k.start("a")
        self.k.verify_fail("a", "broken")
        self.k.add_evidence("a", "soft", "review", "ok")
        self.k.retry("a")
        self.k.verify_pass("a")
        ops = [ev["op"] for ev in self.k.history("a")]
        self.assertEqual(ops, ["task_created", "task_started", "verification_failed",
                               "evidence_added", "task_retried", "verification_passed"])

    def test_history_includes_expansion(self):
        self.k.create_task("P")
        self.k.expand("p", [{"title": "C"}])
        ops = [ev["op"] for ev in self.k.history("c")]
        self.assertEqual(ops, ["task_expanded"])  # c created via parent expansion
        ops_p = [ev["op"] for ev in self.k.history("p")]
        self.assertEqual(ops_p, ["task_created", "task_expanded"])

    def test_inspect_fields(self):
        self.k.create_task("Renderer", "draws", acceptance=["renders"], files=["render.py"])
        self.k.expand("renderer", [{"title": "Camera", "acceptance": ["follows"]}])
        self.k.start("camera")
        self.k.verify_pass("camera")
        info = self.k.inspect("renderer")
        self.assertEqual(info["status"], STATUS_DONE)  # derived from child
        self.assertEqual(info["completion"], 100)
        self.assertEqual(info["children"][0]["id"], "camera")
        self.assertTrue(info["container"])
        self.assertEqual(info["history"][0]["op"], "task_created")
        self.assertEqual(info["history"][1]["op"], "task_expanded")
        self.assertIn("render.py", info["produces"])

    def test_inspect_leaf_completion(self):
        self.k.create_task("A")
        info = self.k.inspect("a")
        self.assertEqual(info["completion"], 0)
        self.assertEqual(info["completion_text"], "not started")
        self.k.start("a")
        self.k.verify_pass("a")
        info = self.k.inspect("a")
        self.assertEqual(info["completion"], 100)

    def test_undo_via_kernel_refolds(self):
        self.k.create_task("A")
        self.k.create_task("B")
        self.k.add_dependency("b", "a")
        removed = self.k.undo(1)
        self.assertEqual(removed[0]["op"], "dependency_added")
        self.assertEqual(self.k.task("b").depends_on, [])

    def test_export_import_roundtrip(self):
        self.k.create_task("A", priority="high", acceptance=["x"])
        self.k.create_task("B")
        self.k.add_dependency("b", "a")
        payload = json.loads(self.k.to_export_json())
        k2 = Kernel(tempfile.mkdtemp())
        stats = k2.import_events(payload)
        self.assertEqual(stats["imported"], 3)
        self.assertEqual(set(k2.graph.tasks), {"a", "b"})
        self.assertEqual(k2.task("a").priority, "high")
        self.assertEqual(k2.task("b").depends_on, ["a"])

    def test_merge_conflict_rejected(self):
        self.k.create_task("A")
        k2 = Kernel(tempfile.mkdtemp())
        k2.create_task("A")
        with self.assertRaises(GraphError):
            self.k.import_events(k2.export_events())

    def test_import_validates_incoming_log(self):
        with self.assertRaises(GraphError):
            self.k.import_events([{"op": "task_started", "id": "ghost"}])  # unknown op shape
        self.assertEqual(len(self.k.store.read_events()), 0)

    def test_replay_via_kernel(self):
        self.k.create_task("A")
        self.k.start("a")
        stats = self.k.replay()
        self.assertEqual(stats["events"], 2)
        self.assertEqual(stats["tasks"], 1)
        self.assertEqual(stats["done"], 0)


if __name__ == "__main__":
    unittest.main()
