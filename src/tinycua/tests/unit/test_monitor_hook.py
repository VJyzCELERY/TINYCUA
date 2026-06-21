"""Unit tests for NodeMonitor and AgentMonitor hook behavior."""

from tinycua.config.node_config import NodeConfigBase, NodeRetryPolicy
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops.node import ProcessNode
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


class ContinuationMonitor:
    """Monitor that returns continuation strings from hooks."""

    def on_before_node_call(
        self, node_id, session_id, attempt, messages, resolved_tools
    ):
        return f"monitor-before-{attempt}"

    def on_after_node_call(
        self, node_id, session_id, attempt, result, validation_result
    ):
        return f"monitor-after-{attempt}"

    def on_retry_exhausted(self, node_id, session_id, error, attempts):
        return None


class ExceptionMonitor:
    """Monitor that raises exceptions in all hooks."""

    def on_before_node_call(
        self, node_id, session_id, attempt, messages, resolved_tools
    ):
        raise RuntimeError("before hook crashed")

    def on_after_node_call(
        self, node_id, session_id, attempt, result, validation_result
    ):
        raise RuntimeError("after hook crashed")

    def on_retry_exhausted(self, node_id, session_id, error, attempts):
        raise RuntimeError("exhausted hook crashed")


def _make_node(monitor=None, max_attempts=1, **kwargs):
    """Create a ProcessNode with mock LLM for testing (single-shot)."""
    config = NodeConfigBase(
        llm_client=MockLLM(
            [
                LLMResult(content="good", tool_calls=[]),
            ]
        ),
        retry_policy=NodeRetryPolicy(
            max_attempts=max_attempts,
            **kwargs,
        ),
        monitor=monitor,
    )
    node = ProcessNode(node_id="test-node", config=config, instruction="Do work")
    node.session = Session()
    return node


class TestNodeMonitorHookTriggerPoints:
    """Tests for NodeMonitor hook call patterns (single-shot __call__)."""

    def test_before_hook_called_once_per_call(self):
        """on_before_node_call is called once (single-shot — retry is loop-owned)."""
        monitor = RecordingMonitor()
        node = _make_node(monitor=monitor)
        node("input")
        assert len(monitor.before_calls) == 1
        assert monitor.before_calls[0]["attempt"] == 1

    def test_after_hook_not_called_on_single_shot_success(self):
        """on_after_node_call is not called — single-shot __call__ has no validation loop.

        The after-hook fires on validation failure during retry, which is now
        owned by TinyCUALoop._call_node_with_retry, not by __call__.
        """
        monitor = RecordingMonitor()
        node = _make_node(monitor=monitor)
        node("input")
        # __call__ is single-shot: no validation loop, no after-hook.
        assert len(monitor.after_calls) == 0

    def test_exhausted_hook_not_called_on_success(self):
        """on_retry_exhausted is not called when the call succeeds."""
        monitor = RecordingMonitor()
        node = _make_node(monitor=monitor)
        node("input")
        assert len(monitor.exhausted_calls) == 0

    def test_exhausted_hook_not_called_on_single_shot(self):
        """on_retry_exhausted is not called by single-shot __call__.

        Exhaustion handling is owned by the loop path
        (TinyCUALoop._call_node_with_retry), not by __call__.
        """
        monitor = RecordingMonitor()
        config = NodeConfigBase(
            llm_client=MockLLM(
                [
                    LLMResult(content="bad1", tool_calls=[]),
                ]
            ),
            retry_policy=NodeRetryPolicy(
                max_attempts=1,
                required_tool_calls=["required_tool"],
                on_retry_exhausted="record_failure",
            ),
            monitor=monitor,
        )
        node = ProcessNode(node_id="test-node", config=config, instruction="Do work")
        node.session = Session()
        node("input")
        # __call__ is single-shot — no validation, no exhaustion handling.
        assert len(monitor.exhausted_calls) == 0


