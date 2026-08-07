# Replay — Proof #4: Rust CSV CLI (`rcli`)

## Goal

Build Proof #4, the second half of the non-Python generalization milestone (C3):
a complete CSV statistics CLI in modern Rust — hand-rolled parser (quoted
fields, escaped quotes, CRLF/LF, blank-line skipping, positioned errors), a
stats engine, `describe`/`head` subcommands, custom error handling with
distinct exit codes, and 48 cargo unit + integration + edge/stress tests —
executed end to end through the public Forge SDK in `examples/rust-cli/`.

## Outcome

**15/15 tasks verified, 0 verification failures, 0 retries.** `cargo build`
produces the `rcli` binary with zero warnings; `cargo test` runs **48 checks**
all green (24 unit + 6 CLI integration via the real binary + 5 CLI arg + 8
edge/stress + 5 stats). Cross-language usage of Proof #3 (C++) recurs here in
Rust: the `.gitignore` root-anchoring lesson is independently re-derived and
re-applied as a regression.

## Timeline (from events.log)

| seq | event | task |
|---|---|---|
| 1–15 | `task_created` × 15 | full DAG planned (`proposal.json`), single entry point `project-skeleton` |
| 16–41 | `dependency_added` × 26 | proposal DAG edges binding the 15 tasks |
| 42–44 | `verification_passed` | project-skeleton (Cargo.toml, root-anchored `.gitignore`) |
| 45–47 | pass | error-def (`RcliError` + `Display` + `From<io>`) |
| 48–56 | passes | csv-parser, stats-engine, cargo-build (gate: build + `--help`) |
| 57–71 | passes | describe, head, cli-args, csv-parser-tests, stats-engine-tests |
| 72–74 | pass | main-wiring (`stats numbers.csv` → `score mean=4.1`) |
| 75–83 | passes | fixtures, cli-tests (exit codes), edge-cases (stress) |
| 84–86 | pass | readme — full bundle, conformance target reached |

`max_ready_queue = 6` — reached at seq 56 when `cargo-build` completed and the
independent describe/head/cli-args/csv-parser-tests/stats-engine-tests frontier
(all depending only on cargo-build or already-done modules) opened at once.

## Turning points

1. **Byte-loops don't decode UTF-8 (the "Ã© bug").** The first parser walked
   raw bytes and did `bytes[i] as char`, so every non-ASCII UTF-8 sequence
   became two separate Unicode scalars — the unicode fixture read back as
   `cafÃ©`. It was invisible on ASCII-only input, so it only surfaced through
   the unicode fixture; the parser was rewritten to iterate `input.chars()`
   and an explicit UTF-8 edge-case test now guards it. This is the proof's
   headline catch: a real, subtle, class-of-bug detection exactly where the
   proof needed the tests to bite.
2. **The blank-line phantom.** A blank line emitted a stray empty row. Row
   emission now guards on `row_started || field non-empty`. Test: `"a\n\nb"`.
3. **`.gitignore` / lockfile discipline.** `/target` must be root-anchored
   (a bare `target` could match a source dir — the Proof #3 regression re-
   caught here), and `Cargo.lock` must be committed for a binary crate so a
   clean checkout builds identically.
4. **Windows native-vs-MSYS toolchain trap.** rustup/GNUTarget and the
   installer's `sh` download both failed writing to `/tmp/...`; the working
   install ran the native `rustup-init.exe` with a real `C:/...` temp path.
   Later, a cargo run routed through a `bash -lc` PATH export under native
   python silently dropped the toolchain — cargo has to be invoked directly.

## Task order (as run)

| # | id | verification evidence |
|---|----|----------------------|
| 1 | project-skeleton | `cargo build` + Cargo.toml/.gitignore (root-anchored `/target`) |
| 2 | error-def | `cargo build` (compiles `RcliError`/Display/From<io>) |
| 3 | csv-parser | `cargo build` (compiles `parse`) |
| 4 | stats-engine | `cargo build` (compiles `ColumnStats`) |
| 5 | cargo-build | `cargo build` + `--help` exits 0 + `Cargo.lock` committed |
| 6 | describe | `cargo build` (compiles `describe`) |
| 7 | head | `cargo build` (compiles `head`) |
| 8 | cli-args | `cargo build` (compiles `parse_args`) |
| 9 | csv-parser-tests | `cargo test --test csv_tests` green |
| 10 | stats-engine-tests | `cargo test --test stats_tests` green |
| 11 | main-wiring | `rcli stats fixtures/numbers.csv` → `score mean=4.1` |
| 12 | fixtures | `check_fixtures.py` — every fixture parses, `empty.csv` → exit 1 |
| 13 | cli-tests | `cargo test --test cli_tests` green (exit codes 0/1/2) |
| 14 | edge-cases | `cargo test --test edge_cases` green (unicode, 1000 rows, 10k line) |
| 15 | readme | 8 sections present, claims C1 & C3 listed |

## Full event log (86 events, contiguous seq 1–86)

- tasks: 15 · events: 86 · passes: 15 · failures: 0 · retries: 0 · duration: 1 min

- seq 1–15   task_created          ×15 (project-skeleton … readme)
- seq 16–41  dependency_added      ×26 (proposal DAG edges)
- seq 42–86  15×( task_started → evidence_added → verification_passed )
- seq 86     verification_passed   readme — run complete, 100%

## Claims addressed

- **C1 — real pipeline, not a toy**: a hand-rolled CSV parser with quoted
  fields, doubled-quote escaping, CRLF/LF tolerance, blank-line handling, and
  positioned error reporting is the kind of real, edge-case-heavy module that
  makes the proof credible.
- **C3 — language / execution-model generalization**: Rust uses a genuinely
  different toolchain (rustc 1.97.1, cargo, `x86_64-pc-windows-gnu`, MSYS2 gcc
  linker) and build/test layout than both the Python (Proof #1) and C++ (Proof
  #3) toolchains — the second independent non-Python execution path.

## Lessons

1. Byte-loops don't decode UTF-8 — iterate `chars()`, or every multibyte
   sequence turns to mojibake ("é" → "Ã©").
2. A blank line's row must not be emitted (guard on "line started").
3. Cargo.lock must be committed for a binary crate; `target` must be
   root-anchored in `.gitignore`.
4. On Windows, native cargo runs cleanly when invoked directly; routing it
   through a `bash -lc` PATH export under native python drops the toolchain.