"""Forge — a deterministic project kernel for autonomous software
development.

The kernel owns project state as an event-sourced task graph. Humans,
planners, executors, verifiers, and MCP servers are interchangeable
clients of the same official API (forge.kernel.Kernel). There is no AI
in the kernel; it is pure, deterministic, and zero-dependency.

    LLM ──┐
          ├──► Kernel ──► events.log (source of truth)
    Human ─┘
"""

__version__ = "0.1.0a1"
# 0.1.0-alpha: the KERNEL is stable and frozen at v1 (docs/SPEC.md,
# Appendix A: Versioning & Freeze Policy); the ecosystem around it
# (executor, reviewer, MCP, UIs) is under active development. The
# kernel contract never tracks this number.

from .model import (  # noqa: F401
    EVIDENCE_HARD, EVIDENCE_SOFT, SCHEMA_VERSION,
    PRIORITIES, PRIORITY_WEIGHT, OP_SHAPES,
    STATUS_TODO, STATUS_IN_PROGRESS, STATUS_NEEDS_REVISION, STATUS_DONE,
    Evidence, TaskNode, Graph, GraphError,
)
from .store import EVENT_FILE, Store, load_project  # noqa: F401
from .scheduler import blockers, is_container, next_task, progress, ready_tasks  # noqa: F401
from .context import build_context, to_json, to_markdown  # noqa: F401
from .query import QueryError, run_query  # noqa: F401
from .kernel import Kernel  # noqa: F401
from .sdk import (  # noqa: F401
    ForgeClient, ProposalError, context_package, slugify,
    validate_proposal,
)
