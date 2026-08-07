# Proof #4 — `rcli`: a Rust CSV statistics CLI

## 1. What was built
A from-scratch Rust command-line tool (`rcli`) that parses CSV and computes
per-column statistics. It is the **second non-Python proof** for Forge (after
Proof #3, the C++ expression parser), exercising the entire Forge pipeline in
a completely different language and build system (cargo/rustc rather than
g++/make).

- Hand-rolled CSV parser: quoted fields, doubled-quote escaping, CRLF/LF, blank
  lines, positioned error reporting (no external crate — hermetic, std-only).
- Statistics engine with even/odd-median handling, `n/a` for non-numeric cells.
- `describe` / `head` subcommands with deterministic output.
- Custom `RcliError` enum + `Display`, clean `From<io::Error>`, distinct exit
  codes (0 success / 1 data/io / 2 usage).
- 48 tests: 24 unit + 6 CLI integration (real binary) + 5 CSV + 8 edge/stress
  + 5 stats.

## 2. Why this proof exists
Forge's central claim is that a single proposal → SDK → executor →
verification → derive → check pipeline generalizes. Proof #1 (Python) and
Proof #3 (C++) already showed two languages with two build systems. Proof #4
shows the pipeline again in **Rust**, adding the strongest independent
generalization signal so far:

- **Claim C1 — the pipeline works for real** (not a toy): a hand-rolled CSV
  parser with edge cases (quotes, CRLF, unicode, positioned errors) is exactly
  the kind of real, non-trivial module the proof needs to be credible.
- **Claim C3 — language/execution-model generalization**: C++ (Proof #3) used
  g++ + Make + the GNU offline flow; **Rust uses cargo + rustc + the MSYS2 gcc
  toolchain** — a genuinely different compiler toolchain, build system, package
  layout, and test runner. Two distinct non-Python toolchains together
  generalize the language-independence claim far better than either one alone.

The .gitignore lesson from Proof #3 (a bare `target` pattern would have matched
a source dir) recursively re-applies here as **its own regression: root-anchored
`/target`**, independently catching the same class of defect again.

## 3. Final architecture
```
main.rs          CLI entry: env args -> parse_args -> dispatch; exit codes
   |   |   |   \
   |   |    \    \
  cli.rs        parse_args -> Command {Stats,Describe,Head}
   csv.rs       parse() -> Vec<Vec<String>>  (positional errors)
   stats.rs     column_stats / stats_all -> ColumnStats
   describe.rs  describe() -> String
   head.rs      head() -> String (re-quoting)
   error.rs     RcliError enum (io|parse|empty|usage) + Display + From<io>
   lib.rs       public modules root
```
Dependency arrows: `main -> {cli, csv, stats, describe, head, error}`;
`csv, stats, describe, head, cli -> error`. All modules depend on `error` only;
nothing else depends on `main`. No external crates.

## 4. Commands
```bash
# build (zero warnings on stable)
cargo build
# run tests (48) — cargo records each suite by name
cargo test
# the CLI (stats | describe | head)
cargo run --quiet -- stats  fixtures/numbers.csv
cargo run --quiet -- describe fixtures/mixed.csv
cargo run --quiet -- head    fixtures/quoted.csv -n 2
# or via the thin wrapper (kept out of the build path)
python run.py stats fixtures/numbers.csv
```
exit codes: `0` success, `1` data/io error, `2` usage error (`--help` → 0).

## 5. Reproduce
- Forge version: **0.1.0a2** (this proof was authored against the SDK at that tag)
- Proposal: `prop_rust_cli_001` (examples/rust-cli/proposal.json)
- Toolchain: rustc/cargo `1.97.1` stable, target `x86_64-pc-windows-gnu`,
  linker gcc (MSYS2) — no external crates on PATH. Tested on Windows 10.
- From a clean checkout (Cargo.lock committed): `cargo build`, `cargo test`

## 6. Artifact index
| path | description |
|------|------|
| `proposal.json` | committed proposal (15 tasks, claims C1 & C3) |
| `src/{lib,main,cli,csv,error,stats,describe,head}.rs` | 8 source files |
| `Cargo.toml` | package `rcli`, edition 2021, lib + bin |
| `Cargo.lock` | committed binary lockfile |
| `.gitignore` | root-anchored `/target` only |
| `tests/csv_tests.rs` | CSV error positions |
| `tests/stats_tests.rs` | stats known-values |
| `tests/edge_cases.rs` | stress: 1000 rows, 10k-char line, unicode |
| `tests/cli_tests.rs` | real-binary exit codes / stderr |
| `fixtures/*.csv` | numbers, mixed, quoted, header-only, crlf, empty, unicode |
| `demo/transcript.txt` | real captured terminal run |
| `run.py` | thin CLI wrapper (libary code is pure Rust) |

## 7. Behavior notes
- First record treated as header for stats/describe/head (data = `rows[1..]`).
- stats emits `name: count=N sum=.. mean=.. median=.. min=.. max=..` with
  Rust `{}` f64 rendering and `n/a` for non-numeric columns.
- describe emits one line per column then `file: R data rows, C columns`.
- head re-quotes fields containing comma/quote/newline; output round-trips
  through the parser.
- UTF-8 header/field names are preserved exactly; parse iterates `chars()`,
  never raw bytes.
- Pathological input (10k-char line, 1000 rows) completes without panic.

## 8. Lessons learned
1. **Byte-loops don't decode UTF-8.** The first parser cast each byte to a char
   (`bytes[i] as char`), silently turning `é` (0xC3 0xA9) into "Ã©". A unicode
   fixture run through the byte-oriented parser caught it; the parser was
   rewritten to iterate `input.chars()`, and an explicit UTF-8 edge case test
   now guards it.
2. **The blank-line phantom.** Row emission must guard on "line actually
   started", otherwise a blank line leaves a stray empty row. Test `"a\n\nb"`.
3. **`/target` must be root-anchored**, and Cargo.lock must be committed for a
   binary crate (a reproducible clean checkout).
4. **Native Windows binaries and MSYS paths disagree.** curl-under-sh and the
   installer script failed writing to `/tmp/...`; pointing both at a real
   `C:/...` temp path and running the native `.exe` (bypassing the script's
   internal downloader) is what actually installed the toolchain.

---

Claim IDs addressed: **C1** (real viability), **C3** (language non-Python,
compile-time toolchain) . See `proofs/PROOF_SPEC.md`.