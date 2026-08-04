"""Forge plugins — clients of the kernel, not part of the forge package.

A plugin never mutates the graph directly. It talks to Forge through
the public SDK (forge.ForgeClient) or the CLI, and nothing else.

    reference/   the human: next -> do -> verify     (SDK proof)
    executor/    reference executor (SPEC §11)
    reviewer/    reference reviewer (SPEC §12)
    mcp/         MCP server (transport for Hermes/Cursor/etc.)

The reference planner graduated to its own distribution: `forge-planner`
(packages/forge-planner), consumed through the forge.commands entry
point. Everything here must be a drop-in behind the same interfaces: an
LLM planner replacing ReferencePlanner, a real executor replacing the
reference client — the kernel cannot tell the difference.
"""
