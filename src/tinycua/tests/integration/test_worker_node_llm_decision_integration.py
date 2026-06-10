"""Integration tests for TinyCUAWorkerNode LLM decision when task exists."""

# --- Standard library ---
from itertools import cycle

import pytest
from unittest.mock import MagicMock

# --- Third-party / local ---
from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.config.node_config import NodeRetryPolicy
from tinycua.loops.node import DecisionResult, NodeExecutionError, ProcessNode
from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.models.session import Session
from tinycua.models.node_input import NodeInput


def _make_session_with_task(task: str = "Write a sorting script") -> Session:
    """Create a Session with an existing task (matches existing test patterns)."""
    session = Session()
    session.task = task
    return session


def _make_mock_node(node_id: str, is_terminal: bool = False) -> ProcessNode:
    """Create a lightweight mock node for queue testing.

    Returns a ProcessNode with the given node_id. Uses MagicMock for llm_client
    to avoid real LLM calls during queue operations.
    """
    config = NodeConfigBase(llm_client=MagicMock())
    return ProcessNode(node_id=node_id, config=config, is_terminal=is_terminal)


def test_worker_node_llm_decision_with_task_exists():
    """WorkerNode performs two-step LLM decision (analysis → classification) when task exists."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Mock LLM: analysis → task_recreation (valid), repeats for all attempts
    mock_analysis = LLMResult(content="Worker should recreate task", role="assistant")
    mock_classification = LLMResult(content="task_recreation", role="assistant")
    mock_llm = MagicMock(side_effect=cycle([mock_analysis, mock_classification]))
    worker._call_llm = mock_llm

    # Act
    result = worker(input_data)

    # Assert — verify LLM calls occurred and route label is correct
    assert result.route_label == "task_recreation"
    assert result.analysis_response == mock_analysis
    assert result.classification_response == mock_classification


def test_worker_node_dynamic_labels_with_worker_spawned():
    """Classification labels include passthrough when worker-spawned nodes exist."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]
    # Simulate worker-spawned node
    spawned = _make_mock_node("spawned_task")
    queue.spawn_after_current([spawned])

    # Act
    labels = worker._get_classification_labels(queue)

    # Assert
    assert "passthrough" in labels
    assert "task_recreation" in labels
    assert "task_reanalysis" in labels
    assert "proceed_execution" in labels


def test_worker_node_dynamic_labels_without_worker_spawned():
    """Classification labels exclude passthrough when no worker-spawned nodes exist."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]

    # Act
    labels = worker._get_classification_labels(queue)

    # Assert
    assert "passthrough" not in labels
    assert "task_recreation" in labels
    assert "task_reanalysis" in labels
    assert "proceed_execution" in labels


def test_worker_node_call_uses_dynamic_labels_with_spawned_nodes():
    """__call__ adjusts classification labels based on queue state when queue is available (FR-003)."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]
    spawned = _make_mock_node("spawned_task")
    queue.spawn_after_current([spawned])
    # Set queue reference (mimics on_complete from previous call)
    worker._queue = queue

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Mock LLM to capture classification labels passed to _classify
    mock_analysis = LLMResult(content="Worker should passthrough", role="assistant")
    mock_classification = LLMResult(content="passthrough", role="assistant")
    mock_llm = MagicMock(side_effect=cycle([mock_analysis, mock_classification]))
    worker._call_llm = mock_llm

    # Act
    result = worker(input_data)

    # Assert — classification labels should include passthrough (4 labels total)
    # The second LLM call is the classification call; check the messages passed to it
    classification_call_args = mock_llm.call_args_list[1]
    classification_messages = classification_call_args[0][0]
    # The classification instruction message contains the labels
    labels_msg = classification_messages[-1]["content"]
    assert "passthrough" in labels_msg
    assert result.route_label == "passthrough"


