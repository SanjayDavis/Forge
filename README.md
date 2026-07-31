# Project Kernel

An AI-agnostic, event-sourced task graph engine. Deterministic Python core
with zero dependencies. LLMs (Claude, Codex, Gemini, Hermes — or none at
all) are just clients that emit the same events a human emits through the
CLI.

The graph is the **shared memory and execution state**. Deterministic code
handles scheduling, dependency resolution, and progress tracking; the LLM
is used only where it's strongest — planning, writing code, reviewing.

```
LLM ──┐
      ├──► Project Kernel ──► events.log (source of truth)
Human ─┘        │
                ├── scheduler (ready/next/blockers)
                ├── verifier gates (hard: tests/lint, soft: review)
                └── context builder (focused package per task)
```

## Design decisions

- **Event sourcing.** The only state is an append-only `events.log`
  (JSONL). The graph is a fold over the log. Undo = truncate, replay =
  refold, crash recovery = skip torn line, audit = the log itself.
- **Derived states.** `blocked` is never stored — it's computed from
  dependencies. `done` on a container task is derived from its children.
- **Runtime expansion.** A task mid-work can be expanded into children;
  the parent becomes a container that completes when its children do.
  The graph evolves instead of the executor guessing.
- **Hard vs soft evidence.** `hard` = tests/compile/benchmark (machine
  verifiable). `soft` = LLM/human review (asserted). Both attach to tasks.
- **Context Builder.** `pk show TASK` produces the exact package an LLM
  client needs: task, acceptance criteria, dependencies + statuses,
  blockers, evidence, project progress. No context reconstruction.

## Install

```
python -m pip install -e .
pk --help
```

(Works without install too: `python -m pkernel.cli ...`)

## Quickstart

```
pk -d myproject init
cd myproject

pk create "Snake Game" --desc "A terminal snake game" -a "game runs"
pk expand snake-game \
    -c "Window::terminal window" \
    -c "Renderer::draws the board::renders;tests pass" \
    -c "Input::keyboard controls"
pk graph                       # see the tree
pk next                        # what to work on
pk start window
pk evidence window --kind hard --source unittest --detail "14 passed"
pk verify-pass window          # hard gate: deps must be done first
pk verify-fail input --reason "edge cases missing"
pk retry input
pk show input                  # context package for an LLM client
pk blockers snake-game --chain # root-cause paths
pk progress
pk undo                        # truncate the last event
pk replay                      # rebuild the graph from the log
```

## States

```
todo ──start──► in_progress ──verify-fail──► needs_revision
                  │  ▲                            │
                  │  └─────────retry──────────────┘
                  └──────verify-pass──────► done ──reopen──► in_progress
```

`verify-pass` is rejected while dependencies are incomplete (`--force`
overrides — humans can break rules, machines shouldn't). Containers can't
be verified directly; they complete when all children complete.

## Commands

```
init          create events.log in DIR
create        add a task (--id, --desc, -a acceptance, -f file)
update        change title/desc/acceptance/files
dep           add/remove a dependency (--remove)
expand        turn a task into a container; children become its work
start         todo -> in_progress
verify-pass   in_progress -> done (requires deps done; --force bypasses)
verify-fail   in_progress -> needs_revision (--reason required)
retry         needs_revision -> in_progress
reopen        done -> in_progress
evidence      attach hard/soft evidence (--kind, --source, --detail)
note          append a note
delete        remove a task (no dependents, no children)
show          context package (--json for machine format)
graph         render the task tree (optional root TASK)
ready         list tasks ready to work on
next          the single next task
blockers      incomplete deps (--chain for root-cause paths)
progress      done/total + per-status counts
validate      consistency check (cycles, dangling refs)
log           view events (--tail N)
undo [N]      truncate the last N events
replay        reconstruct the graph from the log
demo          seed the Snake Game example (empty project only)
```

## Event log

```
{"op": "task_created", "seq": 1, "id": "snake-game", "title": "Snake Game", ...}
{"op": "task_expanded", "seq": 2, "task": "snake-game", "children": [...]}
{"op": "task_started", "seq": 3, "id": "window", ...}
{"op": "verification_passed", "seq": 4, "id": "window", "force": false, ...}
```

## Roadmap

- **M2 — Planner.** One LLM call: goal in, `task_expanded` events out
  (structured JSON → same builders). Validated structurally before entry.
- **M3 — Executor + Verifier.** Executor gets `pk show` output, writes
  code, verifier runs hard gates then emits evidence/verify events.
- **M4 — Multi-agent + MCP.** Expose the builders as MCP tools
  (`graph.create_node`, `graph.ready_tasks`, `graph.get_context`...).
  Any agent works through the same kernel. Nobody owns the project —
  the kernel does.
- **Concurrency.** The log is append-only; a file lock is the only thing
  needed for true multi-process writes.

## Test

```
python -m unittest discover -s tests
```

Zero dependencies, Python 3.10+.
