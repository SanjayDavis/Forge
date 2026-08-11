# forge-proof

Reference proof evidence tooling for [Forge](https://github.com/SanjayDavis/Forge):
a stdlib-only, kernel-free CLI that turns a raw `events.log` into a complete
[Proof Standard](https://github.com/SanjayDavis/Forge/blob/master/proofs/PROOF_SPEC.md)
artifact bundle — no manual steps, no LLM in the loop.

```
forge proof check   <dir>   validate a bundle against the §6 checklist
forge proof derive  <dir>   derive graph.json/metrics.json/replay facts from events.log (§5)
forge proof replay  <dir>   render replay.md (Goal/Outcome/Timeline/Turning points)
forge proof bundle  <dir>   emit the full bundle + validate (net-new artifacts only;
                            curated README/replay.md/media are never clobbered,
                            derived artifacts are verified byte-identical)
```

Installing this package registers the `forge proof` command through the
`forge.commands` entry-point group — same mechanism as `forge plan` from
forge-planner.

Design constraints (Proof Standard §7 / repo plan):
- **stdlib-only**: no runtime dependencies; `graph.png` rendering uses
  matplotlib+networkx when present in the invoking python, otherwise a
  clear hint instead of a crash.
- **kernel-free**: never imports `forge`; the event log is read as raw
  JSON lines, so the proof pipeline cannot disturb project state.
- **reproducible**: derived artifacts are a pure function of `events.log`
  — byte-identical across runs and byte-identical to the canonical
  `tools/proof-derive.py` (pinned by tests).