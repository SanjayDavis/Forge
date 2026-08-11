"""forge-proof — the reference proof evidence pipeline.

`forge proof check/derive/replay/bundle` over a Proof-Standard bundle
(proofs/PROOF_SPEC.md): derive machine-readable artifacts from
events.log alone (§5), render replay.md and graph.png, scaffold README,
and validate the full §6 conformance checklist. Stdlib-only; the kernel
stays out of scope — this package is a client of the artifacts, never
of the event API.
"""
__version__ = "0.1.0a4"

__all__ = ["__version__", "check", "derive", "replay", "bundle"]