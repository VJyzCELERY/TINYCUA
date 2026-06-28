"""Tests for DigestedInformation model."""

from tinycua.models.digested_information import DigestedInformation


class TestDigestedInformation:
    """Tests for DigestedInformation dataclass."""

    def test_dataclass_field_defaults(self) -> None:
        """Test default field values."""
        digest = DigestedInformation()
        assert digest.context_summary == ""
        assert digest.key_points == []
        assert digest.advisory_instructions == []
        assert digest.constraints == []
        assert digest.known_gaps == []
        assert digest.original_query == ""

    def test_construction_with_fields(self) -> None:
        """Test construction with specific field values."""
        digest = DigestedInformation(
            context_summary="Test summary",
            key_points=["point1", "point2"],
            advisory_instructions=["advice1"],
            constraints=["constraint1"],
            known_gaps=["gap1"],
            original_query="test query",
        )
        assert digest.context_summary == "Test summary"
        assert digest.key_points == ["point1", "point2"]
        assert digest.advisory_instructions == ["advice1"]
        assert digest.constraints == ["constraint1"]
        assert digest.known_gaps == ["gap1"]
        assert digest.original_query == "test query"

    def test_fallback_preserves_original_query(self) -> None:
        """Test fallback() creates correct instance with original query."""
        original_query = "Create a plan for the migration"
        digest = DigestedInformation.fallback(original_query)

        assert original_query in digest.context_summary
        assert digest.original_query == original_query
        assert digest.key_points == []
        assert digest.advisory_instructions == []

    def test_has_useful_context_true_when_key_points(self) -> None:
        """Test has_useful_context returns True when key_points exist."""
        digest = DigestedInformation(
            key_points=["point1", "point2"],
            original_query="test",
        )
        assert digest.has_useful_context is True

    def test_has_useful_context_true_when_advisory_instructions(self) -> None:
        """Test has_useful_context returns True when advisory_instructions exist."""
        digest = DigestedInformation(
            advisory_instructions=["advice1"],
            original_query="test",
        )
        assert digest.has_useful_context is True

    def test_has_useful_context_false_for_fallback(self) -> None:
        """Test has_useful_context returns False for fallback-only instance."""
        fallback_digest = DigestedInformation.fallback("test")
        assert fallback_digest.has_useful_context is False

    def test_has_useful_context_false_for_empty(self) -> None:
        """Test has_useful_context returns False for default instance."""
        digest = DigestedInformation()
        assert digest.has_useful_context is False
