# Replay — chip8

**Goal.** Build a complete, test-backed CHIP-8 interpreter (memory, CPU with
22 opcode units, 64x32 framebuffer, hex keypad, timers, ROM loader) plus a
headless CLI, entirely planned, executed, and verified as IRREVERSIBLE
evidence for Proof #2 of the Proof of Forge corpus. The point of this proof
over flask-todo: a wide, dependency-dense DAG and precise machine semantics
that a wrong implementation cannot fake.

**Outcome.** 42 tasks · 259 events · 42 verification passes · 2 failures ·
max_ready_queue 23. All tasks completed; status: `completed`. (The journal
models retries as `verification_failed` followed by a successful re-verify
rather than a distinct `task_retried` event, so the derived `retries` counter
is 0 while the two failure cycles are captured in `verification_failures`.)

---

## Timeline

### Proposal

`proposal.json` (id `prop_chip8_001`, confidence 0.8) decomposed the emulator
into 42 tasks: 9 core subsystems, the fetch-decode-execute core, 22 opcode
units, 7 test groups, CLI, and README. It claims C1, C2, C7.

### Planning (seq 1–135)

All 42 tasks created (seq 1–42). 91 dependency edges added (seq 43–133).
The core subsystems fan into `cpu-fde`, which fans into every opcode unit,
which each feed a test group:

```
memory registers stack timers rng display keypad fontset
   ↘                     cpu-fde                       ↙
     flow(7) alu(4) mem(6) display(2) input(2) timers(2)
        ↘            ↘            test groups            ↙
             cli-run → readme
```

`proposal_committed` and `claims_claimed` close planning (seq 1–2 of the
journal; the DAG in `graph.json`).

### Foundation (seq 136–165)

Nine subsystems + `tests-core` executed cleanly: project-skeleton, memory,
fontset, registers, stack, timers, rng, framebuffer, keypad, tests-core —
10 tasks, 0 failures, 17 minutes (17:34→17:52 UTC).

### Execution (seq 166–259)

ROM loader, then the FDE core, then all 22 opcode units (each paired with its
test group), the six remaining test groups, the CLI, and the README.

Two failures were hit and are preserved verbatim in the journal:

1. **cpu-fde (seq 170–174).** The first combined suite run returned **22
   errors**: the FAMILY dispatch handed each unit the *raw opcode* instead of
   decoded operands — `op_ld_i` set `I = 0xA123` for opcode `0xA123`. Fixed by
   moving decode into the dispatch table (units now receive `x`, `y`, `nn`).
   This is the FDE's data-contract bug, caught by the opcode unit tests, not
   by inspection.
2. **tests-flow (seq 238–240).** The suite wiring had two problems: (a) under
   `python -m unittest discover -s tests` modules import **top-level**, so
   relative imports failed (6 errors); (b) five assertions were wrong — skip
   tests asserted after a single step (which cannot prove a skip), the BCD
   expectation was incorrect, and draw expectations assumed the wrong bit
   order. Fixed via a top-level `_util` helper and corrected assertions.

Verification is the ground truth: 66 unit/integration tests, including a real
ROM (`tests/roms/smoke.ch8`) loaded and run end-to-end.

---

## Metrics (derived, deterministic)

Every value below is a field of `metrics.json`, recomputed by
`proof-derive.py` from `events.log` — verified byte-identical across two
consecutive runs and cross-checked by an independent replay of the log:

| Metric                       | Value |
| ---------------------------- | ----: |
| tasks                        | 42    |
| events                       | 259   |
| verification passes          | 42    |
| verification failures        | 2     |
| max_ready_queue              | 23    |
| max_ready_queue_at (seq)     | 173 (cpu-fde passed) |
| duration (wall, min)         | 44    |

Graph-shape facts that `proof-render-graph.py` reports from the same DAG
(not additional metrics): 91 dependency edges, DAG depth 5.

`max_ready_queue = 23` is the widest simultaneously-executable frontier. It is
worth spelling out how it gets there: after `cpu-fde` lands (seq 173), the 22
opcode units form a wide bank of mutually-independent leaves (each depends
only on the FDE core + one subsystem), so 22+ of them are ready at once before
any test group can verify them. That is the emulator's structural parallelism
— fan-out the sequential web-app proof could not exhibit.

## Turning points

1. **FDE data contract bug (seq 170–174).** The CPU dispatch handed each
   opcode unit the raw opcode instead of decoded operands — `op_ld_i` set
   `I = 0xA123` for `0xA123`. Twenty-two test errors surfaced it instantly:
   the tests, not inspection, owned the machine semantics. The fix moved all
   decode into the dispatch table.
2. **Suite wiring + assertion bugs (seq 238–240).** `discover -s tests`
   imports modules top-level, breaking relative imports (6 errors), and five
   assertions were wrong as authored (skip tests that could not prove a skip,
   a bad BCD expectation, and draw tests that assumed the wrong bit order).
   Corrections: a top-level `_util` helper and canary-based two-step skip
   tests.
3. **ROM data at the end of *instructions*.** The smoke ROM's sprite data
   sits two bytes past where a first estimate put it (it trails the final
   `JP`); `LD I` must point at the true data address. Only the integration
   test + the ASCII framebuffer dump made the mismatch visible.
4. **The graph is wider than the plan phase suggested.** The foundation-only
   frontier implied `max_ready_queue ≈ 8`; the *complete* C7-true frontier is
   **23**, driven by the independent opcode-unit bank. The metric only stops
   moving when the graph is complete.

## Artifacts

`events.log` is the only authoritative input; `graph.json`, `metrics.json`,
`graph.png`, `demo.mp4`, and the snapshots under `demo/snapshots/` are all
derived from it. Reproduce with the commands in `README.md` §5.