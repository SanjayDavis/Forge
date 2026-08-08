# Forge Proof Standard

**Version:** 0.1
**Status:** Draft
**Location:** `proofs/PROOF_SPEC.md`

Versioning: this standard is Draft until the first proof built from scratch against it
conforms; that proof validates the standard by use, and the version then bumps to
1.0 / Stable. `conforms_to` in a proof's `metrics.json` pins the version the proof was
built against.

---

## 1. Purpose

A **Forge Proof** is a reproducible, self-contained example project that demonstrates one
or more claims about Forge, packaged with *uniform* evidence so proofs can be compared
side by side.

This standard defines **what evidence every proof must produce**, and deliberately says
nothing about **how** it is generated. Any tool, script, or manual step that yields a
conforming artifact is acceptable. The standard is implementation-agnostic by design.

Consistency is the point. Five examples that follow one standard are stronger evidence
than five examples that each tell their own story. The goal is a **corpus of reproducible
engineering evidence**: anyone can line up two proofs and compare scale, complexity, and
outcomes in minutes. This is not a performance benchmark — nothing here measures speed or
throughput. The corpus compares reproducibility, evidence quality, architecture, and
project evolution.

## 2. Canonical claims

Every criticism Forge faces gets a claim ID. A claim is *demonstrated* only when the
proof's artifacts give a skeptical reader something to check.

| Claim | Criticism it answers | Typical proof shape |
|-------|----------------------|---------------------|
| C1 | "It only works on toy examples." | Non-trivial domain, real constraints |
| C2 | "It only works for web apps." | Non-web domain (e.g. emulator, parser, CLI) |
| C3 | "It's tied to Python." | Non-Python language (C++, Rust, ...) |
| C4 | "It can't handle long projects." | 100+ tasks, 1000+ events |
| C5 | "It only works with one agent." | Multi-agent run (roles, handoffs, review) |
| C6 | "It's just a fancy todo list." | Real development history: failures, retries, replays |
| C7 | "It can't handle structured complexity." | Many independent subsystems, deep/wide DAG |

The README of every proof **must** list its Claim IDs and, for each, one sentence on how
the proof demonstrates it. Claims are not self-assigned honors — the listed artifacts
must actually support them.

## 3. Required artifact bundle

Every proof lives at `examples/<name>/` and must contain **exactly** these artifacts:

```
examples/<name>/
    README.md          the proof's front door
    events.log         raw, unmodified Forge history
    graph.json         machine-readable dependency graph (final state)
    graph.png          rendered dependency graph (final state)
    replay.md          human-readable timeline of the run
    metrics.json       comparable numbers (see §5)
    screenshots/       at least 2 captures
    demo.mp4           <= 2 minutes of the thing actually running
```

No other evidence files belong at the top level of a proof directory. Derived artifacts
(graph.json, graph.png, replay.md, metrics.json) must be regenerable from `events.log`
alone — the log is the single source of truth.

## 4. Per-artifact requirements

### 4.1 README.md — required sections, in order

1. **What was built** — one paragraph, no fluff.
2. **Why this proof exists** — the criticism/claim it answers; list Claim IDs (§2).
3. **Final architecture** — subsystem breakdown with dependency arrows. For
   subsystem-heavy proofs (CHIP-8-style), enumerate the subsystems explicitly
   (e.g. CPU, memory, timers, display, input, ROM loading, tests) and how they connect.
4. **Commands** — exact commands to build, run, and test. Must work from a clean
   checkout of the repo.
5. **Reproduce** — how the proof was produced: Forge version, planner/executor/
   verifier used, and the seed prompt. Enough that a stranger could rerun it.
6. **Artifact index** — one line per artifact, pointing at it.
7. **Behavior notes** — anything non-obvious discovered during the run (e.g. an
   idempotency decision, a spec ambiguity, a bug found by verification).
8. **Lessons learned** — insights, not bugs. What the run exposed about the project,
   about Forge, or about the domain. Sometimes the interesting thing isn't the project
   itself; it's what the run revealed.

### 4.2 events.log

- The **exact file Forge wrote** during the run: line-delimited JSON, one event per
  line, contiguous `seq` starting at 1.
