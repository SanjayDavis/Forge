# forge-bharatcode

A Forge planner backed by the [BharatCode](https://bharatcode.ai) model API.

The kernel stays zero-dependency; this package is the only part of Forge
that touches the network, and only when you ask it to plan.

## Install

```sh
pip install -e .                  # forge-foundation
pip install -e packages/forge-bharatcode
```

## Usage

```sh
export BHARATCODE_API_KEY=bc_live_...
forge -d myproject init
forge -d myproject plan-bharatcode "Build a CHIP-8 emulator"   # prints proposal JSON
forge -d myproject plan-bharatcode "Build a CHIP-8 emulator" --commit
```

Environment variables:

- `BHARATCODE_API_KEY` — required.
- `BHARATCODE_BASE_URL` — default `https://bharatcode.ai/api/model/v1`.
- `BHARATCODE_MODEL` — default `qwen-3.8-27b`.

## Programmatic

```python
from forge import ForgeClient
from forge_bharatcode import BharatCodePlanner

client = ForgeClient("myproject")
planner = BharatCodePlanner(client)
proposal = planner.plan("Build a CHIP-8 emulator")
client.propose(proposal)
```
