"""Public surface guard — the rc1 freeze referee.

ROAD_TO_1.0.md: "No public-SDK/API change for 90 days (surface-guard CI
is the referee)". This module is that referee. It pins the exact public
surface of the `forge` package — the names the frozen kernel contract
and the SDK expose to every client — so any accidental add, removal,
rename, or signature change fails CI before it ships.

The pinned lists are the SOURCE OF TRUTH by enumeration. When a change
to the public surface is *intentional* (a spec amendment per Appendix A,
or a deliberate SDK addition), update the expected list in the same
commit and say why in the CHANGELOG — the diff of this file then IS the
public API changelog.

Scope:
  - forge.ForgeClient method names + signatures (the one client interface)
  - top-level `forge` namespace (what `from forge import *` offers)
  - ForgeClient's attribute surface (kernel access is private by design)

Not pinned here (by design): kernel-internal method set (docs/API.md is
its contract), CLI flags, plugin APIs.
"""
from __future__ import annotations

import inspect
import unittest

import forge
from forge import ForgeClient


FORGE_NAMESPACE = frozenset("""
    EVIDENCE_HARD EVIDENCE_SOFT SCHEMA_VERSION PRIORITIES PRIORITY_WEIGHT
    OP_SHAPES STATUS_TODO STATUS_IN_PROGRESS STATUS_NEEDS_REVISION
    STATUS_DONE Evidence TaskNode Graph GraphError EVENT_FILE Store
    load_project blockers is_container next_task progress ready_tasks
    build_context to_json to_markdown QueryError run_query Kernel
    ForgeClient ContextError ProposalError PLANNER_OPS context_package
    parse_context slugify validate_proposal
""".split()) | {
    # Import machinery: importing a `forge.*` submodule binds its name on
    # the parent package (e.g. `from forge.plugins import ...` in
    # test_plugins, or plugin tests importing `plugins.executor`). Which
    # of these are present depends on module-import order, so the guard
    # compares against the *stable* curated set plus whatever submodules
    # happen to be bound — but every entry must be an existing forge
    # submodule or a curated name, never anything else.
    "model", "store", "scheduler", "context", "query", "kernel", "sdk",
    "plugins", "webui", "bharatcode",
}
FORGE_SUBMODULES = {"model", "store", "scheduler", "context", "query",
                    "kernel", "sdk", "plugins", "webui", "bharatcode"}


# name -> parameter signature (names only; order matters, defaults do not)
FORGECLIENT_METHODS = {
    "next": (),
    "context": ("task_id",),
    "propose": ("proposal",),
    "start": ("task_id",),
    "expand": ("task_id", "children"),
    "attach_evidence": ("task_id", "kind", "source", "detail"),
    "verify": ("task_id",),
    "verify_fail": ("task_id", "reason"),
    "retry": ("task_id",),
    "query": ("expr",),
    "progress": (),
    "replay": (),
}


def _sig_names(func) -> tuple[str, ...]:
    return tuple(inspect.signature(func).parameters)


class TestForgeNamespace(unittest.TestCase):
    """`from forge import X` keeps working for exactly these names."""

    def _public(self) -> set[str]:
        return {n for n in vars(forge) if not n.startswith("_")}

    def test_curated_names_all_present(self):
        # Every curated name is importable, regardless of import order.
        curated = FORGE_NAMESPACE - FORGE_SUBMODULES
        missing = {n for n in curated if not hasattr(forge, n)}
        self.assertFalse(missing,
                         f"curated public names removed: {sorted(missing)}")

    def test_public_names_are_curated_or_submodules(self):
        # Nothing may appear on the namespace that is neither a curated
        # name nor a forge.* submodule bound by the import machinery.
        stray = self._public() - set(FORGE_NAMESPACE)
        self.assertFalse(
            stray,
            f"new public names need a pin update: {sorted(stray)}")

    def test_submodule_names_are_real_modules(self):
        # A submodule name on the namespace must still resolve to a
        # module — catches accidental shadowing by a non-module value.
        for n in FORGE_SUBMODULES & self._public():
            import types
            self.assertIsInstance(getattr(forge, n), types.ModuleType)

    def test_version_attribute_present(self):
        # __version__ is dunder-prefixed so vars() skips it; pin it here
        self.assertIsInstance(forge.__version__, str)
        self.assertRegex(forge.__version__, r"^\d+\.\d+\.\d+(a|b|rc)\d+$")

    def test_no_new_public_names_silently(self):
        extra = self._public() - set(FORGE_NAMESPACE)
        missing = {n for n in (FORGE_NAMESPACE - FORGE_SUBMODULES)
                   if n not in vars(forge)}
        self.assertFalse(extra, f"new public names need a pin update: {sorted(extra)}")
        self.assertFalse(missing, f"removed public names need a pin update: {sorted(missing)}")


class TestForgeClientSurface(unittest.TestCase):
    """The ONE client interface: same methods, same parameters."""

    def test_method_set_is_exactly_pinned(self):
        actual = {n for n, v in vars(ForgeClient).items()
                  if callable(v) and not n.startswith("_")}
        self.assertEqual(actual, set(FORGECLIENT_METHODS))

    def test_signatures_are_unchanged(self):
        for name, params in FORGECLIENT_METHODS.items():
            with self.subTest(method=name):
                sig = _sig_names(getattr(ForgeClient, name))
                # skip self
                self.assertEqual(sig[0], "self")
                self.assertEqual(sig[1:], params)

    def test_kernel_access_is_private(self):
        # The SDK boundary: clients reach the kernel only through the
        # twelve methods above, never through an exposed internals slot.
        private = [n for n, _ in vars(ForgeClient).items() if n.startswith("__") and n.endswith("__")]
        dunder_only = all(n.startswith("__") and n.endswith("__")
                          for n in vars(ForgeClient) if n.startswith("_"))
        self.assertTrue(dunder_only or not private,
                        "ForgeClient must expose no non-dunder privates beyond convention")

    def test_version_string_shape(self):
        # covered in TestForgeNamespace.test_version_attribute_present
        self.assertRegex(forge.__version__, r"^\d+\.\d+\.\d+(a|b|rc)\d+$")


if __name__ == "__main__":
    unittest.main()
