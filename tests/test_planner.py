"""M2B planner test suite — the first untrusted client of Forge.

Tests the Planner Protocol boundary (SPEC §9) from both sides:

  Valid proposals:      ReferencePlanner output is spec-shaped, carries
                        no seq, predicts kernel-derived ids, commits
                        atomically through the kernel, and the planner
                        itself never touches the graph.

  Invalid proposals:    envelope violations and §9.6 violations are
                        rejected by validate_proposal; semantic
                        violations (unknown tasks, cycles, bad
                        priority, atomicity) are rejected by the kernel
                        on commit — with nothing partially committed.

The kernel is the authority. These tests assert its verdicts.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "packages", "forge-planner"))

from forge import ForgeClient, GraphError, ProposalError, slugify, validate_proposal
from forge.kernel import Kernel
from forge_planner import ALLOWED_OPS, ReferencePlanner

PLANNER_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "packages", "forge-planner",
                           "forge_planner", "planner.py")


def _fresh_kernel() -> Kernel:
    d = tempfile.mkdtemp()
    return Kernel(d)


class TestValidProposals(unittest.TestCase):
    def test_plan_output_is_spec_shaped(self):
        p = ReferencePlanner().plan("Build a Snake game")
        self.assertEqual(
            set(p), {"proposal_id", "reason", "confidence", "events"})
        self.assertRegex(p["proposal_id"], r"^prop_[a-z0-9-]+_[0-9a-f]{8}$")
        self.assertIsInstance(p["reason"], str)
        self.assertTrue(p["reason"])
        self.assertIsInstance(p["confidence"], float)
        self.assertTrue(0.0 <= p["confidence"] <= 1.0)
        self.assertIsInstance(p["events"], list)
        self.assertTrue(p["events"])

    def test_plan_emits_only_allowed_ops_without_seq(self):
        p = ReferencePlanner().plan("Build a Snake game")
        for ev in p["events"]:
            self.assertIn(ev["op"], ALLOWED_OPS)
            self.assertNotIn("seq", ev, "kernel stamps seq, never the planner (§9.4)")

    def test_default_decomposition_matches_kernel_id_derivation(self):
        goal = "Build a Snake game"
        p = ReferencePlanner().plan(goal)
        ops = [ev["op"] for ev in p["events"]]
        self.assertEqual(ops[0], "task_created")
        self.assertEqual(ops[1], "task_expanded")
        root = p["events"][0]["id"]
        self.assertEqual(root, slugify(goal))
        children = p["events"][1]["children"]
        self.assertEqual(len(children), 3)
        expected_ids = [c["id"] for c in children]
        self.assertEqual(expected_ids, [slugify(c["title"]) for c in children])

        # dependency chain: Foundation -> Core -> Acceptance
        deps = [ev for ev in p["events"] if ev["op"] == "dependency_added"]
        self.assertEqual([ev["task"] for ev in deps], expected_ids[1:])
        self.assertEqual([ev["depends_on"] for ev in deps], expected_ids[:-1])

    def test_plan_commits_atomically_through_kernel(self):
        k = _fresh_kernel()
        p = ReferencePlanner().plan("Build a Snake game")
        result = k.import_events(p["events"])
        self.assertEqual(result["imported"], len(p["events"]))
        g = k.graph
        self.assertIn(p["events"][0]["id"], g.tasks)
        self.assertEqual(len(g.tasks), 1 + 3)  # root + 3 children
        # children exist and carry the chain
        children = p["events"][1]["children"]
        expected_ids = [c["id"] for c in children]
        for cid in expected_ids:
            self.assertIn(cid, g.tasks)
        # seqs stamped contiguously from 1
        events = k.store.read_events()
        self.assertEqual([e["seq"] for e in events], list(range(1, len(events) + 1)))

    def test_plan_commits_twice_without_id_collision(self):
        """Two proposals for the same goal on the same project must not
        collide: the second is a separate subgraph (kernel re-derives ids)."""
        k = _fresh_kernel()
        p1 = ReferencePlanner().plan("Build a Snake game")
        p2 = ReferencePlanner().plan("Build a Snake game")
        k.import_events(p1["events"])
        with self.assertRaises(GraphError):
            k.import_events(p2["events"])  # ids collide — reject whole, by design

    def test_explicit_children_priorities_survive_commit(self):
        k = _fresh_kernel()
        p = ReferencePlanner().plan(
            "Renderer", children=[
                {"title": "Camera", "priority": "high"},
                {"title": "UI", "priority": "low"},
            ], priority="medium")
        k.import_events(p["events"])
        g = k.graph
        self.assertEqual(g.tasks["camera"].priority, "high")
        self.assertEqual(g.tasks["ui"].priority, "low")
        self.assertEqual(g.tasks["renderer"].priority, "medium")

    def test_validate_proposal_accepts_plan_output(self):
        for goal in ("Build a Snake game", "Research paper", "Game engine"):
            validate_proposal(ReferencePlanner().plan(goal))  # no raise

    def test_planner_consumes_only_the_public_sdk(self):
        """Structural: the planner imports ONLY the public SDK — never
        kernel internals. It operates entirely through the public
        interfaces, which is the architectural proof the boundary is
        real. The protocol objects it re-exports ARE the SDK's — one
        definition, no private copy."""
        with open(os.path.normpath(PLANNER_SRC), encoding="utf-8") as f:
            src = f.read()
        for banned in ("forge.kernel", "forge.model", "forge.store",
                       "forge.context", "from .", "import_events", ".graph",
                       "replay(", "Store(", "Kernel("):
            self.assertNotIn(banned, src,
                             f"planner must not reference {banned!r} (§9.1)")
        self.assertIn("from forge import", src, "planner must consume the SDK")
        import forge_planner as fp
        self.assertIs(fp.ProposalError, ProposalError,
                      "the planner must not duplicate the protocol")
        self.assertIs(fp.validate_proposal, validate_proposal)
        p = ReferencePlanner().plan("Build a Snake game")
        self.assertIsInstance(p, dict)

    def test_plan_is_deterministic_for_same_goal(self):
        p1 = ReferencePlanner().plan("Build a Snake game")
        p2 = ReferencePlanner().plan("Build a Snake game")
        self.assertEqual(p1["events"], p2["events"])  # only proposal_id differs


class TestInvalidProposals(unittest.TestCase):
    """Intentionally invalid proposals — envelope (§9.3) and §9.6."""

    def test_missing_envelope_fields_rejected(self):
        for field in ("proposal_id", "reason", "confidence", "events"):
            p = ReferencePlanner().plan("Build a Snake game")
            del p[field]
            with self.assertRaises(ProposalError, msg=field):
                validate_proposal(p)

    def test_empty_events_rejected(self):
        p = ReferencePlanner().plan("Build a Snake game")
        p["events"] = []
        with self.assertRaises(ProposalError):
            validate_proposal(p)
        p["events"] = "not-a-list"
        with self.assertRaises(ProposalError):
            validate_proposal(p)

    def test_confidence_out_of_range_rejected(self):
        for bad in (1.5, -0.1, "high", True, None):
            p = ReferencePlanner().plan("Build a Snake game")
            p["confidence"] = bad
            with self.assertRaises(ProposalError, msg=repr(bad)):
                validate_proposal(p)

    def test_plan_rejects_bad_inputs(self):
        with self.assertRaises(ProposalError):
            ReferencePlanner().plan("   ")
        with self.assertRaises(ProposalError):
            ReferencePlanner().plan("OK", confidence=2.0)
        with self.assertRaises(ProposalError):
            ReferencePlanner().plan("OK", priority="urgent")

    def test_pre_stamped_seq_rejected(self):
        """The planner must not stamp seqs — the kernel owns them (§9.4)."""
        p = ReferencePlanner().plan("Build a Snake game")
        p["events"][0]["seq"] = 42
        with self.assertRaises(ProposalError):
            validate_proposal(p)

    def test_executor_ops_rejected(self):
        """Verification/execution events are not the planner's domain (§9.6)."""
        p = ReferencePlanner().plan("Build a Snake game")
        p["events"].append({"op": "verification_passed", "id": "x"})
        with self.assertRaises(ProposalError):
            validate_proposal(p)

    def test_malformed_events_rejected(self):
        p = ReferencePlanner().plan("Build a Snake game")
        p["events"][0] = {"op": "task_created"}  # missing id/title
        with self.assertRaises(ProposalError):
            validate_proposal(p)
        p = ReferencePlanner().plan("Build a Snake game")
        p["events"][-1] = {"op": "dependency_added", "task": "x"}  # missing depends_on
        with self.assertRaises(ProposalError):
            validate_proposal(p)
        p = ReferencePlanner().plan("Build a Snake game")
        p["events"][1] = {"op": "task_expanded", "task": "r", "children": [{"description": "no title"}]}
        with self.assertRaises(ProposalError):
            validate_proposal(p)
        p = ReferencePlanner().plan("Build a Snake game")
        p["events"].append("not-an-event")
        with self.assertRaises(ProposalError):
            validate_proposal(p)


