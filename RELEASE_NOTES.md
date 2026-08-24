# RELEASE_NOTES.md

This file is generated per release: copy the matching `## [x.y.z]`
section from CHANGELOG.md here (strip the heading level), commit it with
the version bump, and tag. The Release workflow reads this file as the
GitHub Release body.

## How to cut a release

1. Update CHANGELOG.md (`[Unreleased]` -> `[x.y.z] - date`).
2. Copy that section into RELEASE_NOTES.md, replacing the content below
   the marker.
3. Bump versions in the four pyproject.toml files + forge/__init__.py +
   packages/forge-proof/forge_proof/__init__.py.
4. Run the full suite + compliance suite locally.
5. Commit ("release: bump to x.y.z — ..."), tag `vx.y.z`, push both.
6. The Release workflow builds, tests, publishes a GitHub Release from
   RELEASE_NOTES.md, and uploads to PyPI via Trusted Publishing.
   PyPI publishing requires a one-time "pypi" environment on GitHub
   with the trusted-publisher binding for all four projects.

<!---release-notes--->
0.1.0b1 — the external-validation release.

The first beta: the question is no longer "can we reliably release
this?" but "does Forge work for people outside the project?" The kernel
is untouched (SPEC v1, zero API changes). `docs/B1_READINESS.md` is the
objective b1 gate.

- `docs/B1_READINESS.md`: ship prereqs (release automation, the four
  PyPI Trusted-Publisher bindings, Windows packaging evidence, docs
  sufficiency, pre-tag checklist) plus the validation evidence boxes —
  5 independent users and 3 completed projects — that earn this release.
- SDK surface guard committed (`tests/test_surface.py`): pins the public
  `forge` namespace and every `ForgeClient` method signature; the rc1
  freeze referee named by ROAD_TO_1.0.md.
- Release workflow publish step fixed: a6's PyPI publish died on a
  multi-line packages-dir reaching the action as one literal path;
  artifacts now stage into one flat directory before upload.
- Packaging verified beyond CI on Windows: all four distributions built,
  installed into clean venvs, CLI/SDK/MCP-wire smoke green from the
  installed packages.
- Docs audited against the pinned surface: API.md, README, CONTRIBUTING
  match exactly; no undocumented public API.
