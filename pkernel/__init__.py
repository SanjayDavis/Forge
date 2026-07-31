"""Project Kernel - an AI-agnostic, event-sourced task graph engine.

The kernel is pure, deterministic Python with zero dependencies and no AI.
LLMs (Claude, Codex, Gemini, Hermes) are just clients that emit the same
events a human emits through the CLI.
"""

from .model import (
    EVIDENCE_HARD,
    EVIDENCE_SOFT,
    STATUS_DONE,
    STATUS_IN_PROGRESS,
    STATUS_NEEDS_REVISION,
    STATUS_TODO,
    Evidence,
    Graph,
    GraphError,
    TaskNode,
)
from .store import EVENT_FILE, Store

__all__ = [
    "EVIDENCE_HARD",
    "EVIDENCE_SOFT",
    "STATUS_DONE",
    "STATUS_IN_PROGRESS",
    "STATUS_NEEDS_REVISION",
    "STATUS_TODO",
    "Evidence",
    "Graph",
    "GraphError",
    "TaskNode",
    "Store",
    "EVENT_FILE",
]

__version__ = "0.1.0"