- Must **not** be edited, filtered, reformatted, or re-ordered after the run. It is raw
  evidence, not a summary. A proof whose log was post-processed fails conformance.
- Event schema is canonical: see `docs/EVENTS.md`. Proofs must not invent new ops;
  a genuinely new op is a kernel/SDK change, which is out of scope for proofs (see §7).

### 4.3 graph.json

Minimal stable schema, final state only:

```json
{
  "proof": "<name>",
  "forge_version": "<version>",
  "planner": "<optional model id>",
  "executor": "<optional model id>",
  "verifier": "<optional model id>",
  "generated_at": "<ISO timestamp>",
  "tasks": [
    {
      "id": "<task id>",
      "title": "<title>",
      "status": "done | in_progress | needs_revision | todo",
      "priority": "high | medium | low",
      "subsystem": "<optional grouping label>"
    }
  ],
  "dependencies": [
    { "task": "<dependent>", "depends_on": "<prerequisite>" }
  ]
}
```

- Reflects the **final** state of `events.log`.
- Every `task` id must appear in `events.log`; every edge must correspond to a
  `dependency_added` event.
- `subsystem` is optional but strongly encouraged for C7 proofs (it powers the
  subsystem-grouped rendering in graph.png).
- `planner` / `executor` / `verifier` are optional model identifiers. Not needed today,
  but five years out the corpus should answer "Claude vs Gemini vs Codex" from the
  proof files alone, without digging through replay narratives.

### 4.4 graph.png

- Rendered from graph.json (or equivalently by replaying events.log).
- Direction: left-to-right or top-to-bottom, consistent within the proof.
- Status-colored nodes: done = green, in_progress = amber, needs_revision = red,
  todo = grey (or equivalent legend). The legend must be visible in the image.
- Readable at 1920px width; subsystem groupings labeled where `subsystem` is used.

### 4.5 replay.md

A narrative timeline a reader can cross-check against `events.log` — every milestone
cites `seq` numbers so the narrative is verifiable, not vibes.

Required skeleton:

- **Goal** — 1–2 lines.
- **Outcome** — the same numbers as `metrics.json` (tasks, events, failures, retries).
- **Timeline** — the run in phases: Proposal → Planning → Execution → Verification →
  Completion. Under Execution: notable failures, retries, reopened tasks, and how each
  was resolved.
- **Turning points** — 1–5 events that changed the run (rejected tasks, discovered
  bugs, scope changes).

Tone is factual, not promotional. If verification failed nine times, say so — the
failures are the evidence. A replay with zero failures reads as *less* credible, not
more.

### 4.6 metrics.json

See §5 for exact field semantics. Required fields are mandatory; unknown values must be
`"not recorded"`, never guessed.

```json
{
  "proof": "<name>",
  "status": "completed",
  "language": "python",
  "tasks": 42,
  "events": 281,
  "verification_passes": 41,
  "verification_failures": 3,
  "retries": 2,
  "duration_minutes": 74,
  "llm": "Claude Code",
  "forge_version": "<version>",
  "conforms_to": "proof-spec-0.1",
  "claims": ["C1", "C6", "C7"]
}
```

### 4.7 screenshots/

- At least 2 PNGs: (a) the artifact running, (b) the test suite passing (or equivalent
  hard evidence). More allowed.
- Naming: `01-run.png`, `02-tests.png`, ... ascending by importance.

### 4.8 demo.mp4

- ≤ 120 seconds, ≤ 720p.
- Audio optional; if present, no narration required.
- Must show real runtime behavior end-to-end: launch → interaction → verification/test
  pass. Screen recording or terminal capture (asciinema-style) both fine.
- A GIF is acceptable where motion is simple; the spec still applies.

## 5. Metrics glossary (normative semantics)

Comparability requires identical measurement. These definitions are binding — a metric
measured differently is a different metric.

