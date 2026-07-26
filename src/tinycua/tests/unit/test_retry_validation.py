"""Unit tests for retry, validation, and exhaustion handling."""

import pytest

from tinycua.config.node_config import NodeConfigBase, NodeRetryPolicy
from tinycua.config.types import LLMResult, ValidationError, ValidationResult
from tinycua.loops.node import NodeExecutionError, ProcessNode
from tinycua.models.session import Session


class MockLLM:
    """Mock LLM returning a sequence of LLMResult responses."""

    def __init__(self, responses):
        self._responses = [
            LLMResult(content=r["content"]) if isinstance(r, dict) else r
            for r in responses
        ]
        self.call_count = 0

    def __call__(self, messages, **kwargs):
        idx = min(self.call_count, len(self._responses) - 1)
        self.call_count += 1
        return self._responses[idx]


def _make_node(config_overrides=None):
    """Create a ProcessNode with mock LLM for testing."""
    defaults = {
        "llm_client": MockLLM([LLMResult(content="ok")]),
        "retry_policy": NodeRetryPolicy(max_attempts=1),
    }
    if config_overrides:
        defaults.update(config_overrides)
    config = NodeConfigBase(**defaults)
    node = ProcessNode(node_id="test", config=config, instruction="Do work")
    node.session = Session()
    return node


class TestValidateOutput:
    """Tests for Node.validate_output()."""

    def test_valid_output_no_requirements(self):
        """No requirements means always valid."""
        node = _make_node()
        result = node.validate_output(LLMResult(content="hello"))
        assert result.is_valid is True
        assert result.errors == []

    def test_valid_tool_calls_present(self):
        """Required tool call present passes validation."""
        node = _make_node(
            config_overrides={
                "retry_policy": NodeRetryPolicy(
                    max_attempts=1,
                    required_tool_calls=["my_tool"],
                ),
            }
        )
        response = LLMResult(
            content="done",
            tool_calls=[{"function": {"name": "my_tool"}}],
        )
        result = node.validate_output(response)
        assert result.is_valid is True

    def test_invalid_tool_call_missing(self):
        """Required tool call missing fails validation."""
        node = _make_node(
            config_overrides={
                "retry_policy": NodeRetryPolicy(
                    max_attempts=1,
                    required_tool_calls=["required_tool"],
                ),
            }
        )
        response = LLMResult(content="no tool calls", tool_calls=[])
        result = node.validate_output(response)
        assert result.is_valid is False
        assert any("required_tool" in e for e in result.errors)

    def test_custom_validation_fn_valid(self):
        """Custom validation_fn returning valid result."""

        def my_validator(result):
            return ValidationResult(is_valid=True, errors=[])

        node = _make_node(
            config_overrides={
                "retry_policy": NodeRetryPolicy(
                    max_attempts=1,
                    validation_fn=my_validator,
                ),
            }
        )
        result = node.validate_output(LLMResult(content="ok"))
        assert result.is_valid is True

    def test_custom_validation_fn_invalid(self):
        """Custom validation_fn returning invalid result."""

        def my_validator(result):
            return ValidationResult(is_valid=False, errors=["custom error"])

        node = _make_node(
            config_overrides={
                "retry_policy": NodeRetryPolicy(
                    max_attempts=1,
                    validation_fn=my_validator,
                ),
            }
        )
        result = node.validate_output(LLMResult(content="bad"))
        assert result.is_valid is False
        assert "custom error" in result.errors

    def test_custom_validation_fn_exception(self):
        """Custom validation_fn raising exception fails validation."""

        def bad_validator(result):
            raise ValueError("boom")

        node = _make_node(
            config_overrides={
                "retry_policy": NodeRetryPolicy(
                    max_attempts=1,
                    validation_fn=bad_validator,
                ),
            }
        )
        result = node.validate_output(LLMResult(content="ok"))
        assert result.is_valid is False
        assert any("boom" in e for e in result.errors)

    def test_custom_validation_fn_returns_none(self):
        """Custom validation_fn returning None is treated as pass."""

        def none_validator(result):
            return None

        node = _make_node(
            config_overrides={
                "retry_policy": NodeRetryPolicy(
                    max_attempts=1,
                    validation_fn=none_validator,
                ),
            }
        )
        result = node.validate_output(LLMResult(content="ok"))
        assert result.is_valid is True


