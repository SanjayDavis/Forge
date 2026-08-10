import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(*args, cwd):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=ROOT)
    return subprocess.run([sys.executable, "-m", "forge.cli", "-d", cwd, *args],
                          capture_output=True, text=True, env=env, cwd=ROOT)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        r = run("init", cwd=self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_lifecycle(self):
        r = run("create", "Window", "-a", "renders", cwd=self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "window")

        r = run("create", "Renderer", cwd=self.dir)
        r = run("dep", "renderer", "window", cwd=self.dir)
        self.assertEqual(r.returncode, 0)

        # blocked from passing before dep done
        r = run("start", "renderer", cwd=self.dir)
        self.assertEqual(r.returncode, 0)
        r = run("verify-pass", "renderer", cwd=self.dir)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("dependencies not done", r.stderr)

        # do the dep properly, with a failure cycle in between
        r = run("start", "window", cwd=self.dir)
        r = run("verify-fail", "window", "--reason", "no tests", cwd=self.dir)
        self.assertIn("needs_revision", r.stdout)
        r = run("retry", "window", cwd=self.dir)
        r = run("verify-pass", "window", cwd=self.dir)
        self.assertIn("done", r.stdout)

        r = run("verify-pass", "renderer", cwd=self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)

        r = run("progress", cwd=self.dir)
        self.assertIn("done 2/2 (100.0%)", r.stdout)

        r = run("validate", cwd=self.dir)
        self.assertIn("graph OK", r.stdout)

    def test_expand_and_tree(self):
        r = run("create", "Snake Game", cwd=self.dir)
        r = run("expand", "snake-game",
                "-c", "Window", "-c", "Renderer::draws board::renders;tests pass", cwd=self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("window", r.stdout)
        self.assertIn("renderer", r.stdout)

        r = run("expand", "renderer", "-c", "Camera", cwd=self.dir)

        r = run("graph", cwd=self.dir)
        self.assertIn("snake-game", r.stdout)
        self.assertIn("├──", r.stdout)
        self.assertIn("renderer", r.stdout)

        # children of renderer hang under it
        r = run("graph", "renderer", cwd=self.dir)
        self.assertIn("camera", r.stdout)

    def test_demo_and_scheduler(self):
        r = run("demo", cwd=self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)

        r = run("next", cwd=self.dir)
        self.assertEqual(r.stdout.strip(), "snake-logic")

        r = run("ready", cwd=self.dir)
        ids = r.stdout.split()
        self.assertIn("snake-logic", ids)
        self.assertNotIn("snake-game", ids)   # container
        self.assertNotIn("renderer", ids)     # container
        self.assertNotIn("window", ids)       # done
        self.assertNotIn("ui", ids)           # in_progress

        r = run("blockers", "snake-game", cwd=self.dir)
        self.assertIn("snake-logic", r.stdout)

        r = run("blockers", "snake-game", "--chain", cwd=self.dir)
        self.assertIn("snake-game -> renderer -> lighting", r.stdout)

        r = run("progress", cwd=self.dir)
        self.assertIn("done 3/11 (27.3%)", r.stdout)

    def test_show_context_and_undo(self):
        r = run("demo", cwd=self.dir)
        r = run("show", "input", cwd=self.dir)
        self.assertIn("# input", r.stdout)
        self.assertIn("[soft] peer review", r.stdout)

        r = run("show", "input", "--json", cwd=self.dir)
        self.assertIn('"effective_status"', r.stdout)

        r = run("log", "--tail", "3", cwd=self.dir)
        self.assertEqual(len(r.stdout.strip().splitlines()), 3)

        before = run("progress", cwd=self.dir).stdout
        r = run("undo", cwd=self.dir)  # undo "start ui"
        self.assertIn("undid", r.stdout)
        after = run("progress", cwd=self.dir).stdout
        self.assertNotEqual(before, after)

        r = run("replay", cwd=self.dir)
        self.assertIn("replayed", r.stdout)

    def test_errors_are_clean(self):
        r = run("start", "ghost", cwd=self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no such task", r.stderr)

        r = run("verify-fail", "ghost", "--reason", "x", cwd=self.dir)
        self.assertEqual(r.returncode, 1)

        r = run("bogus-command", cwd=self.dir)
        self.assertNotEqual(r.returncode, 0)

    def test_demo_rejects_nonempty(self):
        r = run("create", "A", cwd=self.dir)
        r = run("demo", cwd=self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("not empty", r.stderr)


class CliCrashClassTest(unittest.TestCase):
    """Phase 1 regression tests: the 5 documented crash classes must be
    clean errors (or a refused project), never raw tracebacks, and a typo'd
    -d must never silently fork a new project."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def assert_clean_error(self, r, rc=1, want_in=None):
        self.assertNotEqual(r.returncode, 0)
        if rc is not None:
            self.assertEqual(r.returncode, rc, f"stderr: {r.stderr}")
        self.assertNotIn("Traceback", r.stderr, f"raw traceback leaked: {r.stderr}")
        self.assertTrue(r.stderr.strip(), "expected an error message on stderr")
        if want_in:
            self.assertIn(want_in, r.stderr)

    def test_d_flag_pointing_at_file(self):
        f = os.path.join(self.root, "afile")
        with open(f, "w") as fh:
            fh.write("x")
        r = run("next", cwd=f)
        self.assert_clean_error(r)

    def test_events_log_as_directory(self):
        d = os.path.join(self.root, "logdir")
        os.makedirs(os.path.join(d, "events.log"))
        r = run("next", cwd=d)
        self.assert_clean_error(r)

    def test_propose_malformed_json(self):
        d = os.path.join(self.root, "pj")
        r = run("init", cwd=d)
        self.assertEqual(r.returncode, 0, r.stderr)
        bad = os.path.join(self.root, "bad.json")
        with open(bad, "w") as fh:
            fh.write("{not json")
        r = run("propose", bad, cwd=d)
        self.assert_clean_error(r, want_in="not valid JSON")

    def test_typo_d_does_not_silently_auto_init(self):
        typo = os.path.join(self.root, "typo-dir")
        r = run("next", cwd=typo)
        self.assert_clean_error(r, want_in="is not a project")
        self.assertFalse(os.path.exists(typo),
                         "typo'd -d must not silently create a project")

    def test_typo_d_create_does_not_fork_project(self):
        typo = os.path.join(self.root, "typo-create")
        r = run("create", "Task A", cwd=typo)
        self.assert_clean_error(r, want_in="is not a project")
        self.assertFalse(os.path.exists(typo))

    def test_propose_distinguishes_missing_file_from_missing_dir(self):
        # missing proposal FILE inside a valid project -> file message
        d = os.path.join(self.root, "pj")
        r = run("init", cwd=d)
        self.assertEqual(r.returncode, 0, r.stderr)
        missing_file = os.path.join(self.root, "ghost.json")
        r = run("propose", missing_file, cwd=d)
        self.assert_clean_error(r, want_in="proposal file not found")
        self.assertNotIn("is not a project", r.stderr)

        # missing project DIR -> "is not a project", dir NOT auto-created
        missing_dir = os.path.join(self.root, "no-such-project")
        r = run("propose", missing_file, cwd=missing_dir)
        self.assert_clean_error(r, want_in="is not a project")
        self.assertFalse(os.path.exists(missing_dir))

    def test_query_typo_is_clean_error_not_no_matches(self):
        d = os.path.join(self.root, "pj")
        r = run("init", cwd=d)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = run("create", "Task A", cwd=d)
        self.assertEqual(r.returncode, 0, r.stderr)

        for expr in ("sttus == todo", "status == nope", "status == high"):
            r = run("query", expr, cwd=d)
            self.assert_clean_error(r)
            self.assertNotIn("(no matches)", r.stdout,
                             f"typo'd query {expr!r} must not silently return (no matches)")

        # the valid spelling still works
        r = run("query", "status == todo", cwd=d)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "task-a")


if __name__ == "__main__":
    unittest.main()