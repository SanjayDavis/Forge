"""M3 — the executor plugin (SPEC §10).

Task package in, artifacts + hard evidence out; the kernel decides done.

    from plugins.executor import ReferenceExecutor, default_worker, parse_context
"""
from .executor import (ExecutorError, ReferenceExecutor, default_worker,
                       parse_context, render_artifact)

__all__ = ["ExecutorError", "ReferenceExecutor", "default_worker",
           "parse_context", "render_artifact"]
