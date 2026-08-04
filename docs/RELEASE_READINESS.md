# Forge Release Readiness — M2D

Milestone M2D: SDK audit, public API review, packaging, release
readiness, CI, and architecture review. Kernel: **untouched, frozen at
SPEC v1**. This document records what was verified and why the current
shape is the one being distributed.

## 1. SDK audit (every client, every import)

Rule: an external client imports only the public `forge.*` namespace —
never `forge.kernel`, `forge.store`, `forge.model`, and never mutates
project state directly.

| client | imports | verdict |
|--------|---------|---------|
| `plugins/reference/` (human) | `from forge import ForgeClient` | clean |
| `forge-planner` (packages/forge-planner) | `from forge import ForgeClient, PLANNER_OPS, ProposalError, slugify, validate_proposal` | clean (fixed in M2D: was `forge.sdk.PLANNER_OPS`; graduated to its own distribution in v0.1) |
| `plugins/executor/` | `from forge import ForgeClient, GraphError` | clean |
| `plugins/reviewer/` | `from forge import ForgeClient, GraphError, parse_context` | clean |
| `plugins/mcp/server.py` | `from forge import ForgeClient, GraphError, ProposalError` | clean |
| `plugins/mcp/mcp_client.py` | none (wire protocol only) | clean |
| `forge/cli.py` (CLI) | `forge.kernel`, `forge.store`, `forge.model`, `forge.scheduler` | **by design** — see below |

Findings:

1. **All external clients are SDK-only.** Planner, executor, reviewer,
   reference client, and MCP server operate entirely through the public
   namespace. This is the architectural proof the boundary is real:
   a future client (VS Code, Hermes, Cursor, a Web UI) can be written
   against `forge.ForgeClient` alone.
2. **The CLI uses the kernel directly — deliberately.** The CLI ships
   *inside* the `forge` package; it is the kernel's own first-party
   human interface, not an external client. It covers operations the SDK
   intentionally does not expose to agents (init, undo, export/import,
   log inspection, admin graph edits). It is the only in-package
   consumer of kernel internals, which is correct: the SDK exists to
   keep *external* clients honest, and the CLI is not external. The one
   SDK gap it exposed — `PLANNER_OPS` — was a pure re-export, not a
   kernel need.
3. **One private reach found and closed (M2D).** The planner imported
   `forge.sdk.PLANNER_OPS` directly (a submodule reach, albeit inside
   the SDK). Fixed by exporting `PLANNER_OPS` from the top-level `forge`
   namespace; the planner now imports it like every other client, and
   keeps `ALLOWED_OPS` as a backward-compatible alias.
4. **No client mutates project state directly.** Every mutation in every
   client goes through `ForgeClient` -> `Kernel` -> validated event ->
   `Store.append` under the file lock. Tests may construct `Graph`
   objects in memory (white-box kernel tests — correct), but no client
   writes to `events.log` outside the kernel.

No SDK method was added for speculative reasons. The single change is
the `PLANNER_OPS` re-export, demonstrated by a real client import.

## 2. Public API review (every SDK method)

All `ForgeClient` methods, with the client that uses them:

| method | why it exists | used by | general enough | naming |
|--------|---------------|---------|----------------|--------|
| `next()` | single next work item for any agent/human loop | reference, executor, reviewer, MCP | yes — snapshot dict, no node types leak | yes |
| `context(task_id)` | the Context Contract package (Appendix C) | reference, executor, reviewer, MCP, CLI | yes — fixed YAML shape every client parses | yes |
| `propose(proposal)` | planner protocol commit (SPEC §9), atomic | planner, MCP, CLI | yes — envelope validated, kernel decides | yes |
| `start(task_id)` | claim a task | reference, executor, reviewer, MCP | yes | yes |
| `expand(task_id, children)` | re-split oversized tasks (§10.3), atomic | executor | yes | yes |
| `attach_evidence(task_id, kind, source, detail)` | hard/soft evidence | reference, executor, reviewer, MCP | yes | yes |
| `verify(task_id)` | verifier gate (I6); the kernel decides done | all | yes — no force bypass exposed | yes |
| `verify_fail(task_id, reason)` | reviewer verdict | reviewer, MCP | yes | yes |
| `retry(task_id)` | needs_revision -> in_progress (§10.2) | executor, reviewer | yes | yes |
| `query(expr)` | safe expression subset over the graph | MCP, CLI | yes | yes |
| `progress()` | project summary | CLI, MCP | yes | yes |
| `replay()` | refold from disk | MCP, CLI | yes | yes |

Module-level: `validate_proposal`, `context_package`, `parse_context`,
`to_yaml`, `PLANNER_OPS`, `ProposalError`, `ContextError`, plus
`slugify` (public id rule). Every one is used by at least one client.

