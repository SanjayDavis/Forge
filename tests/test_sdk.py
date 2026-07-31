"""Forge SDK test suite — the public interface every client uses.

Proves the boundary the user asked for: a client operating entirely
through forge.ForgeClient / forge.validate_proposal / forge.context_*
needs nothing else. Also proves the Context Contract shape and the
reference (human) client loop.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forge import (
    ForgeClient, GraphError, ProposalError, context_package,
    slugify, validate_proposal,
)
from forge.sdk import to_yaml

REFERENCE_CLIENT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "plugins", "reference", "reference_client.py")


class SdkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.client = ForgeClient(self.dir)

    def tearDown(self):
        self.tmp.cleanup()


class TestNext(SdkTest):
    def test_next_returns_none_on_empty_project(self):
        self.assertIsNone(self.client.next())

    def test_next_returns_snapshot_not_node(self):
        self.client.propose(_proposal("Build a Snake game"))
        t = self.client.next()
        self.assertEqual(set(t), {"id", "title", "description", "status", "priority"})
        self.assertEqual(t["id"], "build-a-snake-game-foundation")
        self.assertEqual(t["status"], "todo")
        self.assertIn(t["priority"], ("low", "medium", "high"))

    def test_next_skips_containers_and_blocked(self):
        self.client.propose(_proposal("Build a Snake game"))
        tid = self.client.next()["id"]
        self.client.start(tid)
        self.client.attach_evidence(tid, "hard", "unittest", "x")
        self.client.verify(tid)
        # next must be the second child, never the container root
        t = self.client.next()
        self.assertEqual(t["id"], "build-a-snake-game-core")
        # root container is never a work item
        self.assertNotEqual(t["id"], "build-a-snake-game")


class TestContextContract(SdkTest):
    def test_context_yaml_has_all_contract_sections(self):
        self.client.propose(_proposal("Build a Snake game"))
        yaml = self.client.context("build-a-snake-game-foundation")
        self.assertTrue(yaml.startswith("Task: build-a-snake-game-foundation"))
        for section in ("Acceptance:", "Dependencies:", "Knowledge:",
                        "Relevant Files:", "Evidence:", "Constraints:"):
            self.assertIn(section, yaml, section)
        self.assertIn("Dependencies: (none", yaml)
        # core depends on foundation: complete foundation first, then the
        # dependency line carries a done marker
        self.client.start("build-a-snake-game-foundation")
        self.client.attach_evidence("build-a-snake-game-foundation",
                                    "hard", "unittest", "x")
        self.client.verify("build-a-snake-game-foundation")
        yaml2 = self.client.context("build-a-snake-game-core")
        self.assertIn("- build-a-snake-game-foundation \u2713 (done)", yaml2)

    def test_context_package_is_canonical_dict(self):
        self.client.propose(_proposal("Build a Snake game"))
        tid = self.client.next()["id"]
        pkg = context_package(self.client.kernel.graph, tid)
        self.assertEqual(set(pkg), {"task", "title", "description", "acceptance",
                                    "dependencies", "knowledge",
                                    "relevant_files", "evidence", "constraints"})
        self.assertIsInstance(to_yaml(pkg), str)

    def test_constraints_come_from_constraint_notes(self):
        self.client.propose(_proposal("Renderer"))
        tid = "renderer-foundation"
        self.client.kernel.add_note(tid, "the camera API exists upstream")
        self.client.kernel.add_note(tid, "constraint: do not modify renderer API")
        pkg = context_package(self.client.kernel.graph, tid)
        self.assertEqual(pkg["knowledge"], ["the camera API exists upstream"])
        self.assertEqual(pkg["constraints"], ["do not modify renderer API"])
        yaml = self.client.context(tid)
        self.assertIn("do not modify renderer API", yaml)


class TestPropose(SdkTest):
    def test_propose_commits_atomically_and_returns_summary(self):
        p = _proposal("Build a Snake game")
        result = self.client.propose(p)
        self.assertEqual(result["proposal_id"], p["proposal_id"])
        self.assertEqual(result["committed"], 4)
        self.assertEqual(result["tasks"], 4)
        events = self.client.kernel.store.read_events()
        self.assertEqual([e["seq"] for e in events], [1, 2, 3, 4])

    def test_propose_rejects_bad_envelope_before_kernel(self):
        p = _proposal("Build a Snake game")
        p["events"][0]["seq"] = 99
        with self.assertRaises(ProposalError):
            self.client.propose(p)
        self.assertEqual(len(self.client.kernel.store.read_events()), 0,
                         "protocol violations must never reach the log")

    def test_propose_rejects_duplicate_whole(self):
        self.client.propose(_proposal("Build a Snake game"))
        before = len(self.client.kernel.store.read_events())
        with self.assertRaises(GraphError):
            self.client.propose(_proposal("Build a Snake game"))
        self.assertEqual(len(self.client.kernel.store.read_events()), before)

    def test_validate_proposal_is_public(self):
        validate_proposal(_proposal("X"))  # no raise
        bad = _proposal("X")
        bad["confidence"] = 1.5
        with self.assertRaises(ProposalError):
            validate_proposal(bad)

    def test_slugify_is_public(self):
        self.assertEqual(slugify("Build a Snake game"), "build-a-snake-game")


class TestExecutorFlow(SdkTest):
    def test_start_evidence_verify_roundtrip(self):
        self.client.propose(_proposal("Build a Snake game"))
        tid = self.client.next()["id"]
        self.client.start(tid)
        # starting a task blocks its dependents until it passes verification
        self.assertIsNone(self.client.next())
        self.client.attach_evidence(tid, "hard", "unittest", "9 assertions")
        ev = self.client.verify(tid)
        self.assertEqual(ev["op"], "verification_passed")
        self.assertEqual(self.client.kernel.task(tid).status, "done")
        # with the dependency done, the next child becomes ready
        self.assertEqual(self.client.next()["id"], "build-a-snake-game-core")

    def test_verify_gate_blocks_todo_task(self):
        self.client.propose(_proposal("Build a Snake game"))
        tid = self.client.next()["id"]
        with self.assertRaises(GraphError):
            self.client.verify(tid)  # never started: I6 status gate
        self.assertEqual(self.client.kernel.task(tid).status, "todo")

    def test_verify_fail_sets_needs_revision(self):
        self.client.propose(_proposal("Build a Snake game"))
        tid = self.client.next()["id"]
        self.client.start(tid)
        self.client.verify_fail(tid, "movement handler misses edge cases")
        t = self.client.kernel.task(tid)
        self.assertEqual(t.status, "needs_revision")
        self.assertIn("edge cases", t.last_failure)

    def test_query_and_progress_are_pass_throughs(self):
        self.client.propose(_proposal("Build a Snake game"))
        self.assertEqual(len(self.client.query("status == todo")), 3)
        self.assertEqual(self.client.progress()["total"], 4)


class TestReferenceClient(unittest.TestCase):
    def test_human_loop_completes_project(self):
        d = tempfile.mkdtemp()
        env = dict(os.environ, PYTHONPATH=os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        subprocess.run(["forge", "-d", d, "init"], check=True,
                       capture_output=True, text=True, env=env)
        p = _proposal("Build a Snake game")
        with open(os.path.join(d, "prop.json"), "w", encoding="utf-8") as f:
            json.dump(p, f)
        subprocess.run(["forge", "-d", d, "propose", os.path.join(d, "prop.json")],
                       check=True, capture_output=True, text=True, env=env)
        r = subprocess.run(["python", REFERENCE_CLIENT, "-d", d, "--auto"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("nothing ready", r.stdout)
        self.assertEqual(r.stdout.count("verified:"), 3)
        g = ForgeClient(d).kernel.graph
        self.assertTrue(all(t.effective_status(g.tasks) == "done"
                            for t in g.tasks.values()))


def _proposal(goal: str, children=None) -> dict:
    """A proposal the kernel will accept, shaped exactly like
    ReferencePlanner output (which lives in plugins/ and is tested
    separately)."""
    from forge import slugify
    root = slugify(goal)
    if children is None:
        children = [{"title": f"{goal} — {m}"} for m in ("Foundation", "Core", "Acceptance")]
    child_ids = []
    existing = {root}
    for c in children:
        base = slugify(c["title"])
        cand, n = base, 2
        while cand in existing:
            cand = f"{base}-{n}"
            n += 1
        existing.add(cand)
        child_ids.append(cand)
    events = [{"op": "task_created", "id": root, "title": goal,
               "description": "", "acceptance": [], "files": [], "notes": [],
               "priority": "medium"}]
    events.append({"op": "task_expanded", "task": root,
                   "children": [{"id": cid, "title": c["title"],
                                 "description": "", "acceptance": [],
                                 "files": [], "priority": "medium"}
                                for cid, c in zip(child_ids, children)]})
    for i in range(1, len(child_ids)):
        events.append({"op": "dependency_added", "task": child_ids[i],
                       "depends_on": child_ids[i - 1]})
    return {"proposal_id": f"prop_{root[:20]}_abcd1234",
            "reason": f"Decompose '{goal}'", "confidence": 0.9,
            "events": events}


if __name__ == "__main__":
    unittest.main()
