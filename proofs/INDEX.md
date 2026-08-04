# Forge Proof Index

Every Forge Proof follows the standard in [PROOF_SPEC.md](PROOF_SPEC.md). This index is
the comparison surface: one row per proof, identical columns, numbers measured by the
same rules (§5 of the spec). As the corpus grows, Forge becomes harder to dismiss.

Legend: **VPass** = verification passes · **VF** = verification failures ·
**Conf.** = conforms to the Proof Standard. Failure rate per proof =
VF / (VPass + VF).

## Comparison table

| # | Proof | Language | Status | Tasks | Events | VPass | VF | Retries | Reopens | Duration (min) | LLM | Claims | Conf. |
|---|-------|----------|--------|-------|--------|-------|----|---------|---------|----------------|-----|--------|-------|
| 1 | [flask-todo](#proof-1--flask-todo) | Python | completed | 8 | 47 | 9 | 1 | 1 | 1 | 5 | not recorded | C6, C7 | **yes** |
| 2 | subsystem-dense (CHIP-8) *(executing)* | Python | in progress | 9/42 | 165 | 10 | 0 | — | — | 17 | Hermes agent | C1, C2, C7 | — |
| 3 | expression-parser *(planned)* | C++ | — | — | — | — | — | — | — | — | — | C1, C3 | — |
| 4 | rust-cli *(planned)* | Rust | — | — | — | — | — | — | — | — | — | C1, C3 | — |
| 5 | multi-agent *(planned)* | — | — | — | — | — | — | — | — | — | — | C4, C5 | — |

## Claim coverage

| Claim | Criticism answered | flask-todo | CHIP-8 | expr-parser | rust-cli | multi-agent |
|-------|--------------------|:---:|:---:|:---:|:---:|:---:|
| C1 | "Only works on toy examples" | | X | X | X | |
| C2 | "Only works for web apps" | | X | X | X | |
| C3 | "Tied to Python" | | | X | X | |
| C4 | "Can't handle long projects" | | | | | X |
| C5 | "Only works with one agent" | | | | | X |
| C6 | "Just a fancy todo list" | X | X | X | X | X |
| C7 | "Can't handle structured complexity" | X | X | | | X |

An X means the proof's artifacts are expected to support the claim — it becomes binding
the moment the proof is marked conforming.

---

## Proof #1 — Flask Todo

**Language:** Python · **Status:** completed · **Claims:** C6, C7

| Metric | Value |
|--------|-------|
| tasks | 8 |
| events | 46 |
| verification passes | 9 |
| verification failures | 1 |
| failure rate | 10% (1 of 10 attempts) |
| retries | 1 |
| reopens | 1 |
| duration (min) | 5 |
| llm | not recorded |

**Story (replay.md summary):** 8 tasks planned (factory → schema → models → routes →
templates → css → tests → readme) in a clean dependency chain. The run's one genuine
development event: `routes` failed verification because completing an already-done task
returned 404 — `mark_done` conflated "not found" and "already done". The executor
reopened `models`, made completion idempotent, retried `routes`, and verification
passed. Real history, not a paint-by-numbers run.

**Conformance:** **conforming** to `proof-spec-0.1` (backfilled from the original
pre-standard run, Aug 2026). The full artifact bundle is present and the derived
artifacts regenerate from `events.log` alone. The backfill surfaced one real
documentation bug — the README omitted the `flask --app app init-db` step, without
which `POST /add` fails on a fresh checkout (`no such table: tasks`) — fixed as part
of the backfill (see Behavior notes in the proof README).

**Location:** `examples/flask-todo/` (first entry in the corpus).

---

## Proof #2 — Subsystem-Dense Systems Project (CHIP-8) *(planning — executing next)*

**Language:** Python · **Claims:** C1, C2, C7

**Planning phase done (Aug 2026):** `examples/chip8/proposal.json` holds a 42-task,
91-edge decomposition (proposal id `prop_chip8_001`): 8 core subsystems
(memory, registers, stack, timers, RNG, framebuffer, keypad, fontset), the
fetch-decode-execute dispatch core, 22 opcode units, 7 test groups, CLI, README.
Verified acyclic DAG, max depth 6. Execution is live (foundation done: core
subsystems + tests-core, 22/22 tests, events.log seq 1..165, executor = Hermes
agent); remaining: dispatch, opcode units, integration tests, CLI, README.

Why: the proof isn't about emulation — it's about dependency structure. CHIP-8 stresses
Forge structurally: CPU, memory, timers, display, input, ROM loading, and tests are
independent subsystems, which makes a deep, wide dependency DAG. It answers "toy
examples" (C1), "web apps" (C2), and "structured complexity" (C7) at once. Its README
must lead with the subsystem-DAG argument, not with "it's an emulator."

Target shape: ~40–90 tasks, non-trivial event count, at least one genuine verification
failure + retry cycle, full artifact bundle per the standard.

---

## Proof #3 — C++ Expression Parser *(planned)*

**Language:** C++ · **Claims:** C1, C3

Why: first non-Python proof. Lexer → parser → AST → evaluator → REPL, plus tests.
Deliberately small but complete; its job is the language claim, not scale.

---

## Proof #4 — Rust CLI *(planned)*

**Language:** Rust · **Claims:** C1, C3

Why: second non-Python proof. Pairs with #3 to make the "not tied to Python" claim a
pattern rather than an anecdote. CLI with subcommands, error handling, tests.

---

## Proof #5 — Multi-Agent Project *(planned)*

**Claims:** C4, C5

Why: planner/executor/verifier handoffs, reviewer loops, 100+ task scale. This is the
proof that answers "long projects" and "one agent" together. May be split into two
proofs if the 100+ task run and the multi-agent run are cleaner as separate evidence.

---

## Backlog

- [x] Backfill Proof #1 (flask-todo) to conformance — done Aug 2026
- [ ] Proof #2 CHIP-8 — build per standard
- [ ] Proof #3 C++ expression parser
- [ ] Proof #4 Rust CLI
- [ ] Proof #5 multi-agent / 100+ task run
- [ ] Tooling (optional): a `proof-check` script that validates a proof's bundle against
      PROOF_SPEC.md — a convenience, not part of the standard