def test_worker_node_call_uses_dynamic_labels_without_spawned_nodes():
    """__call__ adjusts classification labels based on queue state when queue is available (FR-003)."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]
    # Set queue reference (mimics on_complete from previous call)
    worker._queue = queue

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Mock LLM
    mock_analysis = LLMResult(content="Worker should proceed", role="assistant")
    mock_classification = LLMResult(content="proceed_execution", role="assistant")
    mock_llm = MagicMock(side_effect=cycle([mock_analysis, mock_classification]))
    worker._call_llm = mock_llm

    # Act
    result = worker(input_data)

    # Assert — classification labels should NOT include passthrough (3 labels)
    classification_call_args = mock_llm.call_args_list[1]
    classification_messages = classification_call_args[0][0]
    labels_msg = classification_messages[-1]["content"]
    assert "passthrough" not in labels_msg
    assert result.route_label == "proceed_execution"


def test_worker_node_route_task_recreation():
    """task_recreation route handler clears worker-spawned nodes and spawns TaskAnalyzerNode with TaskInit/TaskCreate tools."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]
    spawned = _make_mock_node("old_spawned")
    queue.spawn_after_current([spawned])

    result = DecisionResult(
        route_label="task_recreation",
        analysis_response=LLMResult(content="analysis text", role="assistant"),
        classification_response=LLMResult(content="task_recreation", role="assistant"),
    )

    # Act
    worker._route_task_recreation(queue, result)

    # Assert — old spawned node cleared, TaskAnalyzerNode spawned with correct mode
    node_ids = [n.node_id for n in queue.items]
    assert "old_spawned" not in node_ids
    assert "task_analyzer" in node_ids

    # CRITICAL: Assert mode is "recreation" (NOT "initial_analysis")
    task_analyzer = [n for n in queue.items if n.node_id == "task_analyzer"][0]
    assert task_analyzer.mode == "recreation"  # Includes TaskInit/TaskCreate


def test_worker_node_route_task_reanalysis():
    """task_reanalysis route handler clears worker-spawned nodes and spawns TaskAnalyzerNode without TaskInit/TaskCreate."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]
    spawned = _make_mock_node("old_spawned")
    queue.spawn_after_current([spawned])

    result = DecisionResult(
        route_label="task_reanalysis",
        analysis_response=LLMResult(content="analysis text", role="assistant"),
        classification_response=LLMResult(content="task_reanalysis", role="assistant"),
    )

    # Act
    worker._route_task_reanalysis(queue, result)

    # Assert — TaskAnalyzerNode spawned without task_init/task_create tools
    task_analyzer = [n for n in queue.items if n.node_id == "task_analyzer"][0]
    assert task_analyzer.mode == "reanalysis"  # Excludes TaskInit/TaskCreate


def test_worker_node_route_passthrough():
    """passthrough route handler advances queue and forwards input to next worker-spawned node."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]
    spawned = _make_mock_node("next_node")
    queue.spawn_after_current([spawned])

    result = DecisionResult(
        route_label="passthrough",
        analysis_response=LLMResult(content="analysis text", role="assistant"),
        classification_response=LLMResult(content="passthrough", role="assistant"),
    )

    worker._last_input = NodeInput(input_type="continuation", messages=[])
    worker._route_passthrough(queue, result)

    # Assert — worker removed, next_node is now current, input forwarded
    assert queue.items[0].node_id == "next_node"
    # Verify input was forwarded to next node (behavioral contract)
    # NOTE: Accesses private NodeQueue._inputs — intentional coupling for test purposes.
    # Refactor if NodeQueue changes input storage implementation.
    assert queue._inputs.get("next_node") is not None
    # Assert — result object preserved (on_complete uses result.route_label for dispatch)
    assert result.route_label == "passthrough"


def test_worker_node_route_proceed_execution():
    """proceed_execution route handler ensures terminal response path (Milestone 2.3)."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]

    result = DecisionResult(
        route_label="proceed_execution",
        analysis_response=LLMResult(content="analysis text", role="assistant"),
        classification_response=LLMResult(content="proceed_execution", role="assistant"),
    )

    # Act
    worker._route_proceed_execution(queue, result)

    # Assert — terminal response path exists
    assert queue.items[-1].is_terminal


def test_worker_node_invalid_label_retry():
    """Invalid classification labels trigger retry per NodeRetryPolicy."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(retry_policy=NodeRetryPolicy(max_attempts=3, on_retry_exhausted="raise"))
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]

    # Mock LLM to return invalid label for all calls
    # _execute_with_retry calls analyze + classify (2 calls per attempt)
    # With max_attempts=3, we need 6 responses
    invalid_response = LLMResult(content="invalid_label", role="assistant")
    mock_llm = MagicMock(return_value=invalid_response)
    worker._call_llm = mock_llm

    # Act + Assert — should raise NodeExecutionError after retries
    with pytest.raises(NodeExecutionError):
        worker("Help me write a script")

    # Verify retry count: 2 calls per attempt × max_attempts
    expected_calls = 2 * config.retry_policy.max_attempts
    assert mock_llm.call_count == expected_calls


