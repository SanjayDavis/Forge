# Proof #3: C++ Expression Parser

## 1. What was built

A complete expression-parser pipeline in C++14: a lexer that tokenizes numbers
(integers, decimals, scientific notation), identifiers, operators, and parens; a
precedence-climbing parser producing an AST (right-associative `^`, unary
operators binding between `*` and `^` so `-2^2` is `-(2^2)`); a tree-walking
evaluator with a variable context and 15 builtin math functions plus `pow(2,3)`;
positioned error reporting for both parse and eval failures; and a dual-mode CLI
(single-shot `./expr "2+3"` and an interactive REPL with a hidden `:ast`
debug command). Everything builds with plain `make` (GCC 6.3 / MinGW, no cmake),
and 94 automated checks run via `make test`.

## 2. Why this proof exists

- **C1 — real constraints:** this is a non-trivial language front-end with real
  engineering constraints: precedence/associativity semantics, error
  *positions* (caret rendering), scientific-notation lexing, arity-checked
  function calls, and a cross-cutting test harness that exercises lexer,
  parser, evaluator, CLI, and stress cases.
- **C3 — not tied to Python:** the entire pipeline is implemented and verified
  in C++14, compiled and run by `g++` under `make`, with zero Python in the
  build path. This proof is the first half of the "non-Python generalization"
  release.

## 3. Final architecture

```
        +----------------+      +----------------+
 src/   |  lexer.cpp     | ---> |  parser.cpp    |      include/expr/
        |  (tokens)      |      |  (precedence   |      token.h error.h
        +----------------+      |   climbing)    |      ast.h lexer.h parser.h
                                +-------+--------+      context.h evaluator.h
                                        |               print.h
                                +-------v--------+
                                |  evaluator.cpp | ---> context.cpp (vars + builtins)
                                +-------+--------+
                                        |
                                +-------v--------+
                                |  main.cpp      |  REPL + single-shot CLI
                                +----------------+
```

Subsystems:

- **frontend** — `token.h`, `lexer.cpp` (token stream), `ast.h` (node kinds +
  factories), `parser.cpp` (Pratt-style precedence climbing), `print.cpp`
  (AST pretty printer).
- **runtime** — `context.h/.cpp` (variable map, `pi`/`e`, 15 builtin math
  functions), `evaluator.cpp` (tree walk; `EvalError` on div-by-zero, unknown
  variable/function, bad arity).
- **app** — `main.cpp` (single-shot mode + REPL).
- **tests** — `tests/*.cpp` (lexer, parser, evaluator, CLI end-to-end, stress)
  aggregated by `tests/main.cpp` into one `expr_tests` binary.
- **foundation** — `Makefile` (wildcard-driven build), `.gitignore`.

Dependency arrows: `lexer -> parser -> evaluator -> main`; `context -> evaluator`;
`ast -> parser/print`; everything compiles against `token.h`/`error.h`.

## 4. Commands

```sh
make          # build ./expr from src/*.cpp
./expr "2+3"  # single-shot: prints 5, exit 0; errors -> stderr, exit 1
./expr        # interactive REPL (quit/EOF to exit); try ":ast 2+3*4"
make test     # build and run ./expr_tests (all 94 checks)
make clean    # remove build artifacts
```

All commands work from a clean checkout; the only toolchain requirement is a
C++14 compiler (`g++`) and GNU `make`.

## 5. Reproduce

- **Forge version:** 0.1.0a2 (public SDK `ForgeClient`; proposal id
  `prop_expr_parser_001`, confidence 0.8).
- **Planner/executor:** human-driven execution via the public SDK — every task
  was claimed (`start`), implemented, verified (`make test` as hard evidence),
  and marked `verification_passed`; failures were recorded as `verify_fail` +
  `retry` when tests genuinely failed.
- **Seed:** "Decompose a C++ expression parser for Proof #3 ... 17 tasks across
  foundation/frontend/runtime/tests/app/docs with a 19-edge dependency DAG."
  See `proposal.json` in this directory for the full task DAG.
- **Toolchain:** `g++ (MinGW.org GCC-6.3.0-1)`, GNU make (chocolatey), Windows.

## 6. Artifact index

| Artifact | Path | What it is |
|---|---|---|
| Proposal | `proposal.json` | 17 tasks + 27 dependency edges, SDK-validated |
| Event log | `events.log` | full run transcript, contiguous `seq` 1..N |
| Graph | `graph.json` | derived task graph (states, deps, outcomes) |
| Graph image | `graph.png` | rendered DAG visualization |
| Replay | `replay.md` | human-readable run story |
| Metrics | `metrics.json` | derived run metrics |
| Screenshots | `screenshots/` | CLI + REPL evidence captures |
| Demo | `demo.mp4` | screen capture of the run |
| Source | `src/ include/ tests/ Makefile` | the proof itself |

## 7. Behavior notes

- **Unary precedence is a design decision, not an accident:** `-2^2` evaluates
  to `-4` (`-(2^2)`), matching the math convention, *not* C's `(-2)^2`. Unary
  operators live *inside* the precedence loop at level 25 — tighter than
  `* / %` (20), looser than `^` (30).
- **`%` follows `fmod` semantics** (sign follows dividend): `-7%3 == -1`.
- **`1e` lexes as `1` then `e`** (the constant), not a malformed exponent —
  chosen over erroring so partial input degrades to valid tokens.
- **The `system()`-based CLI tests must invoke `expr`, not `./expr`:** on
  Windows, `system()` shells out to `cmd.exe`, which rejects forward-slash
  relative paths. This is a Windows-only trap caught by the tests themselves.
- **GCC 6.3's `printf` format checker doesn't know `%zu`** — positions are
  printed via `%lu` casts to stay warning-clean under `-Wall -Wextra`.
- **`std::variant` is unavailable** on GCC 6.3's libstdc++; the AST uses a
  tagged struct with `std::shared_ptr` children (C++14).

## 8. Lessons learned

- **The proof standard's event-gated workflow (start -> verify -> verify_fail)
  catches real process bugs**: forgetting to `start` a task surfaced a
  `GraphError` from the kernel's own invariant checks (I6) — the SDK enforces
  the protocol, which is exactly what a public SDK should do.
- **Missing includes produced the most confusing compiler errors of the run**
  (`expected unqualified-id before '&'` in `catch` clauses when the exception
  type was undeclared). A `grep` for "catches ParseError without including
  error.h" found the whole class in one pass — worth doing before the first
  compile, not after.
- **A one-line test expectation bug (wrong mental arithmetic) was caught by the
  harness, not the code**: `floor(2.7)+ceil(1.2) == 4`, my expected `5` was
  wrong — the test suite's job is to catch errors on either side of the
  boundary.
- **For Forge**: the Windows `cmd.exe` incompatibility with `./`-prefixed
  commands in `system()` is a portability wart worth documenting in the
  standard's behavior-notes guidance; it would have been invisible on Linux.
