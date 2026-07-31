"""Forge plugins — clients of the kernel, not part of the forge package.

A plugin never mutates the graph directly. It talks to Forge through
the public SDK (forge.ForgeClient) or the CLI, and nothing else.

    planner/     goal -> Proposal                    (SPEC §9, M2B)
    reference/   the human: next -> do -> verify     (SDK proof)

Everything here must be a drop-in behind the same interfaces: an LLM
planner replacing ReferencePlanner, a real executor replacing the
reference client — the kernel cannot tell the difference.
"""
