# Forge Changelog

All notable changes to the Forge kernel and its SDK. The kernel contract
(SPEC v1) never tracks this file; this is the project's release history.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [PEP 440](https://peps.python.org/pep-0440/);
alpha `0.1.0a4` is the current release.

## [0.1.0a4] - 2026-08-08

### Added

- **Proof #5 `swarm` — 100+ task multi-agent stress proof, conforming.**
  114 tasks, 612 events, 4 concurrent agents, MaxQ 28, 62 s wall-clock,
  three genuine `verification_failed` cycles documented verbatim. Answers
  C4 ("can't handle long projects") and C5 ("only works with one agent").
  `ROAD_TO_1.0.md`'s `multi-agent` evidence box is checked; the corpus is
  complete through Proof #5 and the a4 gate is earned.
- **`claims_claimed` event support.** The kernel's event validator now
  understands `claims_claimed` — the op PROOF_SPEC §5 reads for
  `metrics.json` `claims`; flask-todo's log carries it, so released tooling
  could not previously replay that proof. `forge replay` and `forge-mcp`
  now open the four v1-grammar proofs (flask-todo, expr-parser, rust-cli,
  swarm). Proof #2's log predates the v1 grammar (see chip8 README) and is
  intentionally rejected by the kernel's fail-loud schema; the proof
  tooling (`proof-check.py`, `proof-derive.py`) is its authoritative
  reader.

### Changed

- **Version bump to `0.1.0a4`** across `forge-foundation`,
  `forge-planner`, and `forge-mcp-base`. Per the publish-only-after-evidence
  policy this is **prepared and tagged, not uploaded to PyPI**; the
  previous live release remains `0.1.0a2`. The kernel contract (SPEC v1)
  is untouched.
- **Evidence-system integrity (release-readiness audit).**
  `tools/proof-derive.py` infers `language` from implementation-file
  references inside `events.log` (it was hardcoded to `python`) and falls
  back to the proposal's authored `claims` field for proofs whose runtime
  predates `claims_claimed`. Proofs #3/#4 (`expr-parser`, `rust-cli`) now
  regenerate byte-identically including `language` (C++, Rust) and
  `claims` (C1, C3); Proof #5's `metrics.json` `claims` reads `["C4","C5"]`
  matching `proofs/INDEX.md`. `PROOF_SPEC.md` §5 derivation rule amended.
  The `claims` field was added to the `proposal.json` inputs of Proofs
  #3/#4/#5 — authored evidence, not log edits.
- **MCP server `serverInfo.version`** now reports the installed
  distribution's version from package metadata instead of a hardcoded
  `0.1.0-alpha` literal.