Verdict: nothing redundant, nothing missing for the current clients.
`propose` returns `{proposal_id, committed, tasks}` and the SDK never
exposes `verify_pass(force=True)` — the dependency gate is
unbypassable from the SDK by construction. Both are deliberate and
documented.

## 3. Packaging (Phase 3)

- `pyproject.toml`: full metadata (PEP 621) — license `MIT` (PEP 639
  expression; the license classifier was removed because setuptools
  rejects the redundant classifier), classifiers, authors, URLs,
  keywords, `readme = "README.md"`, `license-files = ["LICENSE"]`.
- Console entry point: `forge = "forge.cli:main"` -> `forge --help`.
- Version: `0.1.0a1` in `pyproject.toml` and `forge/__init__.py`;
  git tag `v0.1.0-alpha` matches the PEP 440 normalized form.
- Dependencies: **none.** `dependencies = []` is explicit; the kernel
  is stdlib-only by design (SPEC Appendix A). No extras were added.
- Only the `forge` package ships; `plugins/` is separate products
  (ROADMAP: Repository separation) and is not installed.
- Verified end-to-end: `python -m build` produces sdist + wheel;
  installing the wheel into a clean venv, `forge --help` works, the SDK
  imports, and an init -> create -> expand -> next -> context smoke
  passes against the installed package.

## 4. Release readiness (Phase 4)

- README: current (six-call SDK example, plugin separation, install
  instructions for both PyPI and dev installs).
- Version consistent across `pyproject.toml`, `forge/__init__.py`, and
  the git tag (single source of truth is `forge/__init__.py`).
- `CHANGELOG.md` created (Keep a Changelog format) with the full
  pre-alpha history and the M2D entry.
- `LICENSE` exists (MIT, Sanjay Davis, 2026) and is referenced from
  pyproject; included in the wheel/sdist (`dist-info/licenses/LICENSE`).
- GitHub release notes: tags exist for every milestone; release notes
  can be generated from the tag list + CHANGELOG at publish time.

## 5. CI (Phase 5)

`.github/workflows/ci.yml` — two jobs:

- **test** (3.10/3.11/3.12): install, canonical suite with
  `-W error` (all warnings are errors, not just ResourceWarning),
  compliance suite with `-W error`, CLI smoke.
- **package** (3.10/3.11/3.12): `python -m build`, install the wheel
  into a clean venv, verify `forge --help` + version + SDK imports from
  the installed package, run an SDK/CLI smoke against it, and verify
  the sdist installs too.

No deployment step. Verification only, as specified.

## 6. Architecture review (external maintainer's eye)

What holds up:

- **The boundary is real and now proven.** Every external client is
  SDK-only; the kernel has no back door. This is the single most
  important property for a distributed platform and it is enforced by
  structure (imports) rather than convention.
- **Event sourcing kept honest.** I3 (no derived state in the log),
  torn-tail recovery, atomic proposals — the compliance suite maps
  one-to-one to spec invariants, which is exactly what a frozen
  contract needs.
- **Zero dependencies is a feature, not an accident.** No supply-chain
  surface on a project whose whole point is determinism.

Accidental complexity / things to watch (none blocking):

- `forge/__init__.py` re-exports a lot of kernel internals
  (`Kernel`, `Graph`, `Store`, scheduler functions) for convenience.
  This is fine for the CLI's sake but means `import forge` pulls the
  whole kernel namespace. Long term, consider whether first-party
  convenience exports should be narrowed — external clients only need
  the SDK names.
- `docs/API.md` documents the kernel API and the SDK in one file; the
  SDK section is the one external developers should read. Splitting
  into `docs/SDK.md` would sharpen the story for new clients (flagged,
  not done — the audit is the deliverable).
- The CLI duplicates a few scheduler/context helpers locally
  (`_node_label`, tree printing). Small, contained, and first-party;
  acceptable.
- `context.py` (kernel markdown/JSON context) and `sdk.py`
  (Context Contract YAML) both build "context" but for different
  consumers. The distinction is documented (API.md, CLI.md) and is not
  a blocker; a future SDK-focused doc pass should make it explicit that
  the YAML contract is THE client package.

Distribution blockers found and fixed by this milestone: none in the
kernel; the packaging metadata was minimal (now complete), the CI did
not verify packaging (now does), and the API doc was missing two SDK
methods (now matches the implementation).

## Summary

Forge is installable (`pip install forge-kernel` -> `forge --help`), its SDK is
the complete public contract (proven by every existing client, one
re-export closed the only private reach), CI verifies tests +
compliance + packaging with warnings as errors, and the next milestone
can focus entirely on the MCP server.
