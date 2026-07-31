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


if __name__ == "__main__":
    unittest.main()
