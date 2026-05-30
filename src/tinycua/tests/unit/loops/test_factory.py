"""Unit tests for create_loop factory."""

from __future__ import annotations

import pytest

from tinycua.loops import create_loop
from tinycua.loops.types import LoopType


class TestCreateLoop:
    """Test create_loop factory function."""

    def test_create_classification_loop(self) -> None:
        """create_loop(CLASSIFICATION) should return a ClassificationLoop."""
        from tinycua.loops.classification import ClassificationLoop

        loop = create_loop(LoopType.CLASSIFICATION)
        assert isinstance(loop, ClassificationLoop)

    def test_create_exploration_loop(self) -> None:
        """create_loop(EXPLORATION) should return an ExplorationLoop."""
        from tinycua.loops.exploration import ExplorationLoop

        loop = create_loop(LoopType.EXPLORATION)
        assert isinstance(loop, ExplorationLoop)

    def test_create_linear_agent_loop(self) -> None:
        """create_loop(LINEAR_AGENT) should return a LinearAgentLoop."""
        from tinycua.loops.linear_agent import LinearAgentLoop

        loop = create_loop(LoopType.LINEAR_AGENT)
        assert isinstance(loop, LinearAgentLoop)

    def test_create_hybrid_review_loop(self) -> None:
        """create_loop(HYBRID_REVIEW) should return a HybridReviewLoop."""
        from tinycua.loops.hybrid_review import HybridReviewLoop

        loop = create_loop(LoopType.HYBRID_REVIEW)
        assert isinstance(loop, HybridReviewLoop)

    def test_create_with_kwargs(self) -> None:
        """create_loop should forward kwargs to the loop constructor."""
        loop = create_loop(LoopType.CLASSIFICATION, rubric_dimensions=["custom"])
        assert loop.rubric_dimensions == ["custom"]

    def test_create_unknown_type(self) -> None:
        """create_loop with unknown type should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown loop type"):
            create_loop("invalid_type")  # type: ignore[arg-type]

    def test_create_all_types_are_baseloop_subclasses(self) -> None:
        """All created loops should be BaseLoop subclasses."""
        from tinycua_sdk.agent.loop import BaseLoop

        for loop_type in LoopType:
            loop = create_loop(loop_type)
            assert isinstance(loop, BaseLoop), f"{loop_type} is not a BaseLoop subclass"

    def test_max_iterations_forwarded(self) -> None:
        """max_iterations parameter should be forwarded to all loops."""
        loop = create_loop(LoopType.CLASSIFICATION, max_iterations=10)
        assert loop.max_iterations == 10

        loop = create_loop(LoopType.EXPLORATION, max_iterations=8)
        assert loop.max_iterations == 8

        loop = create_loop(LoopType.LINEAR_AGENT, max_iterations=15)
        assert loop.max_iterations == 15

        loop = create_loop(LoopType.HYBRID_REVIEW, max_iterations=3)
        assert loop.max_iterations == 3
