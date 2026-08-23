# Contributing / external-user quickstart

Thanks for trying Forge. The fastest path from zero to a working kernel:

## Install

```bash
pip install forge-foundation forge-planner forge-mcp-base
# optional, for the proof tooling:
pip install forge-proof
```

`forge --help` should now work.

## 60-second project

```bash
forge -d my-project init
cd my-project
forge create "My goal" --desc "..." -a "done looks like this"
forge expand my-goal -c "First part" -c "Second part"
forge next        # what to work on
forge progress
```

Every mutation is a proposal; the kernel validates and commits it
atomically or not at all. Nothing outside `events.log` is state.

## Using an LLM agent with Forge

Point any MCP client (Claude Desktop, Cursor, Hermes) at:

```bash
forge-mcp -d path/to/project
```

The six tools (`forge_next`, `forge_context`, `forge_propose`,
`forge_verify`, `forge_query`, `forge_replay`) are the whole agent
surface — the same contract every first-party client uses.

## Python versions

3.10–3.13, stdlib only, zero runtime dependencies. Windows/macOS/Linux
are all first-class CI platforms since 0.1.0a6.
