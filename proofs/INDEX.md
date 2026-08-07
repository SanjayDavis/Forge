# Forge Proof Index

Every Forge Proof follows the standard in [PROOF_SPEC.md](PROOF_SPEC.md). This index is
the comparison surface: one row per proof, identical columns, numbers measured by the
same rules (§5 of the spec). As the corpus grows, Forge becomes harder to dismiss.

Legend: **VPass** = verification passes · **VF** = verification failures ·
**Conf.** = conforms to the Proof Standard. Failure rate per proof =
VF / (VPass + VF).

## Milestones (phases)

| Phase | Question | Evidence | Status |
|-------|----------|----------|--------|
| 0 | Forge is real | core + SDK + planner + MCP + CLI milestones (tags `m2b`…`m5.1`); Proofs #1/#2 | **closed** |
| 1 | "Forge is Python-specific" / "only web apps / toys" (C1–C3) | Proofs #3 (C++) + #4 (Rust) — non-Python generalization datapoints | **closed** — evidence for `0.1.0a3` |
| 2 | "Can't handle long projects / one agent" (C4, C5) | Proof #5: 100+ task multi-agent stress proof (*designed*, see [PHASE2_DESIGN.md](PHASE2_DESIGN.md)) | **next** |
| 3 | publish-per-evidence gate | dists already live for foundation/planner/mcp; each release ships behind its phase evidence | gate |

