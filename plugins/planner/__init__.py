"""M2B — the planner plugin. The first untrusted client of Forge.

Implements the Planner Protocol (SPEC §9): goal in, proposal out.
A planner never edits the graph; it emits a proposal and the kernel
decides.

    from plugins.planner import ReferencePlanner, validate_proposal
"""
from .planner import ALLOWED_OPS, ProposalError, ReferencePlanner, validate_proposal

__all__ = ["ALLOWED_OPS", "ProposalError", "ReferencePlanner", "validate_proposal"]
