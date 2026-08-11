"""Plugin command discovery for the Forge CLI.

The CLI is extensible through the ``forge.commands`` entry-point group
(PEP 621 / importlib.metadata). Each entry point must be a callable::

    def register(subparsers) -> dict[str, handler]

It adds its own subparser(s) to the CLI (so a plugin owns its argument
shape) and returns a ``{command_name: handler}`` map, where each handler
has the same signature as a built-in: ``handler(args, k) -> int``.

``ECOSYSTEM_COMMANDS`` is the curated map of known ecosystem commands to
the packages that provide them. When such a package is not installed,
the CLI still registers the subparser with a stub handler that prints an
install hint — so ``forge plan`` without ``forge-planner`` explains
itself instead of failing with argparse's bare "invalid choice".

The kernel is untouched by this mechanism: plugins are clients of the
public SDK exactly like any other external client.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import sys
from typing import Callable

#: entry-point group that may contribute CLI commands
PLUGIN_GROUP = "forge.commands"

#: known ecosystem commands -> package that should provide them. This is
#: the registry that lets a future forge-mcp / forge-vscode join the CLI.
ECOSYSTEM_COMMANDS: dict[str, str] = {
    "plan": "forge-planner",
    "proof": "forge-proof",
}


def discover(subparsers: argparse._SubParsersAction) -> dict[str, Callable]:
    """Load every entry point in ``forge.commands``.

    Each point is a callable ``register(subparsers)`` returning a
    ``{name: handler}`` dict. A broken plugin is reported and skipped —
    it must never take the whole CLI down with it.
    """
    commands: dict[str, Callable] = {}
    eps = importlib.metadata.entry_points(group=PLUGIN_GROUP)
    for ep in eps:
        try:
            register = ep.load()
        except Exception as e:  # pragma: no cover - environment dependent
            print(f"warning: failed to load forge plugin {ep.name!r}: {e}",
                  file=sys.stderr)
            continue
        try:
            got = register(subparsers)
        except Exception as e:  # pragma: no cover - environment dependent
            print(f"warning: forge plugin {ep.name!r} failed to register: {e}",
                  file=sys.stderr)
            continue
        if not isinstance(got, dict):  # pragma: no cover - plugin contract
            print(f"warning: forge plugin {ep.name!r} must return a "
                  "dict of commands", file=sys.stderr)
            continue
        commands.update(got)
    return commands


def stub_for_ecosystem(subparsers: argparse._SubParsersAction,
                       present: dict[str, Callable]) -> dict[str, Callable]:
    """Register install-hint stubs for known ecosystem commands whose
    package is not installed. Returns the stub handlers so the caller can
    merge them in the same way it would real plugin handlers."""
    stubs: dict[str, Callable] = {}
    for name, pkg in ECOSYSTEM_COMMANDS.items():
        if name in present:
            continue
        c = subparsers.add_parser(name, help=f"{name} (provided by {pkg})")
        c.add_argument("rest", nargs=argparse.REMAINDER,
                       help="(ignored — the real command's arguments come "
                            "from the {pkg} package)".replace("{pkg}", pkg))

        def _stub(args, k, _name=name, _pkg=pkg) -> int:
            print(f"error: the '{_name}' command is provided by the "
                  f"{_pkg} package.", file=sys.stderr)
            print(f"  pip install {_pkg}", file=sys.stderr)
            return 1

        stubs[name] = _stub
    return stubs