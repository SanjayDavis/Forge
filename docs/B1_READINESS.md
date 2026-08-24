# Forge 0.1.0b1 Readiness — the external-validation gate

`0.1.0b1` is the confidence-ladder step whose question is **"Does Forge
work for people outside the project?"** (see `ROAD_TO_1.0.md`). This
document is the objective, checkable gate for that step: what must be
true before the release ships, and what evidence earns it afterwards.
Like `ROAD_TO_1.0.md`, a checked box with no backing evidence is a bug.

Two halves:

- **Ship prereqs** — engineering work; when these are green, cutting the
  tag publishes `0.1.0b1` of all four distributions automatically.
- **Validation evidence** — real-world facts about *other* people using
  Forge. These cannot be manufactured by tooling; they are the actual b1
  gate per `ROAD_TO_1.0.md`.

---

## Part 1 — Ship prereqs

### 1a. Release automation

- [x] Tag-triggered Release workflow runs both suites on the tagged
      commit before building (`release` job) — verified on `v0.1.0a6`.
- [x] **Publish-step bug fixed** (this document's reason to exist): the
      `v0.1.0a6` Release run ([run 32651484495], 2026-08-23) failed in its
      `pypi` job with `FileNotFoundError: ... 'dist/\npackages/
      forge-planner/dist/...'` — the action received the multi-line
      `packages-dir:` block as one literal path. The publish step now
      stages all eight artifacts into a single flat directory
      (`dist-staging/`) and points `packages-dir:` at it — works with
      every version of `pypa/gh-action-pypi-publish`, no feature
      dependence. Rehearsed locally: 8 artifacts staged, twine 8/8.
- [x] GitHub Release job succeeded on `v0.1.0a6` (4 distributions × 2
      artifacts attached).

### 1b. Trusted Publishing bindings (PyPI side — user actions)

> **State, 2026-08-24:** the `0.1.0b1` version bump itself is committed
> on master (versions, CHANGELOG, RELEASE_NOTES) and its artifacts were
> built + battery-tested locally. The only remaining ship action is the
> four bindings below, then `git tag v0.1.0b1 && git push origin
> v0.1.0b1`.

The a6 run also failed the OIDC exchange itself with
`invalid-publisher: valid token, but no corresponding publisher`, so the
following four bindings must be created once on PyPI before any tag can
publish (each project → *Publishing* → *Add a new pending publisher*;
use **exactly** these values):

| PyPI project | Owner | Repository | Workflow | Environment |
|---|---|---|---|---|
| `forge-foundation` | `SanjayDavis` | `Forge` | `release.yml` | `pypi` |
| `forge-planner` | `SanjayDavis` | `Forge` | `release.yml` | `pypi` |
| `forge-mcp-base` | `SanjayDavis` | `Forge` | `release.yml` | `pypi` |
| `forge-proof` | `SanjayDavis` | `Forge` | `release.yml` | `pypi` |

Notes:

- The workflow already declares `environment: pypi` and
  `permissions: id-token: write`; nothing to change in-repo for this.
- The GitHub `pypi` environment should have **no reviewers** so tags can
  publish unattended.
- After adding all four bindings there is nothing left to configure:
  pushing tag `v0.1.0b1` runs suites → builds → attaches artifacts to a
  draft GitHub Release from `RELEASE_NOTES.md` → uploads all four
  distributions to PyPI via OIDC.

### 1c. Packaging verified beyond CI

CI's `package` job proves Linux only; the following was reproduced by
hand on Windows against the locally built `0.1.0a6` artifacts and holds
for any tag whose content passes the same suite:

- [x] All four sdists + wheels build (`python -m build`, root + three
      subpackages); `twine check` 8/8 PASSED.
- [x] Clean venv installs of the four wheels: `forge --help`,
      `import forge` (`__version__`), SDK imports
      (`ForgeClient, PLANNER_OPS, validate_proposal, ProposalError,
      ContextError, parse_context, context_package`),
      `from forge_planner import ReferencePlanner`,
      `forge-mcp --help`, `forge_mcp.ForgeMCPServer` + 6 `TOOLS`,
      `forge proof --help`, `import forge_proof`.
- [x] CLI smoke from the installed package: `init` → `plan --commit` →
      `next`.
- [x] SDK smoke against the installed wheel (`next` → `context`
      containing `Constraints:`).
- [x] MCP wire smoke against the installed server: stdio JSON-RPC
      `initialize` / `tools/list` (exact six tools) / `tools/call`.
- [x] sdist installs into its own clean venv; `forge --help` works.
- [x] Bare-install behavior: without `forge-planner`, `forge plan`
      prints the `pip install forge-planner` hint instead of crashing.
- [ ] Repeat this battery against the actual `v0.1.0b1` artifacts right
      after the first successful automated publish (one command block,
      recorded in the release notes or this file).

### 1d. Docs sufficiency

- [x] `CONTRIBUTING.md` quickstart verified end-to-end against installed
      wheels (install line, 60-second project commands, MCP wiring).
- [x] `docs/API.md` SDK table matches the pinned surface exactly (12
      methods, module-level names); README examples use only pinned API.
- [x] Public surface guard (`tests/test_surface.py`) in CI — any drift
      between docs and reality fails tests.

## Pre-tag checklist (run every release)

```bash
python -W error -m unittest discover -s tests          # full suite
python -W error -m unittest tests.compliance.test_compliance
python -m build && python -m build packages/forge-planner \
  && python -m build packages/forge-mcp && python -m build packages/forge-proof
python -m twine check dist/* packages/*/dist/*
# bump versions in 4 pyproject.toml files + forge/__init__.py, update
# CHANGELOG.md + RELEASE_NOTES.md, commit, then:
git tag v0.1.0b1 && git push origin master v0.1.0b1
```

Watch the Release run until both jobs are green; if `pypi` fails with
`invalid-publisher`, re-check the table in §1b (workflow filename and
environment name must match character-for-character).

---

## Part 2 — Validation evidence (the actual gate)

Per `ROAD_TO_1.0.md`, `0.1.0b1` is earned by **5 independent users AND
3 completed projects** — independent = built something usable without
1:1 author coaching; completed = a finished, committed artifact derived
from Forge's planner/executor. Track candidates here as they appear.

- [ ] User 1 — (name/handle, install date, what they built)
- [ ] User 2 —
- [ ] User 3 —
- [ ] User 4 —
- [ ] User 5 —
- [ ] Completed project 1 — (link to artifact, who built it)
- [ ] Completed project 2 —
- [ ] Completed project 3 —

When all boxes above are checked, cut `0.1.0rc1`: freeze the public
surface (the guard makes the pin explicit), require ≥1 merged external
PR, and start the 90-day stability clock toward `1.0.0`.

[run 32651484495]: https://github.com/SanjayDavis/Forge/actions/runs/32651484495
