"""Unit tests for LoopType enum."""

from __future__ import annotations

from enum import Enum

import pytest

from tinycua.loops.types import LoopType


class TestLoopTypeEnum:
    """Test LoopType enum values, string mapping, and membership."""

    def test_enum_values(self) -> None:
        """LoopType should have exactly four values."""
        values = list(LoopType)
        assert len(values) == 4

    def test_enum_members(self) -> None:
        """Each LoopType member should have the correct name and value."""
        assert LoopType.CLASSIFICATION.value == "classification"
        assert LoopType.EXPLORATION.value == "exploration"
        assert LoopType.LINEAR_AGENT.value == "linear_agent"
        assert LoopType.HYBRID_REVIEW.value == "hybrid_review"

    def test_enum_is_enum(self) -> None:
        """LoopType should be a proper Enum subclass."""
        assert issubclass(LoopType, Enum)

    def test_enum_string_representation(self) -> None:
        """String representation should match enum member name."""
        assert str(LoopType.CLASSIFICATION) == "LoopType.CLASSIFICATION"
        assert repr(LoopType.CLASSIFICATION) == "<LoopType.CLASSIFICATION: 'classification'>"

    def test_enum_iteration(self) -> None:
        """Iterating over LoopType should yield all members."""
        names = [m.name for m in LoopType]
        assert "CLASSIFICATION" in names
        assert "EXPLORATION" in names
        assert "LINEAR_AGENT" in names
        assert "HYBRID_REVIEW" in names

    def test_enum_from_value(self) -> None:
        """LoopType should be constructable from string values."""
        assert LoopType("classification") == LoopType.CLASSIFICATION
        assert LoopType("exploration") == LoopType.EXPLORATION
        assert LoopType("linear_agent") == LoopType.LINEAR_AGENT
        assert LoopType("hybrid_review") == LoopType.HYBRID_REVIEW

    def test_enum_invalid_value(self) -> None:
        """Accessing an invalid value should raise ValueError."""
        with pytest.raises(ValueError, match="'invalid_type'"):
            LoopType("invalid_type")