| Field | Definition |
|-------|------------|
| `tasks` | Number of distinct `task_created` events in `events.log` (equals final node count in graph.json). A task later expanded still counts once. |
| `events` | Number of lines in `events.log` (equals max `seq`). |
| `verification_passes` | Count of `verification_passed` events. |
| `verification_failures` | Count of `verification_failed` events. A failure that leads to a retry is **one** failure, however many evidence rounds follow. |
| `retries` | Count of `task_retried` events. |
| `duration_minutes` | Wall-clock minutes from the first event's `ts` to the last event's `ts`, inclusive, rounded half-up to the nearest minute. Not agent CPU time, not LLM time. |
| `llm` | Model identifier used for planning/execution (e.g. `"Claude Code"`, `"gemini-2.0-flash"`). Shorthand for the primary planning model; for multi-role runs, prefer the optional `planner` / `executor` / `verifier` fields below. Unknown → `"not recorded"`. |
| `planner` / `executor` / `verifier` | Optional. Model identifiers per role. Enables cross-proof model comparison (Claude vs Gemini vs Codex) without replay digging. |
| `status` | `"completed"` (all tasks done), `"partial"` (some tasks not done — README must explain why), or `"failed"` (aborted run — normally not shipped). |
| `language` | Primary implementation language of the proof. |
| `forge_version` | Forge version the proof was produced with. |
| `conforms_to` | Standard version, e.g. `"proof-spec-0.1"`. |
| `claims` | Array of Claim IDs from §2. |

**Derived ratios (not stored, computed on demand):** the pass/fail pair above exists so
verification health can be expressed as a rate, not just a count:

```
verification attempts  = verification_failures + verification_passes
failure rate           = verification_failures / verification_attempts
```

A failure rate of 10% over 10 attempts is a much more meaningful engineering number
than "1 failure". Any consumer of the corpus may compute these; proofs do not store them.

**Derivation rule:** every number in metrics.json must be reproducible by replaying
`events.log` (e.g. `forge replay` or a ten-line script). A number that does not match
the log fails conformance. This rule is what keeps the corpus honest — consistent
shape with inconsistent measurement would be fake consistency. The `claims` array
derives from `claims_claimed` events in the log; proofs whose runtime predates that
op fall back to the `claims` field authored in `proposal.json` (a committed input of
the proof — never a post-hoc edit of the log). `language` derives from
implementation-file references inside the log (see `tools/proof-derive.py`).

## 6. Conformance

A proof **conforms** when all of the following hold:

1. Every artifact in §3 exists and satisfies its §4 requirements.
2. `events.log` is unmodified raw Forge output.
3. Every `metrics.json` value is derivable from `events.log` (§5).
4. The README lists Claim IDs, and each claimed ID has at least one artifact that
   supports it.
5. The project builds, runs, and tests with the README's commands from a clean
   checkout.
6. A one-line entry exists in the Proof Index (`proofs/INDEX.md`).

A proof missing any requirement is **non-conforming** until fixed. Non-conforming proofs
may remain in the repo (as works-in-progress) but are excluded from the comparison
table in the Index until they conform.

### Conformance checklist (per proof)

```
[ ] README.md — all 8 sections (§4.1)
[ ] events.log — raw, unmodified, contiguous seq
[ ] graph.json — valid schema, matches events.log
[ ] graph.png — status-colored, legend, readable at 1920px
[ ] replay.md — goal/outcome/timeline/turning points, seq citations
[ ] metrics.json — derivable from events.log (§5)
[ ] screenshots/ — >= 2 (running + tests passing)
[ ] demo.mp4 — <= 120s, real runtime behavior
[ ] README commands work from clean checkout
[ ] INDEX.md entry added
```

## 7. Rules of engagement

- This standard does **not** change the kernel, SDK, or planner. If producing a proof
  reveals a genuine bug, report it; fix it as a bugfix, not as a proof side-quest.
- Proofs are **demonstrations, not tutorials**. READMEs explain why the proof exists
  and what happened; how-to material belongs in `docs/`.
- Proofs must be reproducible from the repo. Vendored third-party code is allowed only
  when required and is disclosed in the README.
- A proof whose demo or screenshots show a *different* project than the one in
  `events.log` fails conformance. The artifacts must describe the same run.

---

*Documenting evidence beats documenting software. Evidence is strongest when it is
consistent.*
