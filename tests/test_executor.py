"""M3 executor test suite — the second untrusted client of Forge.

Tests the Executor Protocol boundary (SPEC §10) from both sides:

  The loop:        next -> start -> context -> work -> hard evidence ->
                   verify. Five client calls; the kernel decides done,
                   never the executor. Artifacts land on disk and the
                   worker reads exactly the contract package.
  The self-check:  the executor machine-verifies every artifact claim
                   (path exists, byte-exact) before attaching evidence.
                   A lying or buggy worker is caught: no hard evidence,
                   and the task goes needs_revision via verify_fail.
  Expansion:       §10.3 — a task too large for one pass is re-split
                   through the proposal protocol; the parent becomes a
                   container and the children become the work.
  Recovery:        §10.2 — verification_failed -> needs_revision ->
                   retry -> in_progress -> work again -> done.
  The boundary:    the executor imports ONLY the public SDK — never
                   kernel internals (same proof as the planner).

The kernel is the authority. These tests assert its verdicts.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forge import ForgeClient, GraphError
from forge.kernel import Kernel
from plugins.executor import (ExecutorError, ReferenceExecutor,
                              default_worker, parse_context)
from plugins.planner import ReferencePlanner

EXECUTOR_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "plugins", "executor", "executor.py")
EXECUTOR_CLIENT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "plugins", "executor", "executor_client.py")


def _fresh_project(title: str = "Write a stub", **kwargs) -> tuple[ForgeClient, str]:
    """Fresh project with one ready task (seeded via the kernel — tests
    may; the plugin under test must not)."""
    d = tempfile.mkdtemp()
    client = ForgeClient(d)
    defaults = {"title": title, "description": "Produce an artifact stub",
                "acceptance": ["artifact exists", "has acceptance list"]}
    defaults.update(kwargs)
    client.kernel.create_task(**defaults)
    return client, d


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


class TestExecutorLoop(unittest.TestCase):
    """The five client calls, in order; the kernel decides done."""

    def test_flow_is_five_client_calls(self):
        client, d = _fresh_project()
        calls: list[str] = []
        names = ("next", "start", "context", "attach_evidence", "verify")
        orig = {n: getattr(client, n) for n in names}

        def spy(name):
            def wrapper(*a, **kw):
                calls.append(name)
                return orig[name](*a, **kw)
            return wrapper

        for n in names:
            setattr(client, n, spy(n))
        ReferenceExecutor(client, artifact_dir=os.path.join(d, "artifacts")).run(limit=1)
        self.assertEqual(calls, ["next", "start", "context",
                                 "attach_evidence", "verify"],
                         "the executor flow is exactly five client calls")

    def test_execute_writes_artifact_and_verifies(self):
        client, d = _fresh_project()
        res = ReferenceExecutor(
            client, artifact_dir=os.path.join(d, "artifacts")).execute("write-a-stub")
        self.assertEqual(res["status"], "done")
        self.assertEqual(res["artifacts"], [os.path.join(d, "artifacts", "write-a-stub.md")])
        t = client.kernel.task("write-a-stub")
        self.assertEqual(t.status, "done")          # the kernel decided
        self.assertEqual(len(t.evidence), 1)
        self.assertEqual(t.evidence[0].kind, "hard")
        self.assertEqual(t.evidence[0].source, "executor:artifact-check")
        self.assertIn("exists (", t.evidence[0].detail)
        self.assertTrue(os.path.exists(os.path.join(d, "artifacts", "write-a-stub.md")))

    def test_artifact_contains_acceptance_checklist(self):
        client, d = _fresh_project()
        ReferenceExecutor(
            client, artifact_dir=os.path.join(d, "artifacts")).execute("write-a-stub")
        with open(os.path.join(d, "artifacts", "write-a-stub.md"),
                  encoding="utf-8") as f:
            content = f.read()
        self.assertIn("# write-a-stub — Write a stub", content)
        self.assertIn("- [ ] artifact exists", content)
        self.assertIn("- [ ] has acceptance list", content)

    def test_run_walks_dependency_chain(self):
        client, d = _chain_project()
        results = ReferenceExecutor(
            client, artifact_dir=os.path.join(d, "artifacts")).run()
        self.assertEqual([r["task"] for r in results], ["alpha", "beta", "gamma"])
        self.assertTrue(all(r["status"] == "done" for r in results))
        g = client.kernel.graph
        self.assertTrue(all(t.effective_status(g.tasks) == "done"
                            for t in g.tasks.values()))
        for tid in ("alpha", "beta", "gamma"):
            self.assertTrue(os.path.exists(os.path.join(d, "artifacts", f"{tid}.md")))

    def test_run_limit_stops_after_n(self):
        client, d = _chain_project()
        results = ReferenceExecutor(
            client, artifact_dir=os.path.join(d, "artifacts")).run(limit=1)
        self.assertEqual([results[0]["task"]], ["alpha"])
        self.assertEqual(client.kernel.task("alpha").status, "done")
        self.assertEqual(client.kernel.task("beta").status, "todo")

    def test_run_empty_project_returns_nothing(self):
        client = ForgeClient(tempfile.mkdtemp())
        self.assertEqual(ReferenceExecutor(client).run(), [])


class TestWorkerContract(unittest.TestCase):
    """The worker reads the contract package; the executor verifies
    every claim before evidence; the kernel records every verdict."""

    def test_worker_receives_the_context_package(self):
        seen = {}

        def worker(ctx: str) -> dict:
            seen["ctx"] = ctx
            return default_worker(ctx, artifact_dir=os.path.join(d, "artifacts"))

        client, d = _fresh_project()
        ReferenceExecutor(client, worker=worker,
                          artifact_dir=os.path.join(d, "artifacts")).execute("write-a-stub")
        ctx = seen["ctx"]
        self.assertIn("Task: write-a-stub — Write a stub", ctx)
        for section in ("Description:", "Acceptance:", "Dependencies:",
                        "Knowledge:", "Relevant Files:", "Evidence:",
                        "Constraints:"):
            self.assertIn(section, ctx,
                          f"worker must receive the full contract package ({section})")
        self.assertIn("- artifact exists", ctx)

    def test_parse_context_roundtrips_sdk_yaml(self):
        client, _ = _fresh_project()
        pkg = parse_context(client.context("write-a-stub"))
        self.assertEqual(pkg["task"], "write-a-stub")
        self.assertEqual(pkg["title"], "Write a stub")
        self.assertEqual(pkg["description"], "Produce an artifact stub")
        self.assertEqual(pkg["acceptance"], ["artifact exists", "has acceptance list"])

    def test_parse_context_em_dash_title(self):
        """Titles may contain ' — ' themselves; only the id is before
        the first separator."""
        client, _ = _fresh_project(title="Write a stub — v2")
        pkg = parse_context(client.context("write-a-stub-v2"))
        self.assertEqual(pkg["task"], "write-a-stub-v2")
        self.assertEqual(pkg["title"], "Write a stub — v2")

    def test_parse_context_quoted_title(self):
        client, _ = _fresh_project(title="Write: the stub")
        pkg = parse_context(client.context("write-the-stub"))
        self.assertEqual(pkg["title"], "Write: the stub")

    def test_parse_context_multiline_description(self):
        client, _ = _fresh_project(description="line one\nline two")
        pkg = parse_context(client.context("write-a-stub"))
        self.assertEqual(pkg["description"], "line one\nline two")

    def test_parse_context_constraints_and_knowledge(self):
        client, _ = _fresh_project(notes=["constraint: no network", "keep it simple"])
        pkg = parse_context(client.context("write-a-stub"))
        self.assertEqual(pkg["constraints"], ["no network"])
        self.assertEqual(pkg["knowledge"], ["keep it simple"])

    def test_default_worker_is_deterministic(self):
        client, d = _fresh_project()
        ctx = client.context("write-a-stub")
        a1 = default_worker(ctx, artifact_dir=os.path.join(d, "artifacts"))
        a2 = default_worker(ctx, artifact_dir=os.path.join(d, "artifacts"))
        self.assertEqual(a1, a2)

    def test_lying_worker_caught_no_hard_evidence(self):
        d = tempfile.mkdtemp()
        client, _ = _fresh_project()

        def liar(ctx: str) -> dict:
            return {"artifacts": [{"path": os.path.join(d, "nope.md"), "bytes": 5}]}

        res = ReferenceExecutor(client, worker=liar,
                                artifact_dir=os.path.join(d, "artifacts")).execute("write-a-stub")
        self.assertEqual(res["status"], "needs_revision")
        t = client.kernel.task("write-a-stub")
        self.assertEqual(t.status, "needs_revision")
        self.assertIn("missing", t.last_failure)
        self.assertFalse(any(e.kind == "hard" for e in t.evidence),
                         "hard evidence must never be attached to a claim "
                         "the executor did not verify")
        self.assertTrue(any(e.kind == "soft" for e in t.evidence))

    def test_byte_mismatch_caught(self):
        d = tempfile.mkdtemp()
        client, _ = _fresh_project()

        def sloppy(ctx: str) -> dict:
            p = os.path.join(d, "sloppy.md")
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write("x" * 10)
            return {"artifacts": [{"path": p, "bytes": 99}]}

        res = ReferenceExecutor(client, worker=sloppy,
                                artifact_dir=os.path.join(d, "artifacts")).execute("write-a-stub")
        self.assertEqual(res["status"], "needs_revision")
        self.assertIn("size mismatch", client.kernel.task("write-a-stub").last_failure)
        self.assertFalse(any(e.kind == "hard"
                             for e in client.kernel.task("write-a-stub").evidence))

    def test_malformed_work_result_rejected(self):
        client, _ = _fresh_project()
        res = ReferenceExecutor(client, worker=lambda ctx: "hello").execute("write-a-stub")
        self.assertEqual(res["status"], "needs_revision")
        self.assertIn("WorkResult", client.kernel.task("write-a-stub").last_failure)

    def test_worker_exception_is_honest_failure(self):
        client, _ = _fresh_project()

        def boom(ctx: str) -> dict:
            raise RuntimeError("boom")

        res = ReferenceExecutor(client, worker=boom).execute("write-a-stub")
        self.assertEqual(res["status"], "needs_revision")
        reason = client.kernel.task("write-a-stub").last_failure
        self.assertIn("RuntimeError", reason)
        self.assertIn("boom", reason)


class TestExpansion(unittest.TestCase):
    """§10.3: too large for one pass -> SDK expand -> children."""

    def test_worker_may_expand_task_via_sdk(self):
        client, d = _fresh_project()
        calls = []
        orig_expand = client.expand

        def spy_expand(tid, children):
            calls.append((tid, children))
            return orig_expand(tid, children)

        client.expand = spy_expand
        res = ReferenceExecutor(
            client, worker=lambda ctx: {"expand": [{"title": "Sub A", "acceptance": ["sa"]},
                                                   {"title": "Sub B"}]},
            artifact_dir=os.path.join(d, "artifacts")).execute("write-a-stub")
        self.assertEqual(res["status"], "expanded")
        self.assertEqual(res["children"], ["sub-a", "sub-b"])
        self.assertEqual(calls, [("write-a-stub", [{"title": "Sub A", "acceptance": ["sa"]},
                                                   {"title": "Sub B"}])])
        g = client.kernel.graph
        p = g.tasks["write-a-stub"]
        self.assertTrue(p.composite)
        self.assertEqual(p.status, "in_progress")   # expansion promotes the parent
        self.assertEqual(p.depends_on, ["sub-a", "sub-b"])
        self.assertIn("sub-a", g.tasks)
        self.assertEqual(g.tasks["sub-a"].acceptance, ["sa"])
        self.assertFalse(p.evidence)                 # nothing claimed, nothing verified

    def test_run_works_expanded_children_to_completion(self):
        def smart(ctx: str) -> dict:
            pkg = parse_context(ctx)
            if pkg["title"] == "Expand me":
                return {"expand": [{"title": "Child One", "acceptance": ["c1"]},
                                   {"title": "Child Two"}]}
            return default_worker(ctx, artifact_dir=os.path.join(d, "artifacts"))

        client, d = _fresh_project(title="Expand me", acceptance=["a", "b"])
        results = ReferenceExecutor(
            client, worker=smart, artifact_dir=os.path.join(d, "artifacts")).run()
        self.assertEqual([r["status"] for r in results], ["expanded", "done", "done"])
        self.assertEqual([r["task"] for r in results],
                         ["expand-me", "child-one", "child-two"])
        g = client.kernel.graph
        self.assertEqual(g.tasks["child-one"].status, "done")
        self.assertEqual(g.tasks["child-two"].status, "done")
        # the container completes when its children do — derived, never stored
        self.assertEqual(g.tasks["expand-me"].effective_status(g.tasks), "done")
        for tid in ("child-one", "child-two"):
            self.assertTrue(os.path.exists(os.path.join(d, "artifacts", f"{tid}.md")))

    def test_expanding_a_completed_task_rejected_atomically(self):
        client, d = _fresh_project()
        ex = ReferenceExecutor(client, artifact_dir=os.path.join(d, "artifacts"))
        ex.execute("write-a-stub")                   # done
        ex.worker = lambda ctx: {"expand": [{"title": "Late"}]}
        with self.assertRaises(GraphError):
            ex.execute("write-a-stub")
        events = client.kernel.store.read_events()
        self.assertEqual(events[-1]["op"], "verification_passed",
                         "a rejected expansion must leave the log untouched — atomic")
        self.assertEqual(len(client.kernel.graph.tasks), 1)


class TestFailureRecovery(unittest.TestCase):
    """§10.2 round trip: fail -> needs_revision -> retry -> work -> done."""

    def test_needs_revision_then_retry_then_done(self):
        state = {"bad": True}
        client, d = _fresh_project()

        def flaky(ctx: str) -> dict:
            if state["bad"]:
                raise RuntimeError("first attempt fails")
            return default_worker(ctx, artifact_dir=os.path.join(d, "artifacts"))

        ex = ReferenceExecutor(client, worker=flaky,
                               artifact_dir=os.path.join(d, "artifacts"))
        r1 = ex.execute("write-a-stub")
        self.assertEqual(r1["status"], "needs_revision")
        self.assertEqual(client.kernel.task("write-a-stub").status, "needs_revision")
        # §10.2: an executor may retry to continue — through the SDK
        self.assertEqual(client.retry("write-a-stub")["op"], "task_retried")
        self.assertEqual(client.kernel.task("write-a-stub").status, "in_progress")
        state["bad"] = False
        r2 = ex.execute("write-a-stub")          # resume: same executor, same claim
        self.assertEqual(r2["status"], "done")
        t = client.kernel.task("write-a-stub")
        self.assertEqual(t.status, "done")
        kinds = [e.kind for e in t.evidence]
        self.assertIn("hard", kinds)
        self.assertIn("soft", kinds)             # the failed attempt is on the record


class TestBoundary(unittest.TestCase):
    def test_executor_consumes_only_the_public_sdk(self):
        """Structural: the executor imports ONLY the public SDK — never
        kernel internals. It operates entirely through the public
        interfaces, which is the architectural proof the boundary is
        real (same proof as the planner, §10.1)."""
        with open(os.path.normpath(EXECUTOR_SRC), encoding="utf-8") as f:
            src = f.read()
        for banned in ("forge.kernel", "forge.model", "forge.store",
                       "forge.context", "from .", "import_events", ".graph",
                       "replay(", "Store(", "Kernel(", ".kernel", "plugins."):
            self.assertNotIn(banned, src,
                             f"executor must not reference {banned!r} (§10)")
        self.assertIn("from forge import", src, "executor must consume the SDK")
        self.assertIn("ForgeClient", src)


class TestExecutorClient(unittest.TestCase):
    def test_runner_completes_proposal_chain(self):
        """End to end, exactly like a real agent would run it: planner
        proposal lands, executor-client walks the chain to done."""
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
        r = subprocess.run(["python", EXECUTOR_CLIENT, "-d", d],
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
            self.assertTrue(os.path.exists(os.path.join(d, "artifacts", f"{tid}.md")),
                            f"artifact missing for {tid}")


if __name__ == "__main__":
    unittest.main()
