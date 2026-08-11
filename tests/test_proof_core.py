"""Phase 2 unit tests: forge_proof core + check_invariants core (S7 gap class).

Covers the vendored pure logic (derive replay/graph/metrics), byte-parity
between the package derive and the canonical tools/proof-derive.py, the
replay.md renderer, the check_invariants S1..S6 pure checks on synthetic
event logs, and parameterized double-derive (S7) over log variants —
the gap class: S7 was only ever exercised against examples/swarm's single
shipped log.
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "packages", "forge-proof"))
sys.path.insert(0, os.path.join(_REPO, "packages", "forge-planner"))

from forge_proof import check as proof_check           # noqa: E402
from forge_proof import derive as proof_derive         # noqa: E402
from forge_proof import replay as proof_replay         # noqa: E402


# ---------------------------------------------------------------- log builders
def _ev(seq, op, **extra):
    e = {"op": op, "seq": seq, "ts": "2026-08-09T%02d:00:00Z" % (8 + seq % 12)}
    e.update(extra)
    return e


def make_log(variant: str):
    """Synthetic contiguous event logs for derive/invariant param cases."""
    if variant == "minimal":
        return [
            _ev(1, "task_created", id="a", title="Task A", priority="high"),
            _ev(2, "task_created", id="b", title="Task B", priority="medium"),
            _ev(3, "dependency_added", task="b", depends_on="a"),
            _ev(4, "task_started", id="a"),
            _ev(5, "evidence_added", id="a", kind="hard", source="unittest",
                detail="test_a passes (agent=test)"),
            _ev(6, "verification_passed", id="a"),
            _ev(7, "task_started", id="b"),
            _ev(8, "evidence_added", id="b", kind="hard", source="unittest",
                detail="test_b passes (agent=test)"),
            _ev(9, "verification_passed", id="b"),
        ]
    if variant == "retry_cycle":
        return [
            _ev(1, "task_created", id="t", title="T", priority="low"),
            _ev(2, "task_started", id="t"),
            _ev(3, "verification_failed", id="t", reason="flaky"),
            _ev(4, "task_retried", id="t"),
            _ev(5, "evidence_added", id="t", kind="hard", source="unittest",
                detail="test_t passes (agent=test)"),
            _ev(6, "verification_passed", id="t"),
        ]
    if variant == "claims_claimed":
        log = make_log("minimal")
        return log[:2] + [_ev(2, "proposal_committed", id="prop_x",
                              claims=["C1"])] + [
            e for e in log[2:] if e["op"] != "task_created"] + [
            _ev(99, "claims_claimed", id="prop_x", claims=["C1"])]
    if variant == "no_claims_proposal":
        return make_log("minimal")[:-1]
    raise ValueError(variant)


class ProofCoreTest(unittest.TestCase):
    def test_replay_reconstructs_tasks_and_edges(self):
        r = proof_derive.replay(make_log("minimal"))
        self.assertEqual(sorted(r["tasks"]), ["a", "b"])
        self.assertEqual(r["edges"], [("a", "b")])
        self.assertEqual(r["status"]["a"], "done")
        self.assertEqual(r["status"]["b"], "done")
        self.assertEqual(r["meta"]["max_ready_queue"], 1)

    def test_derive_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "events.log").write_text(
                "\n".join(json.dumps(e) for e in make_log("minimal")) + "\n",
                encoding="utf-8")
            proof_derive.derive_dir(str(p), forge_version="0.1.0a4")
            h1 = hashlib.sha256((p / "graph.json").read_bytes()).hexdigest()
            h2 = hashlib.sha256((p / "metrics.json").read_bytes()).hexdigest()
            (p / "graph.json").unlink()
            (p / "metrics.json").unlink()
            proof_derive.derive_dir(str(p), forge_version="0.1.0a4")
            self.assertEqual(
                hashlib.sha256((p / "graph.json").read_bytes()).hexdigest(), h1)
            self.assertEqual(
                hashlib.sha256((p / "metrics.json").read_bytes()).hexdigest(), h2)

    def test_package_derive_byte_identical_to_tools(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "events.log").write_text(
                "\n".join(json.dumps(e) for e in make_log("minimal")) + "\n",
                encoding="utf-8")
            proof_derive.derive_dir(str(p), forge_version="0.1.0a4")
            ours = [(f, hashlib.sha256((p / f).read_bytes()).hexdigest())
                    for f in ("graph.json", "metrics.json")]
            (p / "graph.json").unlink()
            (p / "metrics.json").unlink()
            subprocess.run([sys.executable,
                            os.path.join(_REPO, "tools", "proof-derive.py"),
                            str(p), "--forge-version", "0.1.0a4"],
                           check=True, capture_output=True, text=True)
            theirs = [(f, hashlib.sha256((p / f).read_bytes()).hexdigest())
                      for f in ("graph.json", "metrics.json")]
            self.assertEqual(ours, theirs)

    def test_language_inference(self):
        events = make_log("minimal")
        events[0]["description"] = "implements auth/claims.rs token model"
        self.assertEqual(proof_derive._infer_language(events), "Rust")

    def test_claims_from_log_then_proposal_fallback(self):
        log = make_log("claims_claimed")
        self.assertEqual(proof_derive._infer_claims(log, Path(".")), ["C1"])


class CheckInvariantsCoreTest(unittest.TestCase):
    """Pure S1..S6 checks from examples/swarm/check_invariants.py vs
    synthetic logs — happy path plus one injected failure each."""

    @classmethod
    def setUpClass(cls):
        src = os.path.join(_REPO, "examples", "swarm", "check_invariants.py")
        spec = importlib.util.spec_from_file_location("check_invariants", src)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def _checker(self):
        return self.mod.Checker(Path(tempfile.mkdtemp()))

    def test_s1_s2_s5_happy(self):
        c = self._checker()
        self.assertTrue(c.s1_dag(make_log("minimal")))
        self.assertTrue(c.s2_orphans(make_log("minimal")))
        self.assertTrue(c.s5_contiguous(make_log("minimal")))

    def test_s1_cycle_fails(self):
        log = make_log("minimal")
        log.append(_ev(10, "dependency_added", task="a", depends_on="b"))
        c = self._checker()
        self.assertFalse(c.s1_dag(log))

    def test_s2_orphan_fails(self):
        log = make_log("minimal")[:-3]  # b never started nor passed
        c = self._checker()
        self.assertFalse(c.s2_orphans(log))

    def test_s3_order_violation_fails(self):
        log = make_log("minimal")
        # start b before a passed
        log[6]["seq"], log[5]["seq"] = log[5]["seq"], log[6]["seq"]
        c = self._checker()
        self.assertFalse(c.s3_order(log))

    def test_s4_double_start_fails(self):
        log = make_log("minimal")
        log.append(_ev(10, "task_started", id="a"))
        c = self._checker()
        self.assertFalse(c.s4_ownership(log))

    def test_s5_gap_fails(self):
        log = make_log("minimal")
        log[4]["seq"] = 99
        c = self._checker()
        self.assertFalse(c.s5_contiguous(log))

    def test_s6_missing_passing_evidence_fails(self):
        log = make_log("minimal")
        log = [e for e in log if not (e["op"] == "evidence_added")]  # no evidence
        c = self._checker()
        self.assertFalse(c.s6_evidence(log))


class S7DoubleDeriveParamTest(unittest.TestCase):
    """The S7 gap class: double-derive byte-identity across log variants,
    not just the shipped swarm log."""

    @classmethod
    def setUpClass(cls):
        src = os.path.join(_REPO, "examples", "swarm", "check_invariants.py")
        spec = importlib.util.spec_from_file_location("check_invariants_s7", src)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def _run_derive(self, p, version):
        r = subprocess.run(
            [sys.executable, os.path.join(_REPO, "tools", "proof-derive.py"),
             str(p), "--forge-version", version],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def _assert_double_derive(self, variant):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "events.log").write_text(
                "\n".join(json.dumps(e) for e in make_log(variant)) + "\n",
                encoding="utf-8")
            self._run_derive(p, "0.1.0a4")
            h1 = [(f, hashlib.sha256((p / f).read_bytes()).hexdigest())
                  for f in ("graph.json", "metrics.json")]
            (p / "graph.json").unlink()
            (p / "metrics.json").unlink()
            self._run_derive(p, "0.1.0a4")
            h2 = [(f, hashlib.sha256((p / f).read_bytes()).hexdigest())
                  for f in ("graph.json", "metrics.json")]
            self.assertEqual(h1, h2, f"double-derive mismatch for {variant}")

    def test_minimal(self):
        self._assert_double_derive("minimal")

    def test_retry_cycle(self):
        self._assert_double_derive("retry_cycle")

    def test_claims_claimed(self):
        self._assert_double_derive("claims_claimed")

    def test_shipped_swarm_authoritative(self):
        # the authoritative S7 case, run through check_invariants itself:
        # shipped graph.json/metrics.json must equal the re-derive from the
        # shipped events.log
        c = self.mod.Checker(Path(_REPO) / "examples" / "swarm")
        self.assertTrue(c.s7_double_derive("0.1.0a4"))


class ReplayRenderTest(unittest.TestCase):
    def test_replay_markdown_has_required_sections(self):
        facts = (
            "# Replay facts (derived from events.log)\n"
            "- tasks: 2 · events: 9 · passes: 2 · failures: 0 · retries: 0 · "
            "duration: 0 min\n"
            "- seq 1  task_created  a\n"
            "- seq 6  verification_passed  a\n")
        metrics = {"status": "completed", "tasks": 2, "events": 9,
                   "verification_passes": 2, "verification_failures": 0,
                   "retries": 0, "duration_minutes": 0,
                   "max_ready_queue": 1, "max_ready_queue_at": {"seq": 6}}
        md = proof_replay.render_replay("proj", facts, metrics,
                                        goal="Build the thing")
        for kw in ("Goal", "Outcome", "Timeline", "Turning points"):
            self.assertIn(kw, md)
        self.assertIn("seq 1", md)
        self.assertIn("Build the thing", md)


class ProofCheckCoreTest(unittest.TestCase):
    def test_required_files_constant(self):
        self.assertEqual(
            proof_check.REQUIRED_FILES,
            ["README.md", "events.log", "graph.json", "graph.png",
             "replay.md", "metrics.json", "demo.mp4"])
        self.assertEqual(len(proof_check.README_SECTIONS), 8)


if __name__ == "__main__":
    unittest.main()