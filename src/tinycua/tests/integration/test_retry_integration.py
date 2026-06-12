"""Integration tests for retry, validation, and monitor hook through TinyCUALoop."""

import pytest

from tinycua.config.node_config import NodeConfigBase, NodeRetryPolicy
from tinycua.config.types import LLMResult, ValidationResult
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


class RecordingMonitor:
    """Monitor that records all hook calls for assertion."""

    def __init__(self):
        self.before_calls = []
        self.after_calls = []
        self.exhausted_calls = []

    def on_before_node_call(self, node_id, session_id, attempt, messages, resolved_tools):
        self.before_calls.append({
            "node_id": node_id, "session_id": session_id,
            "attempt": attempt, "message_count": len(messages),
        })
        return None

    def on_after_node_call(self, node_id, session_id, attempt, result, validation_result):
        self.after_calls.append({
            "node_id": node_id, "session_id": session_id,
            "attempt": attempt, "is_valid": validation_result.is_valid,
        })
        return None

    def on_retry_exhausted(self, node_id, session_id, error, attempts):
        self.exhausted_calls.append({
            "node_id": node_id, "session_id": session_id,
            "error": str(error), "attempts": attempts,
        })
        return None


def test_retry_with_validation_fn_integration():
    """End-to-end: node retries when custom validation_fn rejects output."""
    reject_calls = [0]

    def reject_first_call(result):
        reject_calls[0] += 1
        if reject_calls[0] <= 1:
            return ValidationResult(is_valid=False, errors=["Custom validation failed"])
        return ValidationResult(is_valid=True, errors=[])

    mock_llm = MockLLM([
        {"role": "assistant", "content": "bad response"},
        {"role": "assistant", "content": "good response"},
    ])
    config = NodeConfigBase(
        llm_client=mock_llm,
        retry_policy=NodeRetryPolicy(
            max_attempts=2,
            validation_fn=reject_first_call,
        ),
    )
    node = ProcessNode(node_id="test", config=config, instruction="Do work")
    node.session = Session()
    result = node("input")
    assert result.content == "good response"
    assert mock_llm.call_count == 2


def test_exhaustion_record_failure_integration():
    """End-to-end: retry exhaustion writes failure state to session."""
    mock_llm = MockLLM([
        {"role": "assistant", "content": "bad"},
        {"role": "assistant", "content": "bad again"},
    ])
    config = NodeConfigBase(
        llm_client=mock_llm,
        retry_policy=NodeRetryPolicy(
            max_attempts=2,
            required_tool_calls=["required_tool"],
            on_retry_exhausted="record_failure",
        ),
    )
    node = ProcessNode(node_id="test", config=config, instruction="Do work")
    node.session = Session()
    node("input")
    # Session should have failure state recorded
    contents = [e.content for e in node.session.session_context]
    assert any("RETRY_EXHAUSTED" in c for c in contents)


def test_exhaustion_raise_integration():
    """End-to-end: retry exhaustion raises NodeExecutionError."""
    mock_llm = MockLLM([
        {"role": "assistant", "content": "bad"},
        {"role": "assistant", "content": "still bad"},
    ])
    config = NodeConfigBase(
        llm_client=mock_llm,
        retry_policy=NodeRetryPolicy(
            max_attempts=2,
            required_tool_calls=["required_tool"],
            on_retry_exhausted="raise",
        ),
    )
    node = ProcessNode(node_id="test", config=config, instruction="Do work")
    node.session = Session()
    with pytest.raises(NodeExecutionError, match="Retry exhausted"):
        node("input")


def test_monitor_hook_observes_full_cycle():
    """End-to-end: monitor hook is called at correct trigger points."""
    monitor = RecordingMonitor()
    mock_llm = MockLLM([
        LLMResult(content="bad", tool_calls=[]),
        LLMResult(content="good", tool_calls=[{"function": {"name": "required_tool"}}]),
    ])
    config = NodeConfigBase(
        llm_client=mock_llm,
        retry_policy=NodeRetryPolicy(
            max_attempts=2,
            required_tool_calls=["required_tool"],
        ),
        monitor=monitor,
    )
    node = ProcessNode(node_id="test-node", config=config, instruction="Do work")
    node.session = Session()
    node("input")

    assert len(monitor.before_calls) == 2  # 2 attempts
    assert monitor.before_calls[0]["attempt"] == 1
    assert monitor.before_calls[1]["attempt"] == 2
    assert len(monitor.after_calls) == 1  # only 1 failed validation (attempt 1)
    assert monitor.after_calls[0]["is_valid"] is False
    assert len(monitor.exhausted_calls) == 0  # succeeded on attempt 2


def test_max_attempts_zero_single_attempt():
    """End-to-end: max_attempts=0 results in 1 attempt (no retry)."""
    mock_llm = MockLLM([
        {"role": "assistant", "content": "only attempt"},
    ])
    config = NodeConfigBase(
        llm_client=mock_llm,
        retry_policy=NodeRetryPolicy(
            max_attempts=0,
            required_tool_calls=["required_tool"],
            on_retry_exhausted="raise",
        ),
    )
    node = ProcessNode(node_id="test", config=config, instruction="Do work")
    node.session = Session()
    with pytest.raises(NodeExecutionError, match="Retry exhausted"):
        node("input")
    assert mock_llm.call_count == 1
