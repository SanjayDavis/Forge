# Why Forge?

A deterministic project kernel for autonomous software engineering.

Most AI coding tools today share the same architecture:

```
Prompt
   │
   ▼
  LLM
   │
   ▼
 Code
```

The conversation is the state. The markdown plan is the state. The
agent's context window is the state. Which means:

- State becomes **inconsistent** — the plan drifts from the code, the
  conversation drifts from the plan, and nobody can tell which is true.
- Verification is **weak** — "it works" is a claim in prose, not a
  deterministic fact.
- Planning is **textual** — a plan is prose you re-read, not data you
  query, schedule against, or audit.
- The agent is the system — swap the model and you've swapped the
  project's memory.

## The idea

Treat project state as a deterministic data structure.

Forge is a small, frozen, zero-dependency Python kernel that owns a
project's execution state as an event-sourced task graph. Every change
is an event appended to an immutable log. The graph — tasks, statuses,
dependencies, evidence, history — is a deterministic fold over that log.
Undo is truncation. Replay is refolding. Audit is reading the log.

Agents become **clients** of that state, never owners of it:

```
   LLM
   │
   ▼
Proposal          {proposal_id, reason, confidence, events}
   │
   ▼
 Kernel           validate → append → apply
   │
   ▼
Validated State   event-sourced, deterministic, auditable
```

The planner proposes. The kernel decides. The executor writes code and
attaches evidence — it never decides it's done. The reviewer consumes
evidence and emits a verdict — it never touches state directly. Nobody
touches state directly. **Everything is a proposal until the kernel
accepts it.**

That one rule is the line between "an AI assistant with a graph" and "a
deterministic operating system that AI agents can safely use."

## The result

- **A frozen kernel.** The event schema and state machine are v1 and
  stable, like Git's object model. Implementations and plugins change;
  the contract doesn't. Every new kernel feature increases maintenance
  forever, so new features land in plugins instead.
- **A proposal protocol.** Agents emit structured proposals; the kernel
  validates them atomically — whole commit or whole rejection.
- **A compliance suite.** Twelve portable tests map one-to-one to the
  invariants in the spec (I1–I7). They pass against the reference
  implementation *without reading its source*. Any implementation
  claiming to be Forge v1.0 must pass them.
- **An SDK.** `forge.ForgeClient` is the one public surface: `next()`,
  `context()`, `propose()`, `start()`, `attach_evidence()`, `verify()`.
  No graph logic, no replay, no scheduler — the client calls five
  methods, the kernel does the rest.
- **A context contract.** `forge context <task>` hands an agent a
  ~500-token package — Task, Acceptance, Dependencies, Knowledge,
  Relevant Files, Evidence, Constraints — instead of a 20,000-token
  repo dump. This is where the design pays off: agents read a contract,
  not a graph.

## Positioning

Forge does not compete with Claude Code, Codex, or Gemini CLI.

It sits **under** them. Git doesn't know about VS Code or GitHub — those
tools integrate *with* Git. Forge is the same shape: a stable kernel
with a CLI, a Python SDK, and eventually MCP. Any model — Hermes, Claude
Code, Codex, Gemini, or something that doesn't exist yet — plugs in as
one interchangeable client. Above it: intelligence. Below it:
deterministic computing.

The kernel stores what Git can't: project state. Git is the source of
truth for code. Forge is the deterministic source of truth for project
state.
