# Plugins

Everything that is not the kernel lives here. The kernel is frozen
(docs/SPEC.md Appendix A); this directory is where it grows.

Each plugin is a client of the official API (`forge.kernel.Kernel`) and
the protocols in the spec. A plugin never touches `events.log` directly
and never mutates the graph except through the kernel.

| directory   | role                                          | spec     |
|-------------|-----------------------------------------------|----------|
| `planner/`  | goal -> Proposal; emits events only          | §9 (Planner Protocol) |
| `executor/` | task package -> artifacts + hard evidence    | §10 (Executor Protocol) |
| `reviewer/` | acceptance judgment -> soft evidence         | §11 (Reviewer Protocol) |
| `mcp/`      | wire protocol exposing the kernel API        | (M5, last) |

Status:
- M2A (Planner Protocol) is specified (SPEC §9) and enforced by the
  compliance suite (`tests/compliance/`).
- **M2B (Planner Plugin) is DONE.** `planner/` ships a reference planner
  (`ReferencePlanner`) plus protocol validation (`validate_proposal`).
  It emits only proposals (SPEC §9.1); the kernel decides. Tested by
  `tests/test_planner.py` (23 tests): valid proposals commit atomically,
  intentionally invalid ones are rejected by the protocol check or by
  the kernel on commit — whole or nothing.
- M3 (Executor) is next: the `ForgeClient` SDK + `forge next`/`forge context`.

The reference planner is deliberately AI-free: it proves the boundary.
An LLM planner is a drop-in replacement behind the same protocol —
same proposal shape, same commit path, same distrust.
