"""Forge plugins — clients of the kernel, not part of the forge package.

Each plugin is a separate product on top of the kernel (SPEC §9–§11):
planner, executor, reviewer, and later MCP. A plugin never touches
events.log and never mutates the graph except through the official API
(`forge.kernel.Kernel`). The kernel stays tiny and frozen; everything
new lives here.

Not shipped by `pip install forge` — run from the repository root
(PYTHONPATH=repo root) or install plugins separately.
"""