class TestBuildRetryText:
    """Tests for Node._build_retry_text()."""

    def test_default_builder(self):
        """Default builder produces standard message."""
        node = _make_node()
        error = ValidationError("test error")
        text = node._build_retry_text(error, 1)
        assert "Retry attempt 1" in text
        assert "test error" in text

    def test_custom_builder(self):
        """Custom builder produces custom message."""

        def custom_builder(error, attempt):
            return f"Custom retry {attempt}: {error}"

        node = _make_node(
            config_overrides={
                "retry_policy": NodeRetryPolicy(
                    max_attempts=2,
                    retry_continuation_builder=custom_builder,
                ),
            }
        )
        error = ValidationError("err")
        text = node._build_retry_text(error, 2)
        assert text == "Custom retry 2: err"

    def test_custom_builder_empty_fallback(self):
        """Custom builder returning empty string falls back to default."""

        def empty_builder(error, attempt):
            return ""

        node = _make_node(
            config_overrides={
                "retry_policy": NodeRetryPolicy(
                    max_attempts=2,
                    retry_continuation_builder=empty_builder,
                ),
            }
        )
        error = ValidationError("err")
        text = node._build_retry_text(error, 1)
        assert "Retry attempt 1" in text  # fallback

    def test_custom_builder_exception_fallback(self):
        """Custom builder raising exception falls back to default."""

        def bad_builder(error, attempt):
            raise RuntimeError("builder crashed")

        node = _make_node(
            config_overrides={
                "retry_policy": NodeRetryPolicy(
                    max_attempts=2,
                    retry_continuation_builder=bad_builder,
                ),
            }
        )
        error = ValidationError("err")
        text = node._build_retry_text(error, 1)
        assert "Retry attempt 1" in text  # fallback


class TestHandleExhaustion:
    """Tests for Node._handle_exhaustion()."""

    def test_raise_policy(self):
        """raise policy raises NodeExecutionError."""
        node = _make_node(
            config_overrides={
                "retry_policy": NodeRetryPolicy(
                    max_attempts=2,
                    on_retry_exhausted="raise",
                ),
            }
        )
        validation = ValidationResult(is_valid=False, errors=["fail"])
        with pytest.raises(NodeExecutionError, match="Retry exhausted"):
            node._handle_exhaustion(validation, 2)

    def test_record_failure_policy(self):
        """record_failure policy writes diagnostics without downstream context."""
        node = _make_node(
            config_overrides={
                "retry_policy": NodeRetryPolicy(
                    max_attempts=2,
                    on_retry_exhausted="record_failure",
                ),
            }
        )
        validation = ValidationResult(is_valid=False, errors=["fail"])
        node._handle_exhaustion(validation, 2)
        assert node.session.session_context == []
        assert any(
            "RETRY_EXHAUSTED" in item["message"] for item in node.session.diagnostics
        )

    def test_route_failure_fallback(self):
        """route_failure falls back to record_failure when no route defined."""
        node = _make_node(
            config_overrides={
                "retry_policy": NodeRetryPolicy(
                    max_attempts=2,
                    on_retry_exhausted="route_failure",
                ),
            }
        )
        validation = ValidationResult(is_valid=False, errors=["fail"])
        node._handle_exhaustion(validation, 2)
        # Should have recorded diagnostic failure as fallback.
        assert node.session.session_context == []
        assert any(
            "RETRY_EXHAUSTED" in item["message"] for item in node.session.diagnostics
        )


class TestRecordFailure:
    """Tests for Node._record_failure()."""

    def test_records_failure_metadata(self):
        """Failure diagnostic contains node_id, attempts, and errors."""
        node = _make_node(
            config_overrides={
                "retry_policy": NodeRetryPolicy(max_attempts=3),
            }
        )
        validation = ValidationResult(is_valid=False, errors=["err1", "err2"])
        node._record_failure(validation, 3)
        assert node.session.session_context == []
        entry = node.session.diagnostics[-1]
        assert "RETRY_EXHAUSTED" in entry["message"]
        assert entry["node_id"] == "test"
        assert entry["attempts"] == 3
        assert "err1" in entry["errors"]

    def test_max_attempts_zero_single_attempt(self):
        """max_attempts=0 results in 1 attempt with immediate exhaustion."""
        node = _make_node(
            config_overrides={
                "retry_policy": NodeRetryPolicy(
                    max_attempts=0,
                    on_retry_exhausted="raise",
                ),
            }
        )
        validation = ValidationResult(is_valid=False, errors=["fail"])
        with pytest.raises(NodeExecutionError, match="Retry exhausted"):
            node._handle_exhaustion(validation, 1)
