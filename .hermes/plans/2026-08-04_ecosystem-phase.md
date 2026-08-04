# Forge Ecosystem Phase — Plan (Distribution → Adoption)

> **For Hermes:** This is a strategic/phase plan, not a code-implementation
> plan. Execute phase by phase; each phase ends with a verification gate.
> The TDD granularity rules apply only to Phase B (forge-mcp) code tasks.

**Goal:** Move Forge from "installable product" to "adopted product" —
packages on PyPI, one excellent demo, ecosystem packages split out, and
real users attempting real work — with the kernel frozen (no new kernel
features).

**Architecture context:** Kernel frozen at SPEC v1. `forge-kernel` +
`forge-planner` are the only published distributions. MCP server exists
in-tree (`plugins/mcp/server.py`, 257 lines, stdlib-only JSON-RPC 2.0)
and must graduate to its own package. Everything else is distribution,
visibility, and user feedback.

**Tech Stack:** Python 3.10+ (stdlib-only kernel), setuptools + `python -m
build`, twine, GitHub Releases, OBS/ffmpeg (ffmpeg 8.1.2 confirmed
installed), MCP stdio protocol (no `mcp` SDK dependency).

---

## Current State (verified 2026-08-04) — what's ALREADY done

The user's five priorities, checked against reality:

| Priority | Status |
|---|---|
| Kernel frozen / v0.1-alpha declared | ✅ tag `v0.1.0-alpha` + GitHub Release cut (4 artifacts) |
| GitHub Release | ✅ `SanjayDavis/Forge` → Releases → v0.1.0-alpha (2026-08-04) |
| PyPI publish | ⏳ staged but **blocked on user's PyPI account + API token** |
| Demo video | ⏳ screencast-script.md written; recording not done (ffmpeg ready) |
| forge-mcp as separate package | ⏳ exists in-tree at `plugins/mcp/server.py`; not split |
| Get users | ⏳ launch kit drafted (show-hn / reddit / x-thread) |

Additional facts:
- PyPI: `forge` taken (dropseed, active Django project). `forge-kernel` and
  `forge-planner` names are **free** (404 checked 2026-08-04).
- No `~/.pypirc`, no `TWINE_*` env vars, twine not installed. → PyPI
  publish **cannot complete without the user creating an account + token**.
- GitHub orgs `forge`, `forge-project`, `forge-kernel`, `forge-dev`,
  `forgeplatform`, `forgehq` are all **taken**. Free: `forge-ecosystem`,
  `forgefyi`. User owns orgs `Jaabili-Technologies`, `Agent-Dock-Alpha`.
- No `examples/` dir; no Flask anywhere in the repo (release-notes claim
  of a "Flask demo" is aspirational — needs building).
- Launch checklist has one open pre-launch item: replay-number
  reconciliation (`docs/verification.md` says <1s, current runs 1.40-1.56s).

---

## Phase A — Publish to PyPI (external blocker: user action)

**Hard dependency:** The user must create a PyPI account (pypi.org) and an
API token scoped to `forge-kernel` and `forge-planner`. Hermes cannot
create accounts. Everything else can be pre-staged now.

**Task A1 (Hermes, do now):** Pre-stage publish tooling
- `python -m pip install twine`
- Verify `python -m twine check dist/* packages/forge-planner/dist/*` passes
  (long-description renders, metadata valid) — both sdist and wheel.

**Task A2 (user action):** Create PyPI token
- pypi.org → Account settings → API tokens → "Add API token", scope:
  `forge-kernel` + `forge-planner` projects, name `forge-ci`.
- Store as `TWINE_USERNAME=__token__`, `TWINE_PASSWORD=<token>` (user
  holds the secret; never type it into chat).

**Task A3 (Hermes, after A2):** Upload both packages
```bash
twine upload dist/forge_kernel-0.1.0a1.tar.gz dist/forge_kernel-0.1.0a1-py3-none-any.whl
twine upload packages/forge-planner/dist/forge_planner-0.1.0a1.tar.gz packages/forge-planner/dist/forge_planner-0.1.0a1-py3-none-any.whl
```
**Verify:** `pip install forge-kernel forge-planner` in a fresh venv pulls
from PyPI (no `--index-url`), then `forge --help` and the quickstart run.

---

## Phase B — Split `forge-mcp` into its own package

**Objective:** `plugins/mcp/` → `packages/forge-mcp/` as a distribution
`forge-mcp` (import `forge_mcp`), consuming ONLY the public SDK, with its
own test file, keeping the stdlib-only JSON-RPC server unchanged in
behavior.