class TestKernelVerdicts(unittest.TestCase):
    """The kernel is the authority: semantic violations are rejected on
    commit — atomically, with nothing partially written."""

    def test_unknown_task_rejected(self):
        k = _fresh_kernel()
        bad = [{"op": "dependency_added", "task": "ghost", "depends_on": "other-ghost"}]
        with self.assertRaises(GraphError):
            k.import_events(bad)
        self.assertEqual(k.store.read_events(), [])

    def test_cycle_rejected(self):
        k = _fresh_kernel()
        p = ReferencePlanner().plan("Renderer")
        evs = p["events"]
        # append a->b->a cycle on top of the chain
        a, b = evs[2]["task"], evs[2]["depends_on"]
        evs.append({"op": "dependency_added", "task": b, "depends_on": a})
        with self.assertRaises(GraphError):
            k.import_events(evs)
        self.assertEqual(k.store.read_events(), [])

    def test_self_dependency_rejected(self):
        k = _fresh_kernel()
        with self.assertRaises(GraphError):
            k.import_events([{"op": "dependency_added", "task": "x", "depends_on": "x"}])

    def test_expand_unknown_task_rejected(self):
        k = _fresh_kernel()
        with self.assertRaises(GraphError):
            k.import_events([{"op": "task_expanded", "task": "ghost",
                              "children": [{"title": "Child"}]}])

    def test_invalid_priority_rejected(self):
        k = _fresh_kernel()
        p = ReferencePlanner().plan("Build a Snake game")
        p["events"][0]["priority"] = "urgent"
        with self.assertRaises(GraphError):
            k.import_events(p["events"])

    def test_atomicity_whole_or_nothing(self):
        """3 valid events + 1 invalid: nothing commits, log untouched."""
        k = _fresh_kernel()
        p = ReferencePlanner().plan("Build a Snake game")
        events = p["events"]
        events[0]["priority"] = "urgent"  # poison one event
        with self.assertRaises(GraphError):
            k.import_events(events)
        self.assertEqual(k.store.read_events(), [])
        # after the rejection the same proposal minus the poison commits fine
        events[0]["priority"] = "medium"
        k.import_events(events)
        self.assertEqual(len(k.store.read_events()), len(events))

    def test_acceptance_is_deterministic(self):
        """§9.7: same proposal + same state -> same verdict, twice."""
        k = _fresh_kernel()
        p = ReferencePlanner().plan("Build a Snake game")
        k.import_events(p["events"])
        # replay a second identical proposal on the same state
        with self.assertRaises(GraphError):
            k.import_events(ReferencePlanner().plan("Build a Snake game")["events"])
        with self.assertRaises(GraphError):
            k.import_events(ReferencePlanner().plan("Build a Snake game")["events"])


