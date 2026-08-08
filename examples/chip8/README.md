# Proof #2 — CHIP-8 Emulator

## 1. What was built

A complete, stdlib-only CHIP-8 interpreter (4 KiB memory, 16 registers,
64x32 framebuffer, hex keypad, delay/sound timers, 35-opcode instruction
set with quirks-free semantics) plus a headless CLI that runs any `.ch8`
ROM, traces executed opcodes, and dumps ASCII framebuffer frames. No
windowing, no third-party dependencies — the whole machine runs
deterministically from a terminal.

```
examples/chip8/
  chip8/            the emulator (8 subsystems + 22 opcode units)
    memory.py       registers.py   stack.py   timers.py
    rng.py          display.py     keypad.py  fontset.py
    rom.py          cpu.py         cli.py
    ops/            flow, alu, mem, display, input, timers units
  tests/            core + alu + flow + display + input + mem + rom (64 tests)
  tests/roms/       smoke.ch8 — a real 19-byte program
  README.md         this file
  events.log        execution journal (the raw evidence)
  graph.json        derived DAG (42 nodes, depth 5)
  metrics.json      derived metrics (incl. max_ready_queue)
  replay.md         derivation notes for this bundle
  proposal.json     the original 42-task plan
  demo/             transcript + intermediate graph snapshots
  demo.mp4          terminal-style video of a live headless run
  graph.png         the task DAG, rendered
```

## 2. Why this proof exists

Proof #1 (flask-todo) showed Forge planning an 8-task web app and executing
it end-to-end. A single small CRUD app proves the happy path, but it cannot
distinguish "Forge can plan small sequential projects" from "Forge can plan
real systems". CHIP-8 is the second data point:

- **Wide fan-out** — 8 subsystems plus 22 opcode units (42 tasks, 91
  dependency edges) force the planner to interleave many parallel lines of
  work, not just sequence them.
- **Real semantics** — opcodes have precise, testable machine behaviour
  (carry flags, borrow, sprite XOR collision, BCD). A wrong register
  assignment is caught by a test, not by taste.
- **A live artifact** — the deliverable *runs*: `python -m chip8
  tests/roms/smoke.ch8` executes a real program, traces it, and paints a
  real framebuffer.

The claim being tested: *the same pipeline that produced a conforming Flask
todo app also produces a conforming, test-backed CPU emulator, with the
execution journal honestly recording what happened — including the failures.*

## 3. Final architecture

```
                ┌──────────────────────────────────────────┐
                │               chip8.cpu (cpu-fde)         │
                │  fetch → decode → dispatch by high nibble │
                └───────┬───────┬───────┬───────┬──────────┘
                        │       │       │       │
        ┌───────────────┘       │       │       └───────────────┐
        ▼                       ▼       ▼                       ▼
  chip8.ops.flow        chip8.ops.alu   chip8.ops.mem      chip8.ops.display
  RET JMP CALL SKIPs   6XNN 7XNN 8XYN  ANNN FX1E FX29 FX33 00E0 DXYN
  JP V0                CXNN            FX55 FX65
        ┌───────────────┐       ┌──────┴────────┐       ┌───────┘
        ▼               ▼       ▼               ▼       ▼
  chip8.ops.input  chip8.ops.timers        subsystems:
  EX9E EXA1 FX0A   FX07 FX15 FX18          memory registers stack timers rng
                                          display keypad fontset
```

