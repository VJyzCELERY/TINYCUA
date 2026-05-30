"""Factory function for creating loop instances by type."""

from __future__ import annotations

from typing import Any

from tinycua_sdk.agent.loop import BaseLoop

from tinycua.loops.classification import ClassificationLoop
from tinycua.loops.exploration import ExplorationLoop
from tinycua.loops.hybrid_review import HybridReviewLoop
from tinycua.loops.linear_agent import LinearAgentLoop
from tinycua.loops.types import LoopType

__all__ = ["create_loop"]

_LOOP_MAP: dict[LoopType, type[BaseLoop]] = {
    LoopType.CLASSIFICATION: ClassificationLoop,
    LoopType.EXPLORATION: ExplorationLoop,
    LoopType.LINEAR_AGENT: LinearAgentLoop,
    LoopType.HYBRID_REVIEW: HybridReviewLoop,
}


def create_loop(
    loop_type: LoopType,
    *,
    max_iterations: int = 5,
    **kwargs: Any,
) -> BaseLoop:
    """Create the appropriate loop instance for the given loop type.

    Args:
        loop_type: The type of loop to create.
        max_iterations: Maximum iterations for the loop (default 5).
        **kwargs: Additional keyword arguments forwarded to the loop
            constructor (e.g., ``rubric_dimensions``, ``system_prompt_template``).

    Returns:
        An instance of the corresponding ``BaseLoop`` subclass.

    Raises:
        ValueError: If ``loop_type`` is not a recognised ``LoopType`` value.
    """
    loop_cls = _LOOP_MAP.get(loop_type)  # type: ignore[arg-type]
    if loop_cls is None:
        msg = f"Unknown loop type: {loop_type!r}"
        raise ValueError(msg)
    return loop_cls(max_iterations=max_iterations, **kwargs)
