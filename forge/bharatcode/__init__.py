"""Forge BharatCode planner — an LLM-backed planner using BharatCode's
model API (OpenAI-compatible Chat Completions).

This package is a SEPARATE product from ``forge-foundation``: the kernel
stays zero-dependency, stdlib-only. Only this planner package touches the
network, and only when you ask it to plan.

    from forge.bharatcode import BharatCodePlanner
    p = BharatCodePlanner()          # reads BHARATCODE_API_KEY from env
    proposal = p.plan("Build a CHIP-8 emulator")
    p.commit(proposal)               # needs a ForgeClient
"""

from .planner import BharatCodePlanner, BharatCodeError  # noqa: F401

__version__ = "0.1.0b1"
__all__ = ["BharatCodePlanner", "BharatCodeError"]