- **Doc consistency sweep.** README/CHANGELOG/INDEX/verification numbers
  aligned with the measured corpus (217 tests, 15 compliance tests,
  Proof #1 events 47, `not recorded`); README links `ROAD_TO_1.0.md`.
- **Compliance guard hardened.** `test_road_to_1_0_checklist_matches_index`
  searches only `#proof-`-anchored comparison-table rows, so the
  Milestones table can no longer shadow a proof label (it masked the
  `multi-agent` drift this release fixes).

### Fixed

- The compliance command documented in `ROAD_TO_1.0.md`
  (`python -m unittest tests.compliance`) silently ran zero tests; docs
  now use the module invocation that actually executes the 15-test suite
  (what CI runs).
- Proof #2's `metrics.json` records `forge_version` `0.2.0` — an
  unpublished in-development version the run actually used; the chip8
  README now explains the label against the released ladder
  (0.1.0a1 → 0.1.0a2 → 0.1.0a3).

## [0.1.0a3] - 2026-08-07

### Added

- **Generalization corpus complete (Phase 1 closed)**: the non-Python
  datapoints the architecture question needed. **Proof #3** `expr-parser`
  (C++, 17 tasks, 94 checks, `-Wall -Wextra` clean) and **Proof #4**
  `rust-cli` (Rust, std-only, 15 tasks, 48 checks) are both **conforming**;
  the corpus now spans Python, C++, and Rust. `proofs/INDEX.md` gains a
  Milestones table; `ROAD_TO_1.0.md` evidence list is fully checked through
  Proof #4.
- **Proof #5 designed** (`proofs/PHASE2_DESIGN.md`): the 100+ task
  multi-agent stress proof answering C4/C5 — the next release gate
  (`0.1.0a4`, per `ROAD_TO_1.0.md`).

### Changed

- **Version bump to `0.1.0a3`** across `forge-foundation`, `forge-planner`,
  and `forge-mcp-base`. Per the publish-only-after-evidence policy this is
  **prepared and tagged, not uploaded to PyPI**; the previous live release
  remains `0.1.0a2`. The kernel contract (SPEC v1) is untouched.

## [0.1.0a2] - 2026-08-06

### Added

- **CHIP-8 proof conforming** (`proofs/INDEX.md` #2): 42 tasks, 259 events, 42
  checks green; closes the "toy examples" and "web apps only" gaps prior to the
  non-Python proofs. Backlog checkbox flipped to reflect the completed run.

### Changed
- **Version bump to `0.1.0a2`** across `forge-foundation`, `forge-planner`,
  and `forge-mcp-base` (all published to PyPI). Purely a confidence marker for
  the now-conforming CHIP-8 proof; the kernel contract (SPEC v1) is untouched.

## [0.1.0a1] - 2026-08

### Changed

- **Core distribution renamed `forge-kernel` → `forge-foundation`.** `forge`,
  `forge-sdk`, `forge-core`, and `forge-kernel` are all squatted on PyPI by
  unrelated projects, so the core ships under `forge-foundation`. The import
  name (`forge`) and CLI command (`forge`) are unchanged. `forge-planner` and
  `forge-mcp` now declare `forge-foundation` as their dependency.

### Published (2026-08)

- **`forge-foundation` 0.1.0a1**, **`forge-planner` 0.1.0a1**, and
  **`forge-mcp-base` 0.1.0a1** are live on PyPI. `pip install
  forge-foundation forge-planner forge-mcp-base` → `forge --help` and the
  `forge-mcp` server both verified from a clean environment. The MCP server
  ships as `forge-mcp-base` because `forge-mcp` and `forge-mcp-server` are
  squatted on PyPI by unrelated projects; `forge-mcp` remains the console
  script.

### Added

- **Plugin command registry.** `forge/plugins.py` — the CLI discovers
  commands through the `forge.commands` entry-point group, so any
  installable package can contribute a subcommand without touching the
  kernel. Known ecosystem commands whose package is missing get an
  install-hint stub (`pip install forge-planner`) instead of an opaque
  argparse error.
- **`forge-mcp` distribution.** The MCP server graduated from
  `plugins/mcp/` to its own installable package
  (`packages/forge-mcp/`, import name `forge_mcp`) with its own
  pyproject/LICENSE/README and a `forge-mcp` console script
  (`forge-mcp -d PROJECT`). Stdlib-only JSON-RPC 2.0 server, six
  tools, one SDK call each — a transport, nothing more. `plugins/mcp/`
  removed from the core tree.
- **`forge-planner` distribution.** The reference planner graduated
  from `plugins/planner/` to its own installable package
  (`packages/forge-planner/`, import name `forge_planner`), with its
  own pyproject/LICENSE/README and a `plan` entry point. The `forge
  plan` command now lives in that package — a real client of the SDK,
  installed separately, proving the boundary end to end.
- **PyPI distribution naming.** The core distribution is published as
  `forge-foundation` (import name and CLI command stay `forge`), because
  the names `forge`, `forge-sdk`, `forge-core`, and `forge-kernel` are
  taken on PyPI by unrelated projects. `forge-planner` depends on
  `forge-foundation` — so `pip install forge-planner` resolves to this
  SDK, not a foreign package.
- **SDK surface completed (M2D).** `PLANNER_OPS` is now exported from the
  top-level `forge` namespace, so every client (planner included) imports
  only `forge.*` — no submodule reaches, no kernel internals.
- **Packaging metadata.** Full `pyproject.toml`: license (MIT, PEP 639),
  classifiers, authors, URLs, keywords, explicit zero-dependency policy,
  and the `forge` console entry point.
- **CHANGELOG** (this file), release-readiness documentation, and an
  architecture review (`docs/RELEASE_READINESS.md`).

### Changed

- **CI hardens (M2D).** GitHub Actions now runs the canonical suite and
  the compliance suite with `-W error` (all warnings are errors), and a
  new packaging job verifies `pip install` + `forge --help` + the full
  smoke surface on the built wheel/sdist.
- **CI (v0.1):** the test job installs both `forge` and `forge-planner`
  editable; the packaging job builds and installs both wheels and
  verifies `forge plan` works against the installed package (and that a
  bare `forge` install prints the install hint for `plan`).

### Fixed

- `docs/API.md` SDK table was missing `expand()` and `retry()` — the
  documented surface now matches `forge.sdk.ForgeClient` exactly.

## [0.1.0a0] — unreleased pre-alpha history

Prior milestone work (see `docs/ROADMAP.md` for per-milestone detail):

- **M1 — Core kernel.** Graph, event log, scheduler, context builder,
  CLI, verification flow. Zero deps, no AI.
- **M1.5 — Stress + freeze.** Schema v1 frozen, official Kernel API,
  inspector, query language, priority, cross-process locking,
  merge/export/import.
- **v1.0 — Kernel complete.** `docs/SPEC.md` is the contract:
  invariants I1–I7, freeze policy (Appendix A). No new kernel features
  without a spec change and version bump.
- **Compliance — kernel passes its own spec.** `tests/compliance/`
  maps one-to-one to invariants I1–I7 (malformed proposals, fuzzed
  streams, torn-log recovery, atomic commits, replay identity,
  scheduler determinism).
- **M2B — Planner plugin.** Reference planner: goal in,
  `{proposal_id, reason, confidence, events}` out, committed atomically.
- **Context API.** `forge context <task>` / `ForgeClient.context()`:
  the ~500-token contract package (Task / Description / Acceptance /
  Dependencies / Knowledge / Relevant Files / Evidence / Constraints).
- **SDK — ForgeClient.** `forge/sdk.py` is the one public surface
  every client is allowed to touch.
- **M3 — Executor plugin.** Five-call executor flow with byte-exact
  artifact self-checks; `expand()` for re-splitting oversized tasks.
- **M4 — Reviewer plugin.** Three-call review flow; soft evidence only;
  never overrides the dependency gate.
- **M5 — MCP server.** JSON-RPC 2.0 over stdio, stdlib-only, six tools,
  one SDK call each.
- **M5.1 — Security hardening.** Path-traversal-safe task ids, symlink
  guards on the store, control-character rejection in contract fields.
