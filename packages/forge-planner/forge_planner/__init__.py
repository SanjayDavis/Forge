"""forge_planner — the reference planner for Forge.

Implements the Planner Protocol (SPEC §9): goal in, proposal out. This
package is the architectural proof behind the SDK boundary: it is a
separate, installable distribution that consumes ONLY the public
``forge.*`` surface (ForgeClient, validate_proposal, slugify,
PLANNER_OPS) — no kernel internals.
"""

from .planner import ALLOWED_OPS, ProposalError, ReferencePlanner, validate_proposal

__all__ = ["ReferencePlanner", "ProposalError", "validate_proposal",
           "ALLOWED_OPS"]
