# forge-mcp

The MCP server for [Forge](https://github.com/SanjayDavis/Forge) — a
deterministic, stdlib-only transport that exposes the whole Forge SDK to
any MCP client. JSON-RPC 2.0 over stdio, six tools, one SDK call each,
zero business logic.

This package is the ecosystem proof behind the SDK boundary: it is a
*separate, installable package* that consumes only the public
`forge.*` surface — no kernel internals.

## Install

```sh
pip install forge-kernel forge-mcp
```

## Use

```sh
forge-mcp -d myproject
```

Or from Python:

```sh
python -m forge_mcp.server -d myproject
```

An MCP client (Claude, Hermes, the `mcp` SDK, any editor) connects over
stdio and gets six tools — `forge_next`, `forge_context`,
`forge_propose`, `forge_verify`, `forge_query`, `forge_replay` — each a
thin pass-through to one SDK method. The kernel decides; this
translates.

## Reference client

A walk-through client that proves the server is a real MCP server:

```sh
python -m forge_mcp.mcp_client -d myproject
```

It performs the handshake, lists tools, and drives the six-tool loop
over the wire.
