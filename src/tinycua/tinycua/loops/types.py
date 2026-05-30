"""LoopType enum for TINYCUA custom loop types."""

from __future__ import annotations

from enum import Enum

__all__ = ["LoopType"]


class LoopType(Enum):
    """Canonical TINYCUA custom loop types.

    Each value identifies a ``BaseLoop`` subclass that implements a
    specific agent execution pattern.

    Attributes:
        CLASSIFICATION: Fast, high-level context scan + score-based mode
            classification (Query Analyst agent).
        EXPLORATION: Precision-oriented exploration using Enhanced Context
            Retrieval (Information Digester agent).
        LINEAR_AGENT: ReAct loop with single input→output contract, no
            internal routing branches (Task Analyzer, Task Executor, Task
            Assessor, Primary Agent).
        HYBRID_REVIEW: Hybrid deterministic + LLM review loop (Result
            Reviewer agent).
    """

    CLASSIFICATION = "classification"
    EXPLORATION = "exploration"
    LINEAR_AGENT = "linear_agent"
    HYBRID_REVIEW = "hybrid_review"
