# Forge

**Project state is deterministic. Intelligence is replaceable.**

Forge is a deterministic project kernel for autonomous software
engineering. Every change to a project — by an LLM, an agent, or a
human — must be proposed, validated, and committed through the kernel.
No client ever mutates project state directly.

The planner proposes. The kernel decides.

## Why does it exist?

Conversations and markdown plans are a bad place to keep state. They
are lossy, unreplayable, and unauditable. Forge replaces them with an
event-sourced task graph: append-only, deterministic, replayable.

| Traditional agent | Forge |
| --- | --- |
| Conversation is state | Event log is state |
| AI edits directly | AI proposes |
| Memory in prompts | Deterministic graph |
| Hard to replay | Replay built in |
| Hard to audit | Fully auditable |

See [WHY_FORGE.md](WHY_FORGE.md) for the full argument.

## Forge in 60 seconds

```
forge -d chip8 init
cd chip8

forge create "Chip-8 Emulator" \
  --desc "A CHIP-8 interpreter with display, input, and ROM loader" \
  -a "ROM loads and runs" --priority high
forge expand chip-8-emulator \
  -c "CPU::executes opcodes" \
  -c "Memory::4KB RAM + registers" \
  -c "Display::64x32 framebuffer" \
  -c "Input::hex keypad"

forge graph        # the task tree
forge next         # cpu — what to work on first
forge show cpu     # the context contract: task, acceptance, deps, evidence
forge progress     # done 0/5
```

What happened: a goal became a graph. The kernel computed what is
ready, handed the client a focused context package instead of the whole
project, and recorded every step in an append-only log. The planner
proposes; the kernel decides. Nothing was mutated directly.

## Architecture

```
                Human ─┐
                Planner │   (proposals only — never touch the graph)
                Executor├──► Proposal Layer ──► Kernel ──► events.log
                Reviewer│        (validate → append → apply)
                MCP     ─┘
                                 │
                                 ├── scheduler (ready/next/blockers, priority-ordered)
                                 ├── verifier gates (status/dependency/container)
                                 ├── context builder (the ~500-token contract package)
                                 ├── inspector (task dossier + history)
                                 └── query language (safe expression subset)
```

Above the line: intelligence. Below it: deterministic computing.

The SDK in five calls — the whole executor flow:

```python
from forge import ForgeClient

forge = ForgeClient("path/to/project")
task = forge.next()                        # next ready task
ctx  = forge.context(task["id"])           # the ~500-token contract
result = llm(ctx)                          # code, tests
forge.attach_evidence(task["id"], "hard", "unittest", detail)
forge.verify(task["id"])                   # Forge decides "done", not the LLM
```

One implementation. Many clients: Hermes, Claude Code, Codex, a human
with a terminal, an MCP server, a VS Code panel.

## Install

```
python -m pip install -e .
forge --help
```

(Works without install too: `python -m forge.cli ...`)

## Quickstart

```
forge -d myproject init
cd myproject

forge create "Snake Game" --desc "A terminal snake game" -a "game runs" --priority high
forge expand snake-game \
    -c "Window::terminal window" \
    -c "Renderer::draws the board::renders;tests pass" \
    -c "Input::keyboard controls"
forge graph                       # see the tree
forge next                        # what to work on (priority order)
forge start window
forge evidence window --kind hard --source unittest --detail "14 passed"
forge verify-pass window          # hard gate: deps must be done first
forge start input
forge verify-fail input --reason "edge cases missing"
forge retry input
forge show input                  # context package for an LLM client
forge inspect renderer            # dossier: children, evidence, history
forge progress
forge replay                      # rebuild the graph from the log
```

Full command reference: [docs/CLI.md](docs/CLI.md).

## Status

The kernel is frozen at v1. This release is `0.1.0-alpha`.

Done:

- Kernel — event-sourced task graph, scheduler, verifier gates, query
  language, inspector
- Specification — `docs/SPEC.md` v1.0
- Compliance suite — 12 portable tests mapped to invariants I1–I7
- SDK — `forge.ForgeClient`, the single public surface
- Context API — the ~500-token contract package for coding agents
- Planner, Executor, Reviewer plugins — reference clients, each an LLM
  drop-in behind the same protocol
- MCP server — the SDK as six JSON-RPC 2.0 tools over stdio

Next:

- VS Code extension
- Web UI
- Multi-agent orchestrator

Full history: [docs/ROADMAP.md](docs/ROADMAP.md).

## Who is Forge for?

Forge is useful if you are building:

- AI coding agents
- Autonomous software systems
- Multi-agent workflows
- Coding research
- Reproducible AI pipelines

If you are an individual developer who wants an agent to write your
project, Forge is not the tool — yet. It is the foundation those tools
will be built on.

## Why not X?

Forge does not compete with coding agents; it sits underneath them.

- **Claude Code / Codex / OpenHands** are agents that write code. Forge
  is the state layer an agent works against. Run any of them on a Forge
  project: the agent proposes, the kernel decides.
- **LangGraph / CrewAI** orchestrate agent workflows. Forge does not
  orchestrate; it stores and validates the state those workflows
  produce. Your orchestrator of choice is a client.
- **Git** stores source code. Forge stores project state — the task
  graph, the evidence, the decisions. The two are complementary.

Nothing stops you from using all of them together: LangGraph to
orchestrate, Claude Code to write, Forge to hold the truth.

## Documentation

- [docs/SPEC.md](docs/SPEC.md) — the Forge Specification v1.0, the
  normative contract
- [docs/DESIGN.md](docs/DESIGN.md) — design decisions
- [docs/API.md](docs/API.md) — the kernel API
- [docs/EVENTS.md](docs/EVENTS.md) — the event schema
- [docs/CLI.md](docs/CLI.md) — command reference
- [docs/ROADMAP.md](docs/ROADMAP.md) — milestone history and plan
- [docs/verification.md](docs/verification.md) — test suite and stress
  results
- [WHY_FORGE.md](WHY_FORGE.md) — the motivation

## Test

```
python -m unittest discover -s tests
```

Zero dependencies, Python 3.10+.
