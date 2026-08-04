"""forge_mcp — the Forge MCP server distribution.

The Forge wire protocol as an installable package: JSON-RPC 2.0 over
stdio, six tools, one SDK call each, zero business logic. Consumes only
the public SDK (forge.ForgeClient). This is the transport that lets any
MCP client (Claude, Hermes, the `mcp` SDK, a text editor) drive a Forge
project.

    forge-mcp -d PROJECT
    python -m forge_mcp.server -d PROJECT

The distribution is named `forge-mcp`; the import name is `forge_mcp`.
The server is stdlib-only and never touches kernel internals.
"""
from .server import (ForgeMCPServer, PROTOCOL_VERSION, SERVER_INFO, TOOLS,
                     main)

__all__ = ["ForgeMCPServer", "PROTOCOL_VERSION", "SERVER_INFO", "TOOLS",
           "main"]