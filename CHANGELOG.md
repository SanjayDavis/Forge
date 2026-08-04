# Forge Changelog

All notable changes to the Forge kernel and its SDK. The kernel contract
(SPEC v1) never tracks this file; this is the project's release history.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [PEP 440](https://peps.python.org/pep-0440/);
the project version is `0.1.0-alpha` (normalized `0.1.0a1`).

## [0.1.0a1] - 2026-08

### Added

- **Plugin command registry.** `forge/plugins.py` — the CLI discovers
  commands through the `forge.commands` entry-point group, so any
  installable package can contribute a subcommand without touching the
  kernel. Known ecosystem commands whose package is missing get an
  install-hint stub (`pip install forge-planner`) instead of an opaque
  argparse error.
- **`forge-planner` distribution.** The reference planner graduated
  from `plugins/planner/` to its own installable package
  (`packages/forge-planner/`, import name `forge_planner`), with its
  own pyproject/LICENSE/README and a `plan` entry point. The `forge
  plan` command now lives in that package — a real client of the SDK,
  installed separately, proving the boundary end to end.
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
