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
0.1.0a6 — cross-platform hardening release.

- SDK surface guard (`tests/test_surface.py`): pins the public `forge`
  namespace and every `ForgeClient` method signature; any accidental
  API change now fails CI. This file is the public-API changelog going
  forward — the referee ROAD_TO_1.0.md names for the rc1 90-day freeze.
- CI expanded to 3 OS × 4 Python: ubuntu/windows/macos × 3.10–3.13,
  with per-OS ffmpeg installs and an OS-independent smoke test.
  Python 3.13 classifier added to forge-foundation.
- Windows locale-codec fixes completed everywhere: all remaining test
  subprocess helpers decode UTF-8 explicitly, and the reference clients
  (executor, reviewer, human, forge-mcp's MCP client) force UTF-8
  stdout like the CLI already did.
- `forge proof check`: honest ffprobe gap — a present demo.mp4 without
  ffprobe now reports the missing tool instead of a misleading
  "unreadable" error; the swarm conformance tests skip with that
  explanation on machines without ffmpeg (CI installs it).
- New CONTRIBUTING.md quickstart for external users; tag-triggered
  Release workflow publishes GitHub Releases from this file and uploads
  all four distributions to PyPI via Trusted Publishing.
