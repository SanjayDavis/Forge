# Replay — Proof #3: C++ Expression Parser

## Goal

Build Proof #3, the first half of the non-Python generalization milestone: a
complete expression-parser pipeline (lexer → precedence-climbing parser → AST →
evaluator → REPL) in C++14, with a real test harness and positioned error
reporting, executed entirely through the public Forge SDK in
`examples/expr-parser/`.

## Outcome

**17/17 tasks verified, 0 verification failures, 0 retries.** `make` builds the
`expr` binary and `make test` runs 94 automated checks (13 lexer + 18 parser +
25 evaluator + 13 CLI end-to-end + 25 edge-case) — all green under `-Wall
-Wextra` with zero warnings. The proof is conforming to `proof-spec-0.1`
(claims C1 and C3). 96 events, 19 minutes.

## Timeline (from events.log)

| seq | event | task |
|---|---|---|
| 1–17 | `task_created` × 17 | full DAG planned (`proposal.json`), single entry point `project-skeleton` |
| 52 | `verification_passed` | project-skeleton (dirs, `.gitignore`, `main.cpp` stub) |
| 53–57 | passes | build-system (Makefile); token-def; error-report |
| 58–63 | passes | lexer + lexer-tests (13 cases) |
| 64–75 | passes | ast-def, context (15 builtins), parser + parser-tests (18 cases) |
| 76–84 | passes | evaluator + evaluator-tests, print-ast |
| 85–90 | passes | repl, cli-tests (13 cases) |
| 91–93 | passes | edge-cases (25 stress cases) |
| 94–96 | passes | readme — full bundle, conformance target reached |

`max_ready_queue = 3` — at the widest point three tasks were simultaneously
executable, so execution proceeded in 7 levels of depth.

## Turning points

1. **Unary-vs-exponent precedence.** First pass bound unary minus tighter than
   `^` (C-style), so `-2^2` → `(-2)^2`. The proposal contract required the math
   convention (`-(2^2)` == -4). Fix: moved unary into the precedence loop at
   level 25 (between `* / %` and `^`), which made `-2^2 == -4` and kept `5*-3`
   and `---5` correct. The parser acceptance criterion caught it, exactly as
   designed.
2. **"expected unqualified-id before '&'" — a wrong diagnosis.** The baffling
   compiler noise was just an **undeclared exception type** in `catch` clauses
   (`expr::ParseError` with no `error.h` include). Found by scanning every file
   that caught `ParseError`/`EvalError` without including `expr/error.h` — fixed
   the whole class in one pass (parser_tests, evaluator_tests, edge_cases,
   main).
3. **Windows `system()` is `cmd.exe`, not sh.** CLI tests used `./expr`, which
   `cmd.exe` rejects ("'.' is not recognized"). The whole 13-case CLI suite went
   red at once; switching the command string to bare `expr ` fixed all of them —
   a portability trap invisible on Linux.
4. **A wrong expectation, not wrong code.** `make test` flagged
   `floor(2.7)+ceil(2.1)==5` proudly "failing" while the implementation was
   right — `2+2 == 4`. The harness correctly caught the *test's* arithmetic
   bug. Both sides of the boundary were covered.

## Post-conformance verification catch (Aug 2026)

The proof was declared conforming, and then **focused verification found a real
defect that would have broken a clean consumer checkout**. The proof's
`.gitignore` line `expr` (intended for the build binary) also matched the
`include/expr/` source directory — so all 8 C++ headers were silently excluded:
`git ls-files examples/expr-parser/include/` returned 0 even though the commit
looked complete. `git add examples/expr-parser/` had skipped them without a
warning.

Fix: root-anchored the binary patterns (`/expr`, `/expr.exe`) so they can't
match the source directory, committed the headers, and re-verified the *fixed*
tree independently: clean-clone `make test` → 94/94 checks green, CI green.

The sequence — proof appears complete → focused verification → real defect →
clean checkout would fail → fix → clean checkout → 94/94 → CI green — is
exactly the loop proofs are for. **Verification failures (0 in the log) and
engineering corrections (4 here) are different metrics**; the raw replay stays
the authoritative story, numbers and all.