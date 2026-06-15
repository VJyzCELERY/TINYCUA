"""Integration tests for retry, validation, and monitor hook through TinyCUALoop."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tinycua.config.node_config import NodeConfigBase, NodeRetryPolicy
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops.node import DecisionNode, NodeExecutionError, ProcessNode
from tinycua.loops.tinycua_loop import TinyCUALoop
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

    def on_before_node_call(
        self, node_id, session_id, attempt, messages, resolved_tools
    ):
        self.before_calls.append(
            {
                "node_id": node_id,
                "session_id": session_id,
                "attempt": attempt,
                "message_count": len(messages),
            }
        )
        return None

    def on_after_node_call(
        self, node_id, session_id, attempt, result, validation_result
    ):
        self.after_calls.append(
            {
                "node_id": node_id,
                "session_id": session_id,
                "attempt": attempt,
                "is_valid": validation_result.is_valid,
            }
        )
        return None

    def on_retry_exhausted(self, node_id, session_id, error, attempts):
        self.exhausted_calls.append(
            {
                "node_id": node_id,
                "session_id": session_id,
                "error": str(error),
                "attempts": attempts,
            }
        )
        return None


def test_retry_with_validation_fn_integration():
    """End-to-end: node retries when custom validation_fn rejects output."""
    reject_calls = [0]

    def reject_first_call(result):
        reject_calls[0] += 1
        if reject_calls[0] <= 1:
            return ValidationResult(is_valid=False, errors=["Custom validation failed"])
        return ValidationResult(is_valid=True, errors=[])

    mock_llm = MockLLM(
        [
            {"role": "assistant", "content": "bad response"},
            {"role": "assistant", "content": "good response"},
        ]
    )
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
    """End-to-end: retry exhaustion records diagnostics, not context."""
    mock_llm = MockLLM(
        [
            {"role": "assistant", "content": "bad"},
            {"role": "assistant", "content": "bad again"},
        ]
    )
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
    assert not any("RETRY_EXHAUSTED" in str(e.content) for e in node.session.session_context)
    assert any(
        "RETRY_EXHAUSTED" in item["message"]
        for item in node.session.diagnostics
    )


def test_exhaustion_raise_integration():
    """End-to-end: retry exhaustion raises NodeExecutionError."""
    mock_llm = MockLLM(
        [
            {"role": "assistant", "content": "bad"},
            {"role": "assistant", "content": "still bad"},
        ]
    )
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
    mock_llm = MockLLM(
        [
            LLMResult(content="bad", tool_calls=[]),
            LLMResult(
                content="good", tool_calls=[{"function": {"name": "required_tool"}}]
            ),
        ]
    )
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
    mock_llm = MockLLM(
        [
            {"role": "assistant", "content": "only attempt"},
        ]
    )
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


class AgentMonitorRecorder:
    """Monitor that records AgentMonitor hook calls for assertion."""

    def __init__(self):
        self.before_calls = []
        self.after_calls = []

    def on_before_node_call(
        self, node_id, session_id, attempt, messages, resolved_tools
    ):
        self.before_calls.append(
            {
                "node_id": node_id,
                "session_id": session_id,
                "attempt": attempt,
                "message_count": len(messages),
            }
        )
        return None

    def on_after_node_call(
        self, node_id, session_id, attempt, result, validation_result
    ):
        self.after_calls.append(
            {
                "node_id": node_id,
                "session_id": session_id,
                "attempt": attempt,
            }
        )
        return None


@pytest.mark.asyncio
async def test_agent_monitor_observes_execute_node():
    """Integration: AgentMonitor receives correct hooks through TinyCUALoop._execute_node().

    Verifies that agent_monitor.on_before_node_call and on_after_node_call
    are called with root_session.session_id (not node.session.session_id)
    and attempt=1 at the agent level.
    """
    agent_monitor = AgentMonitorRecorder()
    loop = TinyCUALoop(agent_monitor=agent_monitor)

    config = NodeConfigBase(
        llm_client=MockLLM(
            [
                {"role": "assistant", "content": "node output"},
            ]
        ),
    )
    node = ProcessNode(node_id="test-node", config=config, instruction="Do work")
    node.session = loop.root_session

    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "node output", "tool_calls": None}
    )

    await loop._execute_node(node, agent, tools=[])

    # AgentMonitor should have been called with root_session.session_id
    assert len(agent_monitor.before_calls) == 1
    assert len(agent_monitor.after_calls) == 1

    before = agent_monitor.before_calls[0]
    assert before["node_id"] == "test-node"
    assert before["session_id"] == loop.root_session.session_id
    assert before["attempt"] == 1

    after = agent_monitor.after_calls[0]
    assert after["node_id"] == "test-node"
    assert after["session_id"] == loop.root_session.session_id
    assert after["attempt"] == 1


class NodeWithFailureRoute(ProcessNode):
    """ProcessNode subclass that defines a failure route."""

    def __init__(self, *args, failure_route_called=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._failure_route_called = (
            failure_route_called if failure_route_called is not None else []
        )

    def _call_failure_route(self) -> bool:
        """Override to simulate a failure route being called."""
        self._failure_route_called.append(True)
        return True


def test_route_failure_with_real_failure_route():
    """route_failure calls the failure route instead of _record_failure when defined."""
    mock_llm = MockLLM(
        [
            LLMResult(content="bad"),
            LLMResult(content="bad again"),
        ]
    )
    config = NodeConfigBase(
        llm_client=mock_llm,
        retry_policy=NodeRetryPolicy(
            max_attempts=2,
            required_tool_calls=["required_tool"],
            on_retry_exhausted="route_failure",
        ),
    )
    failure_route_called = []
    node = NodeWithFailureRoute(
        node_id="test",
        config=config,
        instruction="Do work",
        failure_route_called=failure_route_called,
    )
    node.session = Session()
    node("input")

    # Failure route should have been called instead of recording failure
    assert len(failure_route_called) == 1
    # Session should NOT have RETRY_EXHAUSTED since route was called
    contents = [e.content for e in node.session.session_context]
    assert not any("RETRY_EXHAUSTED" in c for c in contents)


def test_custom_continuation_builder_through_retry_loop():
    """Custom retry_continuation_builder is invoked during retry."""
    builder_calls = []

    def custom_builder(error, attempt):
        builder_calls.append({"error": str(error), "attempt": attempt})
        return f"Custom retry {attempt}: {error}"

    mock_llm = MockLLM(
        [
            LLMResult(content="bad"),
            LLMResult(content="good"),
        ]
    )
    config = NodeConfigBase(
        llm_client=mock_llm,
        retry_policy=NodeRetryPolicy(
            max_attempts=2,
            required_tool_calls=["required_tool"],
            retry_continuation_builder=custom_builder,
        ),
    )
    node = ProcessNode(node_id="test", config=config, instruction="Do work")
    node.session = Session()
    result = node("input")

    assert result.content == "good"
    assert len(builder_calls) == 1
    assert builder_calls[0]["attempt"] == 1
    assert "required_tool" in builder_calls[0]["error"]


def test_decision_node_monitor_hooks_during_retry():
    """DecisionNode fires monitor hooks during classification retry."""
    monitor = RecordingMonitor()
    mock_llm = MockLLM(
        [
            LLMResult(content="analysis 1"),
            LLMResult(content="wrong"),
            LLMResult(content="analysis 2"),
            LLMResult(content="valid_label"),
        ]
    )
    config = NodeConfigBase(
        llm_client=mock_llm,
        retry_policy=NodeRetryPolicy(max_attempts=2),
        monitor=monitor,
    )
    node = DecisionNode(
        node_id="test-decision",
        config=config,
        instruction="Analyze and classify",
        classification_labels=["valid_label"],
    )
    node.session = Session()
    result = node("input")

    assert result.route_label == "valid_label"
    # Should have 2 before calls (2 classification attempts)
    assert len(monitor.before_calls) == 2
    assert monitor.before_calls[0]["attempt"] == 1
    assert monitor.before_calls[1]["attempt"] == 2
    # After-hook is only called on failed validation, not on success
    # First attempt failed (wrong label), second succeeded (valid_label)
    assert len(monitor.after_calls) == 1
    assert monitor.after_calls[0]["is_valid"] is False


@pytest.mark.asyncio
async def test_agent_monitor_with_retrying_node_through_loop():
    """AgentMonitor sees retry attempts through TinyCUALoop._execute_node()."""
    agent_monitor = AgentMonitorRecorder()
    loop = TinyCUALoop(agent_monitor=agent_monitor)

    # Node that would retry internally, but _execute_node bypasses node.__call__
    # So AgentMonitor should see attempt=1 (loop-level)
    config = NodeConfigBase(
        llm_client=MockLLM(
            [
                {"role": "assistant", "content": "node output"},
            ]
        ),
    )
    node = ProcessNode(node_id="test-node", config=config, instruction="Do work")
    node.session = loop.root_session

    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "node output", "tool_calls": None}
    )

    await loop._execute_node(node, agent, tools=[])

    # AgentMonitor should see attempt=1 at agent level
    assert len(agent_monitor.before_calls) == 1
    assert len(agent_monitor.after_calls) == 1

    before = agent_monitor.before_calls[0]
    assert before["attempt"] == 1

    after = agent_monitor.after_calls[0]
    assert after["attempt"] == 1
