# Forge Specification Compliance Suite

Every implementation claiming to be **Forge v1.0** — Python, Rust, Go,
Java, anything — must pass this suite against its own kernel.

This is a *specification* test suite, not a feature test suite. Each
test maps one-to-one to a clause of `docs/SPEC.md`:

- `test_compliance.py` — the seven invariants (I1–I7, SPEC §1.9) plus
  the adversarial requirements: malformed-proposal matrix, valid-stream
  fuzz, garbage-event fuzz (GraphError or fold — never a crash),
  torn-tail crash recovery, mid-file corruption, atomic proposal
  commits, replay identity across hash seeds, scheduler determinism
  under randomized creation.

If a test fails here, the implementation no longer complies with the
specification. It is not a bug report; it is a conformance failure.

Run as part of the canonical suite:

    python -m unittest discover -s tests
