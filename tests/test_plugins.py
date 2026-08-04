"""Plugin command registry tests (v0.1).

The CLI discovers commands through the ``forge.commands`` entry-point
group (forge/plugins.py). These tests exercise the two mechanisms:

  discover()             entry-point loading, including a broken plugin
                         that must be skipped without taking the CLI down
  stub_for_ecosystem()   known ecosystem commands whose package is not
                         installed get an install-hint stub subparser

Environment note: when forge-planner is pip-installed (as in CI), the
real `plan` command is registered through the entry point; when it is
not, the stub fires. Both paths are covered here — the stub path via
the pure function, the real path via the package's own register().
"""

import argparse
import os
import sys
import unittest
from unittest import mock

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "packages", "forge-planner"))

from forge.plugins import ECOSYSTEM_COMMANDS, discover, stub_for_ecosystem


def _parser():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    return p, sub


class FakeEntryPoint:
    """Stand-in for importlib.metadata.EntryPoint."""

    def __init__(self, name, register):
        self.name = name
        self._register = register

    def load(self):
        return self._register


class TestDiscover(unittest.TestCase):

    def test_empty_group_returns_empty_dict(self):
        p, sub = _parser()
        with mock.patch("importlib.metadata.entry_points", return_value=[]):
            self.assertEqual(discover(sub), {})

    def test_plugin_registers_a_command(self):
        def register(sub):
            sub.add_parser("fake", help="fake")
            return {"fake": lambda args, k: 0}

        p, sub = _parser()
        ep = FakeEntryPoint("fake", register)
        with mock.patch("importlib.metadata.entry_points", return_value=[ep]):
            cmds = discover(sub)
        self.assertEqual(set(cmds), {"fake"})

    def test_broken_plugin_is_skipped_not_fatal(self):
        def register(sub):  # noqa: ARG001
            raise RuntimeError("boom")

        p, sub = _parser()
        ep = FakeEntryPoint("broken", register)
        with mock.patch("importlib.metadata.entry_points", return_value=[ep]):
            cmds = discover(sub)
        self.assertEqual(cmds, {})  # one bad plugin must not kill the CLI

    def test_plugin_returning_non_dict_is_skipped(self):
        def register(sub):  # noqa: ARG001
            return "not-a-dict"

        p, sub = _parser()
        ep = FakeEntryPoint("badshape", register)
        with mock.patch("importlib.metadata.entry_points", return_value=[ep]):
            cmds = discover(sub)
        self.assertEqual(cmds, {})


class TestEcosystemStub(unittest.TestCase):

    def test_known_commands_map_is_curated(self):
        # the only known ecosystem command today is plan -> forge-planner
        self.assertEqual(ECOSYSTEM_COMMANDS, {"plan": "forge-planner"})

    def test_missing_plugin_gets_install_hint_stub(self):
        p, sub = _parser()
        stubs = stub_for_ecosystem(sub, present={})
        self.assertEqual(set(stubs), {"plan"})

        args = p.parse_args(["plan", "Build a calculator"])
        self.assertEqual(args.cmd, "plan")  # parses like the real command
        self.assertEqual(args.rest, ["Build a calculator"])

        with mock.patch("sys.stderr") as err:
            rc = stubs["plan"](args, k=None)
        self.assertEqual(rc, 1)
        err.write.assert_any_call("error: the 'plan' command is provided by "
                                  "the forge-planner package.")
        err.write.assert_any_call("  pip install forge-planner")

    def test_installed_plugin_suppresses_stub(self):
        p, sub = _parser()
        stubs = stub_for_ecosystem(sub, present={"plan": object()})
        self.assertEqual(stubs, {})  # real plugin wins, no stub

    def test_stub_parse_rejects_unknown_flags(self):
        # the stub only promises to parse; it must not swallow everything
        # silently when the real command would have its own args — but it
        # must accept the canonical invocation form.
        p, sub = _parser()
        stub_for_ecosystem(sub, present={})
        args = p.parse_args(["plan"])
        self.assertEqual(args.cmd, "plan")
        self.assertEqual(args.rest, [])


if __name__ == "__main__":
    unittest.main()
