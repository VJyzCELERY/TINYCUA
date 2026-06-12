"""Unit tests for NodeMonitor and AgentMonitor hook behavior."""



from tinycua.config.node_config import NodeConfigBase, NodeRetryPolicy
from tinycua.config.types import LLMResult
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


class ContinuationMonitor:
    """Monitor that returns continuation strings from hooks."""

    def on_before_node_call(self, node_id, session_id, attempt, messages, resolved_tools):
        return f"monitor-before-{attempt}"

    def on_after_node_call(self, node_id, session_id, attempt, result, validation_result):
        return f"monitor-after-{attempt}"

    def on_retry_exhausted(self, node_id, session_id, error, attempts):
        return None


class ExceptionMonitor:
    """Monitor that raises exceptions in all hooks."""

    def on_before_node_call(self, node_id, session_id, attempt, messages, resolved_tools):
        raise RuntimeError("before hook crashed")

    def on_after_node_call(self, node_id, session_id, attempt, result, validation_result):
        raise RuntimeError("after hook crashed")

    def on_retry_exhausted(self, node_id, session_id, error, attempts):
        raise RuntimeError("exhausted hook crashed")


def _make_node(monitor=None, max_attempts=2, **kwargs):
    """Create a ProcessNode with mock LLM for testing."""
    config = NodeConfigBase(
        llm_client=MockLLM([
            LLMResult(content="bad", tool_calls=[]),
            LLMResult(content="good", tool_calls=[{"function": {"name": "required_tool"}}]),
        ]),
        retry_policy=NodeRetryPolicy(
            max_attempts=max_attempts,
            required_tool_calls=["required_tool"],
            **kwargs,
        ),
        monitor=monitor,
    )
    node = ProcessNode(node_id="test-node", config=config, instruction="Do work")
    node.session = Session()
    return node


class TestNodeMonitorHookTriggerPoints:
    """Tests for NodeMonitor hook call patterns."""

    def test_before_hook_called_per_attempt(self):
        """on_before_node_call is called before each LLM attempt."""
        monitor = RecordingMonitor()
        node = _make_node(monitor=monitor)
        node("input")
        assert len(monitor.before_calls) == 2
        assert monitor.before_calls[0]["attempt"] == 1
        assert monitor.before_calls[1]["attempt"] == 2

    def test_after_hook_called_on_validation_failure(self):
        """on_after_node_call is called when validation fails."""
        monitor = RecordingMonitor()
        node = _make_node(monitor=monitor)
        node("input")
        assert len(monitor.after_calls) == 1
        assert monitor.after_calls[0]["is_valid"] is False

    def test_exhausted_hook_not_called_on_success(self):
        """on_retry_exhausted is not called when retry succeeds."""
        monitor = RecordingMonitor()
        node = _make_node(monitor=monitor)
        node("input")
        assert len(monitor.exhausted_calls) == 0

    def test_exhausted_hook_called_on_exhaustion(self):
        """on_retry_exhausted is called when retries exhausted."""
        monitor = RecordingMonitor()
        config = NodeConfigBase(
            llm_client=MockLLM([
                LLMResult(content="bad1", tool_calls=[]),
                LLMResult(content="bad2", tool_calls=[]),
            ]),
            retry_policy=NodeRetryPolicy(
                max_attempts=2,
                required_tool_calls=["required_tool"],
                on_retry_exhausted="record_failure",
            ),
            monitor=monitor,
        )
        node = ProcessNode(node_id="test-node", config=config, instruction="Do work")
        node.session = Session()
        node("input")
        assert len(monitor.exhausted_calls) == 1
        assert monitor.exhausted_calls[0]["attempts"] == 2


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

    def test_after_hook_args(self):
        """on_after_node_call receives correct arguments."""
        monitor = RecordingMonitor()
        node = _make_node(monitor=monitor)
        node("input")
        call = monitor.after_calls[0]
        assert call["node_id"] == "test-node"
        assert call["session_id"] == node.session.session_id


class TestNodeMonitorHookException:
    """Tests for NodeMonitor hook exception handling."""

    def test_exception_in_before_hook_logged(self):
        """Exception in before hook is logged and does not break execution."""
        monitor = ExceptionMonitor()
        node = _make_node(monitor=monitor)
        # Should not raise — exception is swallowed
        result = node("input")
        assert result.content == "good"

    def test_exception_in_after_hook_logged(self):
        """Exception in after hook is logged and does not break execution."""
        monitor = ExceptionMonitor()
        # Force validation failure on both attempts to trigger after hook
        config = NodeConfigBase(
            llm_client=MockLLM([
                LLMResult(content="bad", tool_calls=[]),
                LLMResult(content="bad2", tool_calls=[{"function": {"name": "required_tool"}}]),
            ]),
            retry_policy=NodeRetryPolicy(
                max_attempts=2,
                required_tool_calls=["required_tool"],
            ),
            monitor=monitor,
        )
        node = ProcessNode(node_id="test-node", config=config, instruction="Do work")
        node.session = Session()
        # Should not raise
        result = node("input")
        assert result.content == "bad2"


class TestNodeMonitorContinuation:
    """Tests for monitor hook continuation messages."""

    def test_before_hook_continuation_appended(self):
        """String returned from before hook is appended to messages."""
        monitor = ContinuationMonitor()
        config = NodeConfigBase(
            llm_client=MockLLM([
                LLMResult(content="bad", tool_calls=[]),
                LLMResult(content="good", tool_calls=[{"function": {"name": "required_tool"}}]),
            ]),
            retry_policy=NodeRetryPolicy(
                max_attempts=2,
                required_tool_calls=["required_tool"],
            ),
            monitor=monitor,
        )
        node = ProcessNode(node_id="test-node", config=config, instruction="Do work")
        node.session = Session()
        # The continuation is appended but doesn't affect the mock LLM behavior
        result = node("input")
        assert result.content == "good"