class TestNodeMonitorHookArguments:
    """Tests for NodeMonitor hook argument correctness."""

    def test_before_hook_args(self):
        """on_before_node_call receives correct arguments."""
        monitor = RecordingMonitor()
        node = _make_node(monitor=monitor)
        node("input")
        call = monitor.before_calls[0]
        assert call["node_id"] == "test-node"
        assert call["session_id"] == node.session.session_id
        assert isinstance(call["message_count"], int)


class TestNodeMonitorHookException:
    """Tests for NodeMonitor hook exception handling."""

    def test_exception_in_before_hook_logged(self):
        """Exception in before hook is logged and does not break execution."""
        monitor = ExceptionMonitor()
        node = _make_node(monitor=monitor)
        # Should not raise — exception is swallowed
        result = node("input")
        assert result.content == "good"  # single-shot returns first response


class TestNodeMonitorContinuation:
    """Tests for monitor hook continuation messages."""

    def test_before_hook_return_value_discarded(self):
        """Continuation appending is deferred (FR-012). Return values are currently discarded."""
        monitor = ContinuationMonitor()
        config = NodeConfigBase(
            llm_client=MockLLM(
                [
                    LLMResult(content="good", tool_calls=[]),
                ]
            ),
            retry_policy=NodeRetryPolicy(
                max_attempts=1,
            ),
            monitor=monitor,
        )
        node = ProcessNode(node_id="test-node", config=config, instruction="Do work")
        node.session = Session()
        result = node("input")
        assert result.content == "good"


class TestAgentMonitorIndependence:
    """Tests for AgentMonitor firing independently from NodeMonitor."""

    def test_both_monitors_fire_independently(self):
        """AgentMonitor and NodeMonitor both fire when both configured."""
        agent_monitor = RecordingMonitor()
        node_monitor = RecordingMonitor()
        config = NodeConfigBase(
            llm_client=MockLLM(
                [
                    LLMResult(content="good", tool_calls=[]),
                ]
            ),
            retry_policy=NodeRetryPolicy(
                max_attempts=1,
            ),
            monitor=node_monitor,
        )
        node = ProcessNode(node_id="test-node", config=config, instruction="Do work")
        node.session = Session()
        # Simulate what TinyCUALoop._execute_node does for AgentMonitor
        agent_monitor.on_before_node_call(
            node.node_id, node.session.session_id, 1, [], []
        )
        node("input")
        agent_monitor.on_after_node_call(
            node.node_id,
            node.session.session_id,
            1,
            LLMResult(content="good"),
            ValidationResult(is_valid=True, errors=[]),
        )
        # Both monitors should have been called
        assert len(agent_monitor.before_calls) == 1
        assert len(agent_monitor.after_calls) == 1
        # __call__ is single-shot: one before-hook, no after-hook (no retry)
        assert len(node_monitor.before_calls) == 1
        assert len(node_monitor.after_calls) == 0

    def test_agent_monitor_attempt_always_one(self):
        """AgentMonitor always receives attempt=1 at agent level."""
        agent_monitor = RecordingMonitor()
        config = NodeConfigBase(
            llm_client=MockLLM(
                [
                    LLMResult(content="good", tool_calls=[]),
                ]
            ),
            retry_policy=NodeRetryPolicy(
                max_attempts=1,
            ),
            monitor=RecordingMonitor(),
        )
        node = ProcessNode(node_id="test-node", config=config, instruction="Do work")
        node.session = Session()
        # Simulate AgentMonitor calls with attempt=1 (as TinyCUALoop does)
        agent_monitor.on_before_node_call(
            node.node_id, node.session.session_id, 1, [], []
        )
        node("input")
        agent_monitor.on_after_node_call(
            node.node_id,
            node.session.session_id,
            1,
            LLMResult(content="good"),
            ValidationResult(is_valid=True, errors=[]),
        )
        # AgentMonitor always sees attempt=1
        assert agent_monitor.before_calls[0]["attempt"] == 1
        assert agent_monitor.after_calls[0]["attempt"] == 1
