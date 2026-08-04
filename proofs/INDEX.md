# Forge Proof Index

Every Forge Proof follows the standard in [PROOF_SPEC.md](PROOF_SPEC.md). This index is
the comparison surface: one row per proof, identical columns, numbers measured by the
same rules (§5 of the spec). As the corpus grows, Forge becomes harder to dismiss.

Legend: **VPass** = verification passes · **VF** = verification failures ·
**Conf.** = conforms to the Proof Standard. Failure rate per proof =
VF / (VPass + VF).

## Comparison table

| # | Proof | Language | Status | Tasks | Events | MaxQ | VPass | VF | Retries | Reopens | Duration (min) | LLM | Claims | Conf. |
|---|-------|----------|--------|-------|--------|------|-------|----|---------|---------|----------------|-----|--------|-------|
| 1 | [flask-todo](#proof-1--flask-todo) | Python | completed | 8 | 47 | 1 | 9 | 1 | 1 | 1 | 5 | not recorded | C6, C7 | **yes** |
| 2 | [CHIP-8 emulator](#proof-2--chip-8-emulator) | Python | completed | 42 | 259 | 23 | 42 | 2 | 0 | 0 | 44 | not recorded | C1, C2, C7 | **yes** |
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

## Proof #2 — CHIP-8 Emulator

**Language:** Python · **Status:** completed · **Claims:** C1, C2, C7

| Metric | Value |
|--------|-------|
| tasks | 42 |
| events | 259 |
| verification passes | 42 |
| verification failures | 2 |
| failure rate | 4.5% (2 of 44 attempts) |
| retries | 0 (failures model retry as re-verification) |
| max_ready_queue | 23 (at seq 173, when cpu-fde passed) |
| duration (min) | 44 |
| llm | not recorded |

**Planning (Aug 2026):** `examples/chip8/proposal.json` holds the 42-task,
91-edge decomposition (proposal id `prop_chip8_001`): 8 core subsystems
(memory, registers, stack, timers, RNG, framebuffer, keypad, fontset), the
fetch-decode-execute dispatch core, 22 opcode units, 7 test groups, CLI,
README — a verified acyclic DAG, depth 5, executed by the Forge executor.

**Story (replay.md summary):** the foundation (9 subsystems + tests-core, 22
tests) landed clean; execution then built the ROM loader, the high-nibble
FDE dispatch, all 22 opcode units (each verified by its test group), the
remaining test groups, the headless CLI, and the README. Two genuine failure
cycles are preserved in the journal: (1) the FDE dispatch handed units the
raw opcode instead of decoded operands — `op_ld_i` set `I = 0xA123` for
`0xA123`, 22 test errors, fixed by moving decode into the dispatch table;
(2) suite wiring under `discover -s tests` (top-level imports broke relative
imports) plus five wrong test assertions, fixed with a top-level `_util`
helper and canary-based two-step skip tests. Final: 66 unit/integration
tests green, including a real ROM run end-to-end.

**Conformance:** **conforming** to `proof-spec-0.1`. `proof-check` passes;
`graph.json`/`metrics.json`/snapshots regenerate byte-identically from
`events.log` alone (verified by double-derive hash match).

**MaxQ interpretation:** `max_ready_queue = 23` is the widest
simultaneously-executable frontier — reached at the moment `cpu-fde`
completes, when the 22 opcode units (each depending only on the FDE core +
one subsystem) all become ready at once. Against flask-todo's serial chain
(MaxQ 1), this is the first quantitative read on what wide, deep dependency
structure does to an execution frontier. The evolving graph is snapshotted
under `examples/chip8/demo/snapshots/` (01-foundation → 06-cli-readme).

**Location:** `examples/chip8/` (second entry in the corpus).

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
