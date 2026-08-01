"""M5 — the MCP server plugin (SPEC Appendix A: MCP interfaces may
evolve freely). The Forge wire protocol: JSON-RPC 2.0 over stdio, six
tools, one SDK call each, zero business logic.

    python -m plugins.mcp.server -d PROJECT     (or plugins/mcp/server.py)

An MCP client (Claude, Hermes, the `mcp` SDK) connects over stdio and
gets the whole Forge surface: forge_next, forge_context,
forge_propose, forge_verify, forge_query, forge_replay. The server is
stdlib-only and consumes ONLY the public SDK — a transport, nothing
more. The kernel decides; this translates.
"""
from .server import (ForgeMCPServer, PROTOCOL_VERSION, SERVER_INFO, TOOLS,
                     main)

__all__ = ["ForgeMCPServer", "PROTOCOL_VERSION", "SERVER_INFO", "TOOLS",
           "main"]
