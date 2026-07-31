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

Status: M2A (Planner Protocol) is specified (SPEC §9) and enforced by
the compliance suite (`tests/compliance/`). The first plugin to land
here is M2B, the planner — the first AI client of the kernel.
