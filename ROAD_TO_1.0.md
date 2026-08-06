# ROAD_TO_1.0.md

> Every gate below is **objective and checkable** — nobody has to ask "when is Forge 1.0?"
> they read this file. Each checkbox is a *measured* fact; a checked box with no backing
> evidence is a bug in this file. Forge's version numbers track **confidence, not features**:
> the ladder below is the proof, still to be earned.

## Version ladder (confidence, not features)

| Version    | Stage            | Question it answers                | Trigger |
|-----------|------------------|------------------------------------|---------|
| `0.1.0a1` | Alpha            | Does the architecture work?        | Feature-complete alpha on PyPI |
| `0.1.0a2` | Proof #2 (CHIP-8) | Non-trivial systems project?      | CHIP-8 proof conforming |
| `0.1.0a3` | Generalization    | Does it work beyond Python?       | C++ + Rust proofs conforming |
| `0.1.0a4` | Generalization    | Does execution scale?             | Multi-agent / 100+ task proof conforming |
| `0.1.0b1` | External validation | Does it work for other people?  | 5 independent users AND 3 completed projects |
| `0.1.0rc1`| API freeze         | Can we promise stability?        | Public surface frozen + ≥1 external PR |
| `1.0.0`   | Stable             | Has reality agreed with the design? | 90 days, no API change, all gates green |

---

## Evidence — the proof corpus

Source of truth: [`proofs/INDEX.md`](proofs/INDEX.md). A box is checked only when
`proof-check` marks that proof **conforming**.

- [x] `flask-todo` — Python web app (Proof #1, claims C6, C7)
- [x] `chip8` — CHIP-8 emulator, headless CLI (Proof #2, claims C1, C2, C7)
- [ ] `expr-parser` — C++ expression parser (Proof #3, claims C1, C3)
- [ ] `rust-cli` — Rust CLI (Proof #4, claims C1, C3)
- [ ] `multi-agent` — 100+ task multi-agent run (Proof #5, claims C4, C5)

## Validation — people, not clones

*Independent* = built something usable without 1:1 author coaching (no author-written
code, no DM hand-holding). *Completed* = a finished, committed artifact the user derived
from Forge's planner/executor, not a fork + clone.

- [ ] 5 independent external users
- [ ] 3 completed projects (independent users finishing real work)
- [ ] 1 external PR merged

## Stability — the 1.0 referee

- [ ] No public-SDK/API change for 90 days (surface-guard CI is the referee)
- [ ] Compliance suite green (`python -m unittest tests.compliance`)
- [ ] Proof suite green (`proof-check` passes on every conforming entry in the corpus)

## Release

- [ ] `1.0.0` tagged and published as stable

---

*Maintained alongside `proofs/INDEX.md`. A mismatch between this file and the index*
*fails the compliance suite (see `tests/compliance/test_compliance.py` →
`test_road_to_1_0_checklist_matches_index`).*