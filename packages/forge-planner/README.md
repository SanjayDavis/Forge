# forge-planner

The reference planner for [Forge](https://github.com/SanjayDavis/Forge) —
a deterministic, stdlib-only client of the public SDK. Goal in, proposal
out (SPEC §9); the kernel commits or rejects the proposal whole.

This package is the architectural proof behind the SDK boundary: it is a
*separate, installable package* that consumes only the public
`forge.*` surface — no kernel internals.

## Install

```sh
pip install forge-kernel forge-planner
```

## Use

```sh
forge init demo
forge plan "Build a calculator"        # print the proposal (no commit)
forge plan "Build a calculator" --commit  # commit atomically through the kernel
```

`forge plan` is registered as a `forge.commands` entry point: the CLI
discovers the command from this package at runtime.

## The planner

- Deterministic: `ReferencePlanner.plan(goal)` is a pure function of the goal.
- Stdlib-only: no AI, no network.
- Constrained (SPEC §9.6): only task ops, no seq on events, every
  referenced id predicted with the kernel's own slugify/next_id derivation.
- Any LLM planner is a drop-in replacement behind the same protocol.

## License

MIT