`0.1.0a3` — **Generalization** — is the tagged release-point whose evidence corpus is the
closing of Phase 1 (C++ and Rust proofs added to the Python-established corpus). Per the
publish-only-after-evidence policy it is prepared and tagged, not uploaded (see the
version note in the Proof #4 entry). `0.1.0a4` will carry the Phase 2 multi-agent milestone.

## Comparison table

| # | Proof | Language | Status | Tasks | Events | MaxQ | VPass | VF | Retries | Reopens | Duration (min) | LLM | Claims | Conf. |
|---|-------|----------|--------|-------|--------|------|-------|----|---------|---------|----------------|-----|--------|-------|
| 1 | [flask-todo](#proof-1--flask-todo) | Python | completed | 8 | 47 | 1 | 9 | 1 | 1 | 1 | 5 | not recorded | C6, C7 | **yes** |
| 2 | [CHIP-8 emulator](#proof-2--chip-8-emulator) | Python | completed | 42 | 259 | 23 | 42 | 2 | 0 | 0 | 44 | not recorded | C1, C2, C7 | **yes** |
| 3 | [expression-parser](#proof-3--c-expression-parser) | C++ | completed | 17 | 96 | 3 | 17 | 0 | 0 | 0 | 19 | not recorded | C1, C3 | **yes** |
| 4 | [rust-cli](#proof-4--rust-cli) | Rust | completed | 15 | 86 | 6 | 15 | 0 | 0 | 0 | 1 | not recorded | C1, C3 | **yes** |
| 5 | multi-agent *(planned)* | — | — | — | — | — | — | — | — | — | — | C4, C5 | — |

## Claim coverage

| Claim | Criticism answered | flask-todo | CHIP-8 | expr-parser | rust-cli | multi-agent |
|-------|--------------------|:---:|:---:|:---:|:---:|:---:|
| C1 | "Only works on toy examples" | | X | X | X | |
| C2 | "Only works for web apps" | | X | | X | |
| C3 | "Tied to Python" | | | X | X | |
| C4 | "Can't handle long projects" | | | | | X |
| C5 | "Only works with one agent" | | | | | X |
| C6 | "Just a fancy todo list" | X | X | | X | X |
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

## Proof #3 — C++ Expression Parser

**Language:** C++ · **Status:** completed · **Claims:** C1, C3

|| Metric | Value |
||---|--------|-------|
|| tasks | 17 |
|| events | 96 |
|| verification passes | 17 |
|| verification failures | 0 |
|| failure rate | 0% (17 of 17 attempts) |
|| retries | 0 |
|| max_ready_queue | 3 (at seq 66, when ast-def passed) |
|| duration (min) | 19 |
|| llm | not recorded |

**Planning (Aug 2026):** `examples/expr-parser/proposal.json` holds the 17-task,
27-edge decomposition (proposal id `prop_expr_parser_001`): foundation
(skeleton, Makefile), frontend (token-def, error-report, lexer, ast-def,
precedence-climbing parser, print-ast), runtime (context, evaluator), app (REPL
CLI), and test suites (lexer, parser, evaluator, CLI end-to-end, edge-cases).
A verified acyclic DAG, depth 7, single entry point `project-skeleton`,
`max_ready_queue = 3`.

**Story (replay.md summary):** executed substrate → frontend → runtime → app →
tests in 7 levels. All 17 tasks passed verification on first claim; every
mid-implementation error was caught before the verification gate. Three real
engineering events: (1) unary-vs-exponent precedence — first pass bound `-2^2`
as `(-2)^2` (C-style); the proposal contract wanted the math convention
`-(2^2)`, fixed by moving unary into the precedence loop at level 25; (2) a
"…unqualified-id before '&'" compiler-noise class that turned out to be an
undeclared exception type (`expr::ParseError` without an `error.h` include) —
found across four files at once by grepping catch clauses; (3) the 13-case CLI
suite went entirely red on Windows because `system()` uses `cmd.exe`, which
rejects `./`-paths — switched to bare `expr`. The harness also caught a wrong
*test* expectation, not wrong code (`floor(2.7)+ceil(2.1)==5` was the test's
arithmetic error; the code was correct). Final: 94 checks green
(13 lexer + 18 parser + 25 evaluator + 13 CLI + 25 edge-case) under `-Wall
-Wextra` with zero warnings, `make`-driven, no Python in the build path.

**Conformance:** **conforming** to `proof-spec-0.1`. `proof-check` passes;
`graph.json`/`metrics.json`/`graph.png` derive from `events.log` alone.
Post-conformance verification caught a `.gitignore` defect that had silently
excluded `include/expr/` (headers); root-anchored patterns, committed the
headers, clean-clone `make test` → 94/94. See replay.md.
This proof is the C++ half of the non-Python generalization release (`0.1.0a3`).

**Location:** `examples/expr-parser/` (third entry in the corpus).

---

## Proof #4 — Rust CLI

**Language:** Rust · **Status:** completed · **Claims:** C1, C3

||| Metric | Value |
|||---|--------|-------|
||| tasks | 15 |
||| events | 86 |
||| verification passes | 15 |
||| verification failures | 0 |
||| failure rate | 0% (15 of 15 attempts) |
||| retries | 0 |
||| max_ready_queue | 6 (at seq 56, when cargo-build passed) |
||| duration (min) | 1 |
||| llm | not recorded |

**Planning (Aug 2026):** `examples/rust-cli/proposal.json` holds the 15-task,
26-edge decomposition (proposal id `prop_rust_cli_001`): foundation
(skeleton, cargo build/test pipeline), frontend (error-def, hand-rolled CSV
parser + unit tests, stats engine + tests, describe, head), app (hand-rolled
CLI arg parsing, main wiring with exit codes), data (fixtures), tests
(CLI integration, edge/stress), and the README. A verified acyclic DAG,
depth 5, `max_ready_queue = 6`. Std-only (no external crates), so the build
is hermetic.

**Story (replay.md summary):** executed skeleton → modules → build gate →
tests → wiring → fixtures → integration/stress → readme in one pass. All 15
tasks passed verification on first claim, 0 failures, 0 retries. The code
itself fought back twice before the verification gate — both caught by the
proof's own test suites: (1) the byte-oriented parser cast each byte to a
char, silently double-encoding every non-ASCII field ("é" became "Ã©"); a
unicode fixture through the parser caught it, rewritten to iterate
`input.chars()`; (2) blank lines left a phantom empty row — row emission now
guards on "line actually started". The Proof #3 `.gitignore` lesson
recurs here as an independent regression: root-anchored `/target` only.
Final: **48 checks green** (24 unit + 6 CLI integration via the real binary
+ 5 CLI arg + 8 edge/stress + 5 stats) on rustc/cargo 1.97.1
(`x86_64-pc-windows-gnu`, MSYS2 gcc linker), zero warnings, `Cargo.lock`
committed, no Python in the build path (run.py is a thin shell-out wrapper).

**Conformance:** **conforming** to `proof-spec-0.1`. `proof-check` passes;
`graph.json`/`metrics.json`/`graph.png` derive from `events.log` alone
(86 events, contiguous seq 1–86). Toolchain lesson preserved in replay.md:
on Windows, cargo must be invoked directly — routing it through a
`bash -lc` PATH export under native python silently drops the toolchain.
This proof is the Rust half of the non-Python generalization release
(`0.1.0a3`), pairing with #3 to make the language-independence claim a
pattern rather than an anecdote.

**Location:** `examples/rust-cli/` (fourth entry in the corpus).

---

## Proof #5 — Multi-Agent Project *(planned)*

**Claims:** C4, C5

Why: planner/executor/verifier handoffs, reviewer loops, 100+ task scale. This is the
proof that answers "long projects" and "one agent" together. May be split into two
proofs if the 100+ task run and the multi-agent run are cleaner as separate evidence.

---

## Backlog

- [x] Backfill Proof #1 (flask-todo) to conformance — done Aug 2026
- [x] Proof #2 CHIP-8 — build per standard
- [x] Proof #3 C++ expression parser — conforming Aug 2026
- [x] Proof #4 Rust CLI — conforming Aug 2026
- [ ] Proof #5 multi-agent / 100+ task run
- [ ] Tooling (optional): a `proof-check` script that validates a proof's bundle against
      PROOF_SPEC.md — a convenience, not part of the standard