**Files:**
- Move: `plugins/mcp/server.py` → `packages/forge-mcp/src/forge_mcp/server.py`
- Move: `plugins/mcp/__init__.py`, `plugins/mcp/mcp_client.py` → same layout
- Create: `packages/forge-mcp/pyproject.toml` (name `forge-mcp`, version
  `0.1.0a1`, dependency `forge-kernel`, no other deps; console script
  optional `forge-mcp = forge_mcp.server:main` if one exists)
- Move: `tests/test_mcp.py` → `packages/forge-mcp/tests/test_mcp.py`
  (imports updated to `forge_mcp`)

**Step 1:** Copy tree + write pyproject. **Step 2:** Update imports in
tests and any `__init__` re-exports. **Step 3:** Run moved tests:
```bash
cd packages/forge-mcp && python -W error -m unittest discover -s tests
```
Expected: same pass count as current `tests/test_mcp.py` (check current
count first). **Step 4:** Clean-venv install of the wheel, run the server
one round-trip against a scratch project (next → context → verify).
**Step 5:** Remove `plugins/mcp/` from the core tree; grep for stale
references (`plugins.mcp`, `plugins/mcp`) in code + docs. **Step 6:**
README/CHANGELOG note; commit.

**Note:** MCP server registers no `forge.commands` entry point (it's a
server, not a subcommand) — verify this stays true after the split.

---

## Phase C — `forge-examples` (build the Flask demo the release notes promise)

**Objective:** an `examples/`-style repo/package with 2 runnable demos:
(1) the terminal quickstart loop (already scriptable), (2) a Flask web
page rendering the context contract for a task — proving the SDK works
from a web app.

**Files:** `examples/flask_demo/app.py`, `examples/flask_demo/requirements.txt`
(flask + forge-kernel), `examples/flask_demo/README.md`; a
`forge-examples` README at repo top or a new `forge-examples` repo later.

**Verify:** `flask --app app run` against a scratch Forge project; GET a
task's context contract as HTML; screenshot for the release/demo.

---

## Phase D — Demo video (75-90s, terminal only)

**Files:** `forge-launch/screencast-script.md` (exists —
follow it verbatim), OBS or terminal recording, ffmpeg 8.1.2 available.

**Steps:** record takes 1-4 per script (init → plan → next/context/evidence/
verify → replay), trim to 75-90s with ffmpeg, captions optional. **Verify:**
play once end-to-end; time it; the viewer can follow the loop without
explanation. Upload to YouTube unlisted first, then public at launch.

---

## Phase E — Get users (launch execution)

**Files:** `show-hn.md`, `reddit.md`, `x-thread.md`, `launch-checklist.md`
(all drafted in `forge-launch/`).

**Pre-launch gate:** resolve the replay-number inconsistency
(verification.md <1s vs measured 1.40-1.56s) — pick one number everywhere.
**Then:** publish the release assets, post Show HN + Reddit + X per drafts,
and target the explicit goal: **five real users** installing from PyPI and
attempting a real project. Take notes; do not over-explain; let them break
assumptions.

---

## Phase F — GitHub organization (deferred decision, not now)

User's instinct is right but premature. `forge-project` is taken anyway.
**Recommendation:** stay under `SanjayDavis/Forge` until ≥2 external
packages exist and adoption justifies the move; then take a free name
(`forge-ecosystem` or `forgefyi`) and transfer repos. Record this in the
checklist as a Phase F trigger: "when a second external package ships,
decide org name."

---

## Risks / Open Questions

1. **PyPI token** — the single hard blocker. Everything in Phase A past
   A1 waits on the user's account. (User action required.)
2. **`forge` name collision** — already handled via `forge-kernel`;
   README/install docs updated. Monitor for confusion in user feedback.
3. **Org naming** — most obvious names taken; decision deferred to Phase F
   trigger, candidates `forge-ecosystem` / `forgefyi`.
4. **MCP split risk** — moving `plugins/mcp/` must not break the core
   test suite (215 tests) or the entry-point registry. Verify full suite
   after Phase B, not just the moved tests.
5. **Flask demo** — adds a non-stdlib dep to the ecosystem (fine — it's
   an example, not the kernel). Keep the kernel itself zero-dependency.
6. **Replay number** — must be reconciled before any public post cites it.

---

## Sequence & Gates

```
A1 (stage twine/check) ──► B (forge-mcp split; full suite green) ──►
C (examples/Flask demo) ──► D (video) ──► [user: PyPI token] ──► A3 (upload;
PyPI clean-install verified) ──► E (launch; 5 users) ──► F (trigger-gated)
```

Each phase ends with its verify step before the next begins. Kernel
receives **zero** new features — only packaging/docs/test moves.