class TestPlannerViaSdk(unittest.TestCase):
    """The planner's official commit path is the SDK, not the kernel:
    ReferencePlanner(client) -> commit() -> ForgeClient.propose()."""

    def test_commit_through_client(self):
        client = ForgeClient(tempfile.mkdtemp())
        planner = ReferencePlanner(client)
        proposal = planner.plan("Build a Snake game")
        result = planner.commit(proposal)
        self.assertEqual(result["proposal_id"], proposal["proposal_id"])
        self.assertEqual(result["committed"], 4)
        self.assertEqual(result["tasks"], 4)
        # the client sees the committed state; the planner never did
        t = client.next()
        self.assertEqual(t["id"], "build-a-snake-game-foundation")

    def test_commit_without_client_raises(self):
        with self.assertRaises(ProposalError):
            ReferencePlanner().commit(ReferencePlanner().plan("Build a Snake game"))

    def test_commit_rejects_duplicate_whole(self):
        client = ForgeClient(tempfile.mkdtemp())
        planner = ReferencePlanner(client)
        planner.commit(planner.plan("Build a Snake game"))
        with self.assertRaises(GraphError):
            planner.commit(planner.plan("Build a Snake game"))
        self.assertEqual(len(client.kernel.store.read_events()), 4)


if __name__ == "__main__":
    unittest.main()
