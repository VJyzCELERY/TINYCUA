"""Unit tests for Node base class."""

from __future__ import annotations

import pytest

from tinycua.config.node_config import NodeConfigBase, NodeRetryPolicy
from tinycua.config.types import LLMResult, ValidationError, ValidationResult
from tinycua.loops.node import Node
from tinycua.models.session import Session


class ConcreteNode(Node):
    """Concrete Node subclass for testing abstract base."""

    def __init__(
        self,
        node_id: str = "test",
        config: NodeConfigBase | None = None,
        instruction: str = "Test instruction",
    ) -> None:
        super().__init__(
            node_id=node_id,
            config=config or NodeConfigBase(),
            instruction=instruction,
        )

    def __call__(self, input: object) -> LLMResult:  # noqa: ARG002
        return LLMResult(content="test")


class TestNodeInit:
    """Tests for Node initialization."""

    def test_defaults(self) -> None:
        """Node initializes with defaults."""
        node = ConcreteNode()
        assert node.node_id == "test"
        assert node.session is None
        assert node.parent is None
        assert node.is_terminal is False
        assert node._instruction == "Test instruction"

    def test_custom_config(self) -> None:
        """Node accepts custom config."""
        config = NodeConfigBase(custom_instruction_append="Custom")
        node = ConcreteNode(config=config)
        assert node.config is config

    def test_is_terminal(self) -> None:
        """Node can be marked as terminal."""
        node = ConcreteNode()
        node.is_terminal = True
        assert node.is_terminal is True


class TestEnsureSession:
    """Tests for ensure_session method."""

    def test_creates_session_from_root(self) -> None:
        """ensure_session creates session from root session."""
        node = ConcreteNode()
        root = Session()
        session = node.ensure_session(root)
        assert session is root
        assert node.session is root

    def test_returns_existing_session(self) -> None:
        """ensure_session returns existing session if set."""
        node = ConcreteNode()
        existing = Session()
        node.session = existing
        result = node.ensure_session(Session())
        assert result is existing

    def test_adopts_parent_session(self) -> None:
        """ensure_session adopts parent node's session."""
        parent = ConcreteNode()
        child = ConcreteNode()
        child.parent = parent
        parent_session = Session()
        parent.session = parent_session

        result = child.ensure_session(Session())
        assert result is parent_session
        assert child.session is parent_session

    def test_no_session_no_parent_raises(self) -> None:
        """ensure_session raises ValueError with no session and no parent."""
        node = ConcreteNode()
        with pytest.raises(ValueError, match="No session available"):
            node.ensure_session(None)

    def test_parent_without_session_uses_root(self) -> None:
        """ensure_session uses root when parent has no session."""
        parent = ConcreteNode()
        child = ConcreteNode()
        child.parent = parent
        root = Session()

        result = child.ensure_session(root)
        assert result is root


class TestBuildInstruction:
    """Tests for build_instruction method."""

    def test_returns_static_instruction(self) -> None:
        """build_instruction returns hardcoded instruction."""
        node = ConcreteNode(instruction="Static instruction")
        assert node.build_instruction() == "Static instruction"

    def test_appends_custom(self) -> None:
        """build_instruction appends custom_instruction_append."""
        config = NodeConfigBase(custom_instruction_append="Custom part")
        node = ConcreteNode(instruction="Base", config=config)
        result = node.build_instruction()
        assert "Base" in result
        assert "Custom part" in result

    def test_override_instructions(self) -> None:
        """build_instruction uses override when provided."""
        node = ConcreteNode(instruction="Original")
        result = node.build_instruction(override_instructions="Override")
        assert result == "Override"

    def test_empty_instruction(self) -> None:
        """build_instruction returns empty string with no instruction."""
        node = ConcreteNode(instruction="")
        assert node.build_instruction() == ""


class TestValidateOutput:
    """Tests for validate_output method."""

    def test_valid_when_no_requirements(self) -> None:
        """validate_output returns valid when no requirements set."""
        node = ConcreteNode()
        response = LLMResult(content="test")
        result = node.validate_output(response)
        assert result.is_valid is True
        assert result.errors == []

    def test_fails_missing_tool_call(self) -> None:
        """validate_output fails when required tool call is missing."""
        config = NodeConfigBase(
            retry_policy=NodeRetryPolicy(required_tool_calls=["web_search"])
        )
        node = ConcreteNode(config=config)
        response = LLMResult(content="test", tool_calls=[])
        result = node.validate_output(response)
        assert result.is_valid is False
        assert any("web_search" in e for e in result.errors)

    def test_passes_with_required_tool_call(self) -> None:
        """validate_output passes when required tool call is present."""
        config = NodeConfigBase(
            retry_policy=NodeRetryPolicy(required_tool_calls=["web_search"])
        )
        node = ConcreteNode(config=config)
        response = LLMResult(
            content="test",
            tool_calls=[{"function": {"name": "web_search"}}],
        )
        result = node.validate_output(response)
        assert result.is_valid is True

    def test_custom_validation_fn(self) -> None:
        """validate_output uses custom validation function."""
        def custom_fn(response: LLMResult) -> ValidationResult:  # noqa: ARG001
            r = ValidationResult()
            r.is_valid = False
            r.errors = ["custom error"]
            return r

        config = NodeConfigBase(
            retry_policy=NodeRetryPolicy(validation_fn=custom_fn)
        )
        node = ConcreteNode(config=config)
        response = LLMResult(content="test")
        result = node.validate_output(response)
        assert result.is_valid is False
        assert "custom error" in result.errors


class TestBuildRetryContinuation:
    """Tests for build_retry_continuation method."""

    def test_basic_retry_message(self) -> None:
        """build_retry_continuation includes error and attempt."""
        node = ConcreteNode()
        error = ValidationError("Missing tool call")
        result = node.build_retry_continuation(error, 1)
        assert "Retry attempt 1" in result
        assert "Missing tool call" in result

    def test_custom_retry_append(self) -> None:
        """build_retry_continuation includes custom retry append."""
        config = NodeConfigBase(custom_retry_append="Custom retry text")
        node = ConcreteNode(config=config)
        error = ValidationError("Error")
        result = node.build_retry_continuation(error, 2)
        assert "Custom retry text" in result


class TestLifecycleHooks:
    """Tests for lifecycle hook methods."""

    def test_record_output_appends_to_session(self) -> None:
        """record_output appends response to session context."""
        node = ConcreteNode()
        node.session = Session()
        response = LLMResult(content="recorded content")
        node.record_output(response)
        assert len(node.session.session_context) == 1
        assert node.session.session_context[0]["content"] == "recorded content"

    def test_record_output_no_session(self) -> None:
        """record_output does not crash when no session."""
        node = ConcreteNode()
        response = LLMResult(content="content")
        # Should not raise
        node.record_output(response)

    def test_propagate_no_op(self) -> None:
        """propagate is a no-op by default."""
        node = ConcreteNode()
        # Should not raise
        node.propagate()

    def test_on_complete_no_op(self) -> None:
        """on_complete is a no-op by default."""
        node = ConcreteNode()
        response = LLMResult(content="done")
        # Should not raise
        node.on_complete(queue=object(), response=response)
