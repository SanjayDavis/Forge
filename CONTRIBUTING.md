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

## Already have a plan? Commit it as a proposal

```
forge -d my-project propose examples/proposal.example.json
```

That file is a complete, minimal, runnable proposal. The schema is
documented in `forge propose --help`, and larger real ones live in
`examples/<proof>/proposal.json`.

If a proposal is rejected, the error names the field it expected and
points at a working file — fix the named field and retry. A proposal is
committed whole or rejected whole, so a rejection never leaves the
project half-changed.

## Point any agent at it

Point any MCP client (Claude Desktop, Cursor, Hermes) at:

```
forge-mcp -d path/to/project
```

The six tools (`forge_next`, `forge_context`, `forge_propose`,
`forge_verify`, `forge_query`, `forge_replay`) are the whole agent
surface — the same contract every first-party client uses.

## Python versions

3.10–3.13, stdlib only, zero runtime dependencies. Windows/macOS/Linux
are all first-class CI platforms since 0.1.0a6.
