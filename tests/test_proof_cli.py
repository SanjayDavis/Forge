"""Phase 2 CLI-surface tests: `forge proof check/derive/replay/bundle`.

The proof commands come from the forge-proof package via the
forge.commands entry-point group (like forge-planner's `plan`). These
tests run the real CLI in subprocesses against real directories:

  - proof must work from a NON-project cwd (-d) — it is a self-contained
    evidence tool, exempt from the Phase-1 "is not a project" gate
  - check/derive/replay/bundle behave per the Proof Standard
  - bundle emits the machine-derivable artifacts of a fresh run and
    reports the human-captured gaps (screenshots, demo.mp4, run.py)
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from forge import Kernel  # noqa: E402

SWARM = os.path.join(_REPO, "examples", "swarm")


def run_cli(*args, cwd=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=_REPO)
    return subprocess.run([sys.executable, "-m", "forge.cli", "-d", cwd, *args],
                          capture_output=True, text=True, env=env, cwd=_REPO,
                          timeout=120)


class ProofCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # ------------------------------------------------------------------ check
    def test_check_swarm_conforming_outside_project(self):
        # -d points at a non-project dir: the proof command must NOT be
        # blocked by the Phase-1 gate (it is not a project command)
        r = run_cli("proof", "check", SWARM, cwd=self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("CONFORMING: swarm", r.stdout)
        self.assertNotIn("is not a project", r.stderr + r.stdout)

    def test_check_nonconforming_dir(self):
        r = run_cli("proof", "check", str(self.root), cwd=self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("NON-CONFORMING", r.stdout)

    # ----------------------------------------------------------------- derive
    def test_derive_writes_artifacts_on_log_copy(self):
        p = self.root / "proj"
        p.mkdir()
        (p / "events.log").write_bytes(Path(SWARM, "events.log").read_bytes())
        r = run_cli("proof", "derive", str(p), "--forge-version", "0.1.0a4",
                    cwd=self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        for f in ("graph.json", "metrics.json"):
            self.assertTrue((p / f).exists(), f)
        self.assertTrue((p / "demo" / "_replay_facts.md").exists())

    # ----------------------------------------------------------------- replay
    def test_replay_renders_required_sections(self):
        p = self.root / "proj"
        p.mkdir()
        (p / "events.log").write_bytes(Path(SWARM, "events.log").read_bytes())
        (p / "proposal.json").write_bytes(Path(SWARM, "proposal.json").read_bytes())
        r = run_cli("proof", "derive", str(p), cwd=self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = run_cli("proof", "replay", str(p), cwd=self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        md = (p / "replay.md").read_text(encoding="utf-8")
        for kw in ("Goal", "Outcome", "Timeline", "Turning points"):
            self.assertIn(kw, md)
        self.assertIn("seq ", md)

    # ----------------------------------------------------------------- bundle
    def test_bundle_swarm_conforming(self):
        r = run_cli("proof", "bundle", SWARM, "--forge-version", "0.1.0a4",
                    cwd=self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("CONFORMING: swarm", r.stdout)
        # the shipped derived artifacts must have been verified byte-identical
        self.assertIn("byte-identical", r.stdout.lower())

    def test_bundle_fresh_project_emits_derivable(self):
        p = self.root / "proj"
        k = Kernel(str(p))  # SDK auto-init: fresh project, minimal run
        k.create_task("A", "The A", acceptance=["a works"], priority="high")
        k.create_task("B", "The B", acceptance=["b works"], priority="medium")
        k.add_dependency("b", "a")
        k.start("a")
        k.add_evidence("a", "hard", "unittest", "test_a passes")
        k.verify_pass("a")
        k.start("b")
        k.add_evidence("b", "hard", "unittest", "test_b passes")
        k.verify_pass("b")

        r = run_cli("proof", "bundle", str(p), cwd=self.root)
        # rc 1: the run-captured media cannot be synthesized, so the fresh
        # bundle is honestly NON-CONFORMING until the run records them
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("NON-CONFORMING", r.stdout)
        for f in ("graph.json", "metrics.json", "replay.md", "graph.png",
                  "README.md"):
            self.assertTrue((p / f).exists(), f"{f} not emitted by bundle")
        self.assertTrue((p / "demo" / "_replay_facts.md").exists())
        # gaps the machine cannot fabricate are reported:
        self.assertIn("screenshots", r.stdout)

    # ----------------------------------------------------------------- surface
    def test_proof_without_subcommand_usage_error(self):
        r = run_cli("proof", cwd=self.root)
        self.assertEqual(r.returncode, 2)
        self.assertIn("proof", r.stderr)


if __name__ == "__main__":
    unittest.main()