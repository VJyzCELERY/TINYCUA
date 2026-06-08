"""Integration tests for WorkerNode deterministic task_creation routing."""

from __future__ import annotations

from unittest.mock import MagicMock
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.node import ProcessNode
from tinycua.models.session import Session
from tinycua.models.node_input import NodeInput


def test_worker_node_routes_to_task_creation_when_no_task():
    """WorkerNode routes to task_creation deterministically when no task exists."""
    # Arrange
    from tinycua.loops.worker import TinyCUAWorkerNode
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    session.task = None  # No task exists

    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    worker.ensure_session(session)

    queue = NodeQueue()
    response_node = ProcessNode(
        node_id="response", config=config, is_terminal=True,
    )
    queue.items = [worker, response_node]

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Act
    result = worker(input_data)

    # Assert
    assert result.route_label == "task_creation"


def test_worker_node_does_not_use_llm_for_task_creation():
    """WorkerNode task_creation route does not trigger LLM decision."""
    # Arrange
    from tinycua.loops.worker import TinyCUAWorkerNode
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    session.task = None

    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    worker.ensure_session(session)

    queue = NodeQueue()
    response_node = ProcessNode(
        node_id="response", config=config, is_terminal=True,
    )
    queue.items = [worker, response_node]

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Act
    _ = worker(input_data)

    # Assert — LLM client should NOT have been called
    config.llm_client.assert_not_called()


def test_task_create_node_creates_root_task():
    """TaskCreateNode creates root task using TaskInit/TaskCreate tools."""
    # Arrange
    from tinycua.loops.task_create import TinyCUATaskCreateNode
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    config = NodeConfigBase()
    task_create = TinyCUATaskCreateNode(node_id="task_create", config=config)
    task_create.ensure_session(session)

    # Act
    # TaskCreateNode uses LLM to create task — mock the LLM response
    mock_llm = MagicMock()
    mock_llm.return_value = {
        "content": "Task created: Write a script",
        "role": "assistant",
        "tool_calls": [],
    }
    config.llm_client = mock_llm

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )
    _ = task_create(input_data)

    # Assert
    assert session.task is not None


def test_task_create_node_advances_queue_to_task_analyzer():
    """TaskCreateNode advances queue with TaskAnalyzerNode as next node."""
    # Arrange
    from tinycua.loops.task_create import TinyCUATaskCreateNode
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    config = NodeConfigBase()
    task_create = TinyCUATaskCreateNode(node_id="task_create", config=config)
    task_create.ensure_session(session)

    queue = NodeQueue()
    task_analyzer = MagicMock()
    task_analyzer.node_id = "task_analyzer"
    queue.items = [task_create, task_analyzer]

    # Mock LLM to return a successful response
    mock_llm = MagicMock()
    mock_llm.return_value = {
        "content": "Task created",
        "role": "assistant",
        "tool_calls": [],
    }
    config.llm_client = mock_llm

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )
    result = task_create(input_data)

    # Act — on_complete should advance queue
    task_create.on_complete(queue, result)

    # Assert
    assert queue.current.node_id == "task_analyzer"


def test_task_analyzer_no_task_tools_in_initial_analysis():
    """TaskAnalyzerNode (initial_analysis) does not have TaskInit/TaskCreate tools."""
    # Arrange
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode
    from tinycua.config.node_config import NodeConfigBase

    config = NodeConfigBase()
    task_analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=config,
        mode="initial_analysis",
    )

    # Assert
    assert "TaskInit" not in task_analyzer.tool_scope
    assert "TaskCreate" not in task_analyzer.tool_scope


def test_worker_node_detects_worker_spawned_nodes():
    """WorkerNode detects worker-spawned nodes in queue."""
    # Arrange
    from tinycua.loops.worker import TinyCUAWorkerNode
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    worker.ensure_session(session)

    queue = NodeQueue()
    spawned_node = ProcessNode(node_id="task_create", config=config)
    response_node = ProcessNode(
        node_id="response", config=config, is_terminal=True,
    )
    queue.items = [worker, spawned_node, response_node]

    # Act
    spawned_nodes = worker._detect_worker_spawned_nodes(queue)

    # Assert
    assert len(spawned_nodes) == 1
    assert spawned_nodes[0].node_id == "task_create"


def test_worker_node_reuse_detection():
    """Existing WorkerNode is recognized in worker-owned segment."""
    # Arrange
    from tinycua.loops.worker import TinyCUAWorkerNode
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    worker.ensure_session(session)

    queue = NodeQueue()
    response_node = ProcessNode(
        node_id="response", config=config, is_terminal=True,
    )
    queue.items = [worker, response_node]

    # Act
    existing = queue.find_existing_worker_node()

    # Assert
    assert existing is worker


def test_worker_node_records_routing_decision_in_session_context():
    """WorkerNode records routing decision in session_context for downstream nodes."""
    # Arrange
    from tinycua.loops.worker import TinyCUAWorkerNode
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    session.task = None
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    worker.ensure_session(session)

    queue = NodeQueue()
    response_node = ProcessNode(
        node_id="response", config=config, is_terminal=True,
    )
    queue.items = [worker, response_node]

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Act
    _ = worker(input_data)

    # Assert — session_context should contain the routing decision
    context_contents = [
        ctx.get("content", "") for ctx in session.session_context
    ]
    assert any("task_creation" in c for c in context_contents), (
        "Session context should contain task_creation decision"
    )


def test_clear_after_current_ensures_terminal():
    """Route handler ensures terminal response after clear."""
    # Arrange
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.loops.worker import TinyCUAWorkerNode
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    worker.ensure_session(session)

    queue = NodeQueue()
    response_node = ProcessNode(
        node_id="response", config=config, is_terminal=True,
    )
    queue.items = [worker, response_node]

    # Act — clear after current removes terminal
    queue.clear_after_current()

    # Assert — ensure_terminal should add it back
    default_response = ProcessNode(
        node_id="default_response", config=config, is_terminal=True,
    )
    queue.ensure_terminal(default_response)

    assert queue.items[-1].is_terminal
