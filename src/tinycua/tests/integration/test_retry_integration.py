"""Integration tests for retry, validation, and monitor hook through TinyCUALoop.

Node-level retry is owned by the loop path (TinyCUALoop._call_node_with_retry),
not by Node.__call__ (which is now single-shot). Tests that exercised retry via
node.__call__ directly have been removed; the loop-owned path is covered by
test_unbounded_recovery.py and the _execute_node-based tests below.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.loops.node import ProcessNode
from tinycua.loops.tinycua_loop import TinyCUALoop


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
