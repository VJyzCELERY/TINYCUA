"""TINYCUA custom loop types (M2).

Provides four canonical custom loop types — Classification, Exploration,
Linear Agent, and Hybrid Review — as ``BaseLoop`` subclasses. A ``LoopType``
enum and ``create_loop()`` factory provide discovery and instantiation.

All public types are importable from this single entry point:

    from tinycua.loops import (
        LoopType, create_loop,
        ClassificationLoop, ExplorationLoop,
        LinearAgentLoop, HybridReviewLoop,
        ClassificationConfig, ExplorationConfig,
        LinearAgentConfig, HybridReviewConfig,
        CheckResult,
    )
"""

from __future__ import annotations

from tinycua.loops.types import LoopType
from tinycua.loops.factory import create_loop
from tinycua.loops.classification import ClassificationLoop, ClassificationConfig
from tinycua.loops.exploration import ExplorationLoop, ExplorationConfig
from tinycua.loops.linear_agent import LinearAgentLoop, LinearAgentConfig
from tinycua.loops.hybrid_review import HybridReviewLoop, HybridReviewConfig, CheckResult

__all__ = [
    "LoopType",
    "create_loop",
    "ClassificationLoop",
    "ClassificationConfig",
    "ExplorationLoop",
    "ExplorationConfig",
    "LinearAgentLoop",
    "LinearAgentConfig",
    "HybridReviewLoop",
    "HybridReviewConfig",
    "CheckResult",
]