Key invariants (mirroring the proposal's acceptance criteria):

- `cpu.step()` routes **by high nibble**; each opcode unit is a plain
  function in the file the proposal names.
- The CPU never touches rendering beyond the framebuffer; the CLI is the
  only place that prints.
- All arithmetic wraps at 8 bits; VF carries flags (carry/borrow/shifted
  bit/collision); `draw_sprite` XORs with hardware-style edge wrap.
- `FX55/FX65` use the incrementing-I variant (I advances past the block).

## 4. Commands

```sh
cd examples/chip8

# run the whole suite (66 tests, stdlib unittest)
python -m unittest discover -s tests

# headless run of the smoke ROM, with trace (canonical run.py entry)
python run.py tests/roms/smoke.ch8 --cycles 12 --trace

# run to a fixed frame count and dump the framebuffer as ASCII
python run.py tests/roms/smoke.ch8 --cycles 5 --frame

# deterministic runs (fixed RNG seed)
python run.py tests/roms/smoke.ch8 --cycles 300 --seed 7

# identical via the module entry (`python -m chip8 <rom> ...`)
```

## 5. Reproduce

Everything in this bundle is a pure function of `events.log`:

```sh
cd ..            # repo root (project-kernel)
python tools/proof-derive.py examples/chip8 --forge-version 0.2.0
python tools/proof-check.py examples/chip8
python tools/proof-render-graph.py examples/chip8
python tools/proof-render-demo.py examples/chip8 examples/chip8/demo/transcript.txt demo.mp4
```

Note: `0.2.0` was the unpublished in-development version of the package when this
proof ran (it sits between the a1 and a2 release ladder in the repo; no `0.2.0` tag
or distribution was ever published). The recorded value is the version the run
actually used — the released ladder is 0.1.0a1 → 0.1.0a2 → 0.1.0a3 (see
`CHANGELOG.md`). The log also predates the frozen event grammar
(`docs/EVENTS.md`): it carries `proposal_committed` and its own evidence
vocabulary, so the released kernel rejects it loudly by design (unknown-op /
unknown-field errors on replay). The Proof **tooling** — `proof-check.py`,
`proof-derive.py`, `proof-render-*.py` — replays and verifies it directly; that
is the authoritative reader for this corpus.

`proof-derive` regenerates `graph.json` and `metrics.json` byte-identically
(deterministic; verified in-session by hashing two consecutive runs).
`proof-check` recomputes the same invariants over the raw log
(contiguous sequence, structural validity, canonical events, every task
claimed, all claims evidenced) and reports **CONFORMING**.

The tests themselves are the ground truth for the machine's behaviour:
each opcode unit in `chip8/ops/` has unit tests covering its flags and edge
cases, and `tests/test_rom.py` loads the real `smoke.ch8` ROM and runs it
end-to-end.

## 6. Artifact index

| Artifact      | What it is                                   | Produced by            |
| ------------- | -------------------------------------------- | ---------------------- |
| `events.log`  | 200+ raw execution events (the evidence)     | the executor           |
| `graph.json`  | 42-node task DAG (successors, depth, queue)  | `proof-derive.py`      |
| `metrics.json`| tasks, edges, failures, retries, max_ready_queue | `proof-derive.py` |
| `graph.png`   | rendered DAG                                 | `proof-render-graph.py`|
| `demo.mp4`    | terminal-style video of a headless run       | `proof-render-demo.py` |
| `replay.md`   | derivation notes                             | `proof-derive.py`      |
| `proposal.json`| the 42-task plan (task ids, deps, acceptance)| the planner           |

## 7. Behavior notes

- **Quirks-free semantics**: 8XY6/8XYE shift the register being written;
  VF is a pure flag register; FX55/FX65 advance I.
- **Sprite XOR + wrap**: pixels wrap at 64x32 like the original hardware;
  a draw that toggles any pixel off sets VF (collision) — verified by
  `test_draw_collision_sets_vf` and `test_draw_wraps_horizontally`.
- **Key wait**: `FX0A` blocks by rewinding PC until a key is pressed
  (standard emulator approach) — `test_fx0a_blocks_then_stores`.
- **Determinism**: seeded RNG (`RNG(seed=...)`) makes runs reproducible;
  the CLI accepts `--seed`.
- **Failures are evidence too**: the journal records two genuine failure
  cycles — (a) the CPU dispatch passed raw opcodes instead of decoded
  operands (22 test errors; fixed in the dispatch table), and (b) the first
  test-suite wiring attempt broke under `discover -s tests` (relative
  imports; switched to a top-level helper). Both are visible in
  `events.log` as `verification_failed` / retry pairs.

## 8. Lessons learned

1. **Dispatch-by-nibble keeps opcode units dumb.** Handing each unit fully
   decoded operands (`x`, `y`, `nn`) made every unit a one-liner that a
   test can pin down; all decoding lives in one table. The original mistake
   — handing the raw opcode to units — produced 22 test errors and was the
   cheapest kind of bug to catch: the tests said so immediately.
2. **A ROM is a contract between the assembler and the loader.** The first
   smoke ROM pointed `LD I` two bytes past its sprite data (miscounted the
   instruction length); the emulator ran "correctly" against the wrong
   bytes. The integration test (`test_smoke_rom_runs_end_to_end`) plus the
   ASCII framebuffer dump are what made the mismatch visible.
3. **Skip-instruction tests need a canary that *provably* runs.** The first
   version asserted after one step, which cannot distinguish "skipped" from
   "hasn't run yet". Two steps (op + canary) make the semantics
   unambiguous.
4. **`unittest discover -s tests` imports modules top-level** — relative
   imports in test files fail. A top-level `_util` helper (which also puts
   the package on `sys.path`) is the portable fix.
5. **A self-erasing demo is still honest.** The smoke sprite eventually
   toggles every pixel off as it scrolls; showing a mid-run frame (5
   cycles) alongside the 300-cycle summary keeps the demo truthful without
   faking the ending.
