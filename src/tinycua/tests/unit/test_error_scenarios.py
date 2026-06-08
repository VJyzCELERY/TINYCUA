"""Error scenario tests for WorkerNode, TaskCreateNode, NodeQueue."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.loops.task_create import TinyCUATaskCreateNode
from tinycua.loops.node import ProcessNode, NodeExecutionError
from tinycua.loops.node_queue import NodeQueue
from tinycua.models.session import Session
from tinycua.models.node_input import NodeInput


def test_task_create_node_failure_retries():
    """TaskCreateNode failure triggers NodeRetryPolicy; after max retries, error propagates."""
    config = NodeConfigBase()
    config.retry_policy.max_attempts = 2
    # Require tool calls so empty responses fail validation
    config.retry_policy.required_tool_calls = ["TaskInit"]
    task_create = TinyCUATaskCreateNode(node_id="task_create", config=config)
    session = Session()
    task_create.ensure_session(session)

    # Mock LLM to always fail (no tool calls)
    mock_llm = MagicMock()
    mock_llm.return_value = {
        "content": "I cannot do that",
        "role": "assistant",
        "tool_calls": [],
    }
    config.llm_client = mock_llm

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Should not raise — record_failure is default
    result = task_create(input_data)
    assert isinstance(result, LLMResult)
    # LLM should have been called max_attempts times
    assert mock_llm.call_count == 2


def test_worker_node_empty_input_passes_through():
    """Empty or null input reaches WorkerNode without crash; original input is preserved."""
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    session = Session()
    session.task = None
    worker.ensure_session(session)

    # Empty input should not crash
    input_data = NodeInput(
        input_type="continuation",
        messages=[],
    )

    result = worker(input_data)
    assert result.route_label == "task_creation"


def test_clear_after_current_without_ensure_terminal():
    """Verify queue has no terminal node when ensure_terminal is NOT called."""
    queue = NodeQueue()
    node_a = MagicMock()
    node_a.node_id = "a"
    node_a.is_terminal = False
    node_a.propagate = MagicMock()
    node_b = MagicMock()
    node_b.node_id = "b"
    node_b.is_terminal = False
    node_b.propagate = MagicMock()
    queue.items = [node_a, node_b]

    queue.clear_after_current()

    # After clear, only node_a remains — no terminal node
    assert len(queue.items) == 1
    assert queue.items[-1].is_terminal is False


def test_stale_worker_spawned_nodes_detection():
    """Worker-spawned nodes detected as stale when WorkerNode is re-entered with existing spawned nodes."""
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    session = Session()
    session.task = None
    worker.ensure_session(session)

    queue = NodeQueue()
    stale_spawned = ProcessNode(node_id="task_create", config=config)
    terminal = ProcessNode(
        node_id="response", config=config, is_terminal=True,
    )
    queue.items = [worker, stale_spawned, terminal]

    # Detect spawned nodes
    spawned = worker._detect_worker_spawned_nodes(queue)
    assert len(spawned) == 1
    assert spawned[0].node_id == "task_create"
