# Forge Verification

How Forge proves itself. The canonical suite plus focused ad-hoc
checks, run on every milestone.

## Test suite

```
python -m unittest discover -s tests
```

Zero dependencies, Python 3.10+. Full suite: 255 tests (240 in
`tests/`, 15 compliance).
Breakdown:

| Suite | Count | Proves |
| --- | --- | --- |
| `tests/test_planner.py` | 26 | planner protocol: valid + intentionally invalid proposals, kernel verdicts |
| `tests/test_mcp.py` | 26 | MCP wire protocol, tools, faults, official-SDK interop |
| `tests/test_executor.py` | 23 | five-call flow, self-check, expansion, recovery, SDK-only boundary, end-to-end run |
| `tests/test_proof_core.py` | 18 | proof derive/check/bundle core: determinism, byte-identity with tools/ |
| `tests/test_model.py` | 18 | graph model: folding, statuses, priorities |
| `tests/test_reviewer.py` | 17 | three-call flow, judge slot, blocked path, SDK-only boundary, end-to-end run |
| `tests/test_security.py` | 16 | task-id charset, event typing, symlink-safe store, context injection, query recursion |
| `tests/test_sdk.py` | 16 | SDK surface + reference client loop end-to-end |
| `tests/test_query.py` | 16 | query grammar and errors |
| `tests/test_cli.py` | 13 | CLI commands incl. typo'd -d refusal |
| `tests/test_kernel.py` | 12 | kernel ops, undo, merge/export/import |
| `tests/test_store.py` | 8 | append, locks, torn-tail recovery |
| `tests/test_plugins.py` | 8 | plugin command registration |
| `tests/test_proof_cli.py` | 7 | `forge proof` CLI surface |
| `tests/test_stress.py` | 6 | 100k-event fold/replay, concurrency |
| `tests/test_scheduler.py` | 6 | ready ordering, dependency gating |
| `tests/test_context.py` | 4 | context contract package |
| `tests/compliance/test_compliance.py` | 15 | SPEC invariants I1–I7 one-to-one + ROAD_TO_1.0 guards |

## Specification Compliance Suite

`tests/compliance/` is the Specification Compliance Suite: it maps
one-to-one to invariants I1–I7 — malformed proposals, fuzzed event
streams, torn-log crash recovery, atomic proposal commits, replay
identity across hash seeds, scheduler determinism.

Run separately:

```
python -m unittest tests.compliance.test_compliance
```

It found and fixed four real gaps before freeze:

1. Un-stamped proposal events.
2. Torn-tail line merging.
3. Torn-tail seq duplication.
4. Byte/char drift in tail recovery.

Every implementation claiming to be Forge v1.0 must pass it.

## Stress results (M1.5)

- 100k events replay in <1s.
- 5-thread and 4-process concurrent writers, no corruption.
- 5-level expansion.
- Cycle rejection.

## Boundary enforcement

Structural tests read each plugin's source and assert the absence of
kernel internals (`forge.kernel`, `forge.model`, `forge.store`,
`forge.context`, `from .`, `import_events`, `.graph`, `replay(`,
`Store(`, `Kernel(`, `.kernel`, `plugins.`) and, per plugin, the
file-write APIs and gate-override calls. A plugin that touches the
graph directly fails the suite.
