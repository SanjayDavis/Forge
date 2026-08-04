"""M4 reviewer test suite — the semantic layer of Forge.

Tests the Reviewer Protocol boundary (SPEC §11) from both sides:

  The loop:        context -> judge -> approve (soft evidence + verify)
                          -> reject (soft evidence + verify_fail).
                   Three client calls; the kernel decides done, never
                   the reviewer. Deterministic checks stay the
                   executor's hard evidence; the reviewer judges only
                   the semantic layer and records it as soft evidence.
  The judge slot:  judge(ctx_yaml) is the llm slot — the reference
                   judge is deterministic (acceptance coverage), and
                   any callable with the same contract is a drop-in.
  The blocked path:the structural gate (dependencies not done) is the
                   kernel's; a machine reviewer MUST NOT force — it
                   reports blocked and leaves the task untouched.
  The boundary:    the reviewer imports ONLY the public SDK, attaches
                   ONLY soft evidence, and never writes files — never
                   kernel internals (same proof as planner/executor).

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

from forge import ForgeClient, GraphError
from forge.kernel import Kernel
from forge_planner import ReferencePlanner
from plugins.executor import default_worker
from plugins.reviewer import (REVIEW_SOURCE, ReferenceReviewer, default_judge)

REVIEWER_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "plugins", "reviewer", "reviewer.py")
REVIEWER_CLIENT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "plugins", "reviewer", "reviewer_client.py")


def _fresh_project(title: str = "Write a stub", acceptance=None, **kwargs) -> tuple[ForgeClient, str]:
    """Fresh project with one ready task (seeded via the kernel — tests
    may; the plugin under test must not)."""
    d = tempfile.mkdtemp()
    client = ForgeClient(d)
    defaults = {"title": title, "description": "Produce an artifact stub",
                "acceptance": acceptance if acceptance is not None
                else ["artifact exists", "has acceptance list"]}
    defaults.update(kwargs)
    client.kernel.create_task(**defaults)
    return client, d


def _worked_task(client: ForgeClient, d: str, tid: str) -> None:
    """Executor slot: claim, write the stub artifact, attach hard
    evidence — the deterministic layer, exactly as the executor does.
    The reviewer then judges what the tooling cannot."""
    client.start(tid)
    artifact_dir = os.path.join(d, "artifacts")
    ctx = client.context(tid)
    result = default_worker(ctx, artifact_dir=artifact_dir)
    for a in result["artifacts"]:
        client.attach_evidence(
            tid, "hard", "executor:artifact-check",
            f"{a['path']} exists ({a['bytes']} bytes)")


def _chain_project() -> tuple[ForgeClient, str]:
    """Alpha -> Beta -> Gamma; only Alpha is ready."""
    d = tempfile.mkdtemp()
    client = ForgeClient(d)
    k = client.kernel
    k.create_task("Alpha")
    k.create_task("Beta")
    k.create_task("Gamma")
    k.add_dependency("beta", "alpha")
    k.add_dependency("gamma", "beta")
    return client, d


class TestReviewerLoop(unittest.TestCase):
    """The three client calls; the kernel decides done."""

    def test_approve_attaches_soft_evidence_and_verifies(self):
        client, d = _fresh_project(acceptance=["artifact exists"])
        tid = client.next()["id"]
        _worked_task(client, d, tid)
        reviewer = ReferenceReviewer(client)
        r = reviewer.review(tid)
        self.assertEqual(r["status"], "done")
        self.assertEqual(r["verdict"], "approve")
        t = client.kernel.graph.tasks[tid]
        self.assertEqual(t.effective_status(client.kernel.graph.tasks), "done")
        soft = [e for e in t.evidence
                if e.kind == "soft" and e.source == REVIEW_SOURCE]
        self.assertEqual(len(soft), 1, "approve must attach soft evidence")
        self.assertIn("approved", soft[0].detail)

    def test_flow_is_three_client_calls(self):
        client, d = _fresh_project(acceptance=["artifact exists"])
        tid = client.next()["id"]
        _worked_task(client, d, tid)
        calls: list[str] = []
        orig = {n: getattr(client, n) for n in ("context", "attach_evidence", "verify")}

        def spy(name):
            def wrapper(*a, **kw):
                calls.append(name)
                return orig[name](*a, **kw)
            return wrapper

        for n in orig:
            setattr(client, n, spy(n))
        ReferenceReviewer(client).review(tid)
        self.assertEqual(calls, ["context", "attach_evidence", "verify"])

    def test_reject_gap_verify_fail(self):
        client, d = _fresh_project(acceptance=["has acceptance list"])
        tid = client.next()["id"]
        _worked_task(client, d, tid)
        r = ReferenceReviewer(client).review(tid)
        self.assertEqual(r["status"], "needs_revision")
        self.assertEqual(r["verdict"], "reject")
        t = client.kernel.graph.tasks[tid]
        self.assertEqual(t.effective_status(client.kernel.graph.tasks), "needs_revision")
        soft = [e for e in t.evidence if e.source == REVIEW_SOURCE]
        self.assertEqual(len(soft), 1)
        self.assertIn("rejected", soft[0].detail)
        self.assertIn("has acceptance list", r["reason"])

    def test_no_evidence_is_nothing_to_review(self):
        client, d = _fresh_project(acceptance=["artifact exists"])
        tid = client.next()["id"]
        client.start(tid)  # claimed, but no evidence on record
        r = ReferenceReviewer(client).review(tid)
        self.assertEqual(r["status"], "needs_revision")
        self.assertIn("nothing to review", r["reason"])

    def test_blocked_never_forces(self):
        """The structural gate is the kernel's. A machine reviewer must
        not override it (SPEC §11.2): blocked, task untouched."""
        client, d = _chain_project()
        client.start("beta")
        client.attach_evidence(
            "beta", "hard", "executor:artifact-check",
            "artifacts/beta.md exists (11 bytes)")
        r = ReferenceReviewer(client).review("beta")
        self.assertEqual(r["status"], "blocked")
        self.assertEqual(r["verdict"], "approve")  # judged fine…
        t = client.kernel.graph.tasks["beta"]
        # …but the kernel refused: alpha not done — and nobody forced it.
        self.assertEqual(t.effective_status(client.kernel.graph.tasks), "in_progress")
        events = client.kernel.store.read_events()
        self.assertFalse(any(e["op"] == "verification_passed" for e in events))

    def test_run_walks_reviewable_tasks(self):
        client, d = _fresh_project(acceptance=["artifact exists"])
        tid = client.next()["id"]
        _worked_task(client, d, tid)
        reviewer = ReferenceReviewer(client)
        results = reviewer.run()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["task"], tid)
        self.assertEqual(results[0]["status"], "done")

    def test_run_skips_blocked_tasks(self):
        """A blocked task stays in_progress with evidence — run() must
        not re-review it forever; it is set aside after one pass."""
        client, d = _chain_project()
        client.start("beta")
        client.attach_evidence(
            "beta", "hard", "executor:artifact-check",
            "artifacts/beta.md exists (11 bytes)")
        results = ReferenceReviewer(client).run()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "blocked")

    def test_judge_exception_is_honest_failure(self):
        client, d = _fresh_project(acceptance=["artifact exists"])
        tid = client.next()["id"]
        _worked_task(client, d, tid)

        def broken_judge(ctx):
            raise ValueError("model offline")

        r = ReferenceReviewer(client, judge=broken_judge).review(tid)
        self.assertEqual(r["status"], "needs_revision")
        self.assertIn("model offline", r["reason"])

    def test_judge_invalid_verdict_is_rejected(self):
        client, d = _fresh_project(acceptance=["artifact exists"])
        tid = client.next()["id"]
        _worked_task(client, d, tid)
        r = ReferenceReviewer(
            client, judge=lambda ctx: {"verdict": "maybe"}).review(tid)
        self.assertEqual(r["status"], "needs_revision")
        self.assertIn("invalid verdict", r["reason"])


class TestJudge(unittest.TestCase):
    """The llm slot: judge(ctx_yaml) -> {verdict, gaps, notes}."""

    def test_custom_judge_is_the_llm_slot(self):
        """Any callable with the contract is a drop-in — the reviewer
        passes it the exact contract package and obeys the verdict."""
        client, d = _fresh_project(acceptance=["artifact exists"])
        tid = client.next()["id"]
        _worked_task(client, d, tid)
        seen = {}

        def judge(ctx):
            seen["ctx"] = ctx
            return {"verdict": "approve", "gaps": [],
                    "notes": ["looks good to me"]}

        r = ReferenceReviewer(client, judge=judge).review(tid)
        self.assertEqual(r["status"], "done")
        self.assertIn("Task: ", seen["ctx"])
        self.assertIn("Acceptance:", seen["ctx"])

    def test_default_judge_approves_when_covered(self):
        pkg_yaml = (
            "Task: 'write-a-stub' — 'Write a stub'\n"
            "Description: Produce an artifact stub\n"
            "Acceptance:\n"
            "  - 'artifact exists'\n"
            "Relevant Files: (none)\n"
            "Evidence:\n"
            "  - '[hard] executor:artifact-check — "
            "artifacts/write-a-stub.md exists (123 bytes)'\n")
        v = default_judge(pkg_yaml)
        self.assertEqual(v["verdict"], "approve")
        self.assertEqual(v["gaps"], [])

    def test_default_judge_rejects_uncovered_criterion(self):
        pkg_yaml = (
            "Task: 'write-a-stub' — 'Write a stub'\n"
            "Description: Produce an artifact stub\n"
            "Acceptance:\n"
            "  - 'handles unicode input'\n"
            "Relevant Files: (none)\n"
            "Evidence:\n"
            "  - '[hard] executor:artifact-check — "
            "artifacts/write-a-stub.md exists (123 bytes)'\n")
        v = default_judge(pkg_yaml)
        self.assertEqual(v["verdict"], "reject")
        self.assertIn("handles unicode input", v["gaps"][0])

    def test_default_judge_rejects_no_evidence(self):
        pkg_yaml = (
            "Task: 'write-a-stub' — 'Write a stub'\n"
            "Description: Produce an artifact stub\n"
            "Acceptance:\n"
            "  - 'artifact exists'\n"
            "Relevant Files: (none)\n"
            "Evidence: (none)\n")
        v = default_judge(pkg_yaml)
        self.assertEqual(v["verdict"], "reject")
        self.assertIn("nothing to review", v["gaps"][0])

    def test_default_judge_vacuous_approve_without_acceptance(self):
        """A task with no acceptance criteria has nothing to judge
        against — the reference judge approves and says so."""
        pkg_yaml = (
            "Task: 'build-a-snake-game-foundation' — 'Build a Snake game — Foundation'\n"
            "Description: \n"
            "Acceptance: (none)\n"
            "Relevant Files: (none)\n"
            "Evidence:\n"
            "  - '[hard] executor:artifact-check — "
            "artifacts/build-a-snake-game-foundation.md exists (5 bytes)'\n")
        v = default_judge(pkg_yaml)
        self.assertEqual(v["verdict"], "approve")
        self.assertTrue(any("vacuous" in n for n in v["notes"]))


class TestBoundary(unittest.TestCase):
    """The reviewer consumes ONLY the public SDK (same proof as the
    planner and executor), attaches ONLY soft evidence, and never
    touches the filesystem or the graph."""

    def test_reviewer_consumes_only_the_public_sdk(self):
        with open(os.path.normpath(REVIEWER_SRC), encoding="utf-8") as f:
            src = f.read()
        for banned in ("forge.kernel", "forge.model", "forge.store",
                       "forge.context", "from .", "import_events", ".graph",
                       "replay(", "Store(", "Kernel(", ".kernel", "plugins.",
                       '"hard"', "force", "open(", "write_text", "write_bytes",
                       "Path(", "os.write", "shutil", "tempfile"):
            self.assertNotIn(banned, src,
                             f"reviewer must not reference {banned!r} (§11)")
        self.assertIn("from forge import", src, "reviewer must consume the SDK")
        self.assertIn("parse_context", src,
                      "the SDK owns the Context Contract reader")
        self.assertIn("ForgeClient", src)

    def test_reviewer_never_attaches_hard_evidence(self):
        """Behavioral proof on top of the source scan: every evidence
        attach through the whole flow is soft."""
        client, d = _fresh_project(acceptance=["artifact exists"])
        tid = client.next()["id"]
        _worked_task(client, d, tid)
        attaches: list[tuple] = []
        orig = client.attach_evidence

        def spy(tid, kind, source, detail):
            attaches.append((kind, source))
            return orig(tid, kind, source, detail)

        client.attach_evidence = spy
        ReferenceReviewer(client).run()
        self.assertTrue(attaches, "reviewer must attach evidence")
        self.assertTrue(all(k == "soft" for k, _ in attaches),
                        f"reviewer attached hard evidence: {attaches}")


class TestReviewerClient(unittest.TestCase):
    def test_runner_completes_proposal_chain(self):
        """End to end, exactly like a real agent would run it: planner
        proposal lands, reviewer-client walks the chain to done —
        executor slot (hard evidence) then reviewer slot (judge)."""
        d = tempfile.mkdtemp()
        env = dict(os.environ, PYTHONPATH=os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        subprocess.run(["forge", "-d", d, "init"], check=True,
                       capture_output=True, text=True, env=env)
        p = ReferencePlanner().plan("Build a Snake game")
        prop_path = os.path.join(d, "prop.json")
        with open(prop_path, "w", encoding="utf-8") as f:
            json.dump(p, f)
        subprocess.run(["forge", "-d", d, "propose", prop_path],
                       check=True, capture_output=True, text=True, env=env)
        r = subprocess.run(["python", REVIEWER_CLIENT, "-d", d],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("nothing ready", r.stdout)
        self.assertEqual(r.stdout.count("done:"), 3)
        g = ForgeClient(d).kernel.graph
        self.assertTrue(all(t.effective_status(g.tasks) == "done"
                            for t in g.tasks.values()))
        for tid in ("build-a-snake-game-foundation",
                    "build-a-snake-game-core",
                    "build-a-snake-game-acceptance"):
            t = g.tasks[tid]
            self.assertTrue(any(e.kind == "hard" for e in t.evidence),
                            f"hard evidence missing for {tid}")
            self.assertTrue(any(e.kind == "soft"
                                and e.source == REVIEW_SOURCE
                                for e in t.evidence),
                            f"reviewer soft evidence missing for {tid}")


if __name__ == "__main__":
    unittest.main()