def test_worker_node_route_clear_ensures_terminal():
    """Route handlers calling clear_after_current() ensure terminal response path exists."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]

    result = DecisionResult(
        route_label="task_recreation",
        analysis_response=LLMResult(content="analysis text", role="assistant"),
        classification_response=LLMResult(content="task_recreation", role="assistant"),
    )

    # Act
    worker._route_task_recreation(queue, result)

    # Assert — terminal node exists
    last_node = queue.items[-1]
    assert last_node.is_terminal


def test_worker_node_queue_invariant_query_analyst_first():
    """QueryAnalyst remains first in queue after WorkerNode dispatches to any route (FR-016)."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    query_analyst = _make_mock_node("query_analyst", is_terminal=False)
    queue = NodeQueue()
    queue.items = [query_analyst, worker]
    queue.current_index = 1  # WorkerNode is current

    result = DecisionResult(
        route_label="task_recreation",
        analysis_response=LLMResult(content="analysis text", role="assistant"),
        classification_response=LLMResult(content="task_recreation", role="assistant"),
    )

    # Act
    worker._route_task_recreation(queue, result)

    # Assert — QueryAnalyst remains first
    assert queue.items[0].node_id == "query_analyst"


def test_worker_node_input_preservation_contract():
    """__call__ stores input on _last_input and passthrough handler forwards it via set_input (FR-013, SC-010).

    Validates the behavioral contract (input stored → input forwarded), not the full
    loop integration. In production the loop calls on_complete(queue, result) after __call__.
    """
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]
    spawned = _make_mock_node("next_node")
    queue.spawn_after_current([spawned])
    worker._queue = queue

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Mock LLM: analysis → classification as passthrough
    mock_analysis = LLMResult(content="Forward to spawned node", role="assistant")
    mock_classification = LLMResult(content="passthrough", role="assistant")
    mock_llm = MagicMock(side_effect=cycle([mock_analysis, mock_classification]))
    worker._call_llm = mock_llm

    # Act — __call__ stores input and returns DecisionResult
    result = worker(input_data)

    # Assert — input was stored on _last_input by __call__
    assert worker._last_input == input_data
    # Assert — classification produced passthrough route
    assert result.route_label == "passthrough"

    # Act — on_complete dispatches the route (mimics loop behavior)
    worker.on_complete(queue, result)

    # Assert — input was forwarded to next node via set_input
    assert queue._inputs.get("next_node") is worker._last_input


def test_worker_node_invalid_label_triggers_retry_and_succeeds():
    """Invalid classification label triggers retry, then succeeds with valid label on second attempt (FR-006)."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Mock: analysis → first classification (invalid) → second analysis → second classification (valid)
    mock_analysis = LLMResult(content="Worker should analyze task", role="assistant")
    # First classification call outputs invalid route label
    mock_classification_invalid = LLMResult(content="invalid_label", role="assistant")
    # Second classification call outputs valid route label
    mock_classification_valid = LLMResult(content="task_recreation", role="assistant")

    # _execute_with_retry calls analyze + classify per attempt (2 calls per attempt)
    # Attempt 1: analyze → mock_analysis, classify → mock_classification_invalid (invalid, triggers retry)
    # Attempt 2: analyze → mock_analysis, classify → mock_classification_valid (valid)
    # Attempt 3: analyze → mock_analysis, classify → mock_classification_valid (valid, wins)
    mock_llm = MagicMock(side_effect=[
        mock_analysis,              # Attempt 1: Analysis LLM call
        mock_classification_invalid, # Attempt 1: Classification (invalid)
        mock_analysis,              # Attempt 2: Analysis LLM call (retry)
        mock_classification_valid,   # Attempt 2: Classification (valid)
        mock_analysis,              # Attempt 3: Analysis LLM call
        mock_classification_valid,   # Attempt 3: Classification (valid — wins)
    ])
    worker._call_llm = mock_llm

    # Act
    result = worker(input_data)

    # Assert — retry succeeded with valid label (task_recreation, not invalid_label)
    assert result.route_label == "task_recreation"
    # Verify the classification result is from the valid retry attempt
    assert result.classification_response == mock_classification_valid


def test_worker_node_latest_valid_verdict_wins():
    """When multiple valid labels are returned across attempts, the last valid one wins (FR-005, SC-008)."""
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]
    spawned = _make_mock_node("next_node")
    queue.spawn_after_current([spawned])
    worker._queue = queue

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Attempt 1: analysis -> task_recreation (valid)
    # Attempt 2: analysis -> passthrough (valid, last one wins)
    # Attempt 3: analysis -> passthrough (same, for max_attempts=3)
    mock_analysis = LLMResult(content="analysis", role="assistant")
    mock_valid_1 = LLMResult(content="task_recreation", role="assistant")
    mock_valid_2 = LLMResult(content="passthrough", role="assistant")
    mock_llm = MagicMock(side_effect=[
        mock_analysis, mock_valid_1,
        mock_analysis, mock_valid_2,
        mock_analysis, mock_valid_2,
    ])
    worker._call_llm = mock_llm

    result = worker(input_data)

    # The last valid classification (passthrough) should win
    assert result.route_label == "passthrough"
    assert mock_llm.call_count == 6  # 2 calls per attempt x 3 attempts
