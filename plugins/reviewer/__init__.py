"""M4 — the reviewer plugin (SPEC §11).

The semantic layer on hard evidence: context in, soft evidence +
verdict out; the kernel decides done.

    from plugins.reviewer import ReferenceReviewer, default_judge
"""
from .reviewer import REVIEW_SOURCE, ReferenceReviewer, default_judge

__all__ = ["REVIEW_SOURCE", "ReferenceReviewer", "default_judge"]
