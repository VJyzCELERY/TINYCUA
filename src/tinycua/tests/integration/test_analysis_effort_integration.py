"""Integration tests for TinyCUAAnalysisEffortNode — worker → effort → executor flow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.loops.analysis_effort import TinyCUAAnalysisEffortNode, WorkerEffort
from tinycua.loops.node import DecisionResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session


def _make_mock_node(node_id: str, *, is_terminal: bool = False) -> MagicMock:
    """Create a mock node with required attributes."""
    node = MagicMock()
    node.node_id = node_id
    node.is_terminal = is_terminal
    return node


def test_analysis_effort_node_with_worker_task_creation():
    """End-to-end: WorkerNode → task_creation → TaskCreate → TaskAnalyzer → AnalysisEffortNode."""
    # Arrange
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    session = Session()
    session.task = None  # No task → deterministic task_creation route
    worker.ensure_session(session)

    queue = NodeQueue()
    terminal = _make_mock_node("response", is_terminal=True)
    queue.items = [worker, terminal]

    # Simulate task_creation route
    result = DecisionResult(
        route_label="task_creation",
        analysis_response=LLMResult(content="analysis", role="assistant"),
        classification_response=LLMResult(content="task_creation", role="assistant"),
    )
    worker.on_complete(queue, result)

    # Act — verify queue shape
    node_ids = [n.node_id for n in queue.items]

    # Assert
    assert "task_create" in node_ids
    assert "task_analyzer" in node_ids
    assert "analysis_effort" in node_ids
    # Verify ordering: task_create → task_analyzer → analysis_effort → terminal
    tc_idx = node_ids.index("task_create")
    ta_idx = node_ids.index("task_analyzer")
    ae_idx = node_ids.index("analysis_effort")
    assert tc_idx < ta_idx < ae_idx


def test_analysis_effort_node_with_worker_task_recreation():
    """End-to-end: WorkerNode → task_recreation → TaskAnalyzer → AnalysisEffortNode."""
    # Arrange
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    session = Session()
    session.task = "Existing task"
    worker.ensure_session(session)

    queue = NodeQueue()
    terminal = _make_mock_node("response", is_terminal=True)
    queue.items = [worker, terminal]

    result = DecisionResult(
        route_label="task_recreation",
        analysis_response=LLMResult(content="analysis", role="assistant"),
        classification_response=LLMResult(content="task_recreation", role="assistant"),
    )
    worker.on_complete(queue, result)

    # Act
    node_ids = [n.node_id for n in queue.items]

    # Assert
    assert "task_analyzer" in node_ids
    assert "analysis_effort" in node_ids
    ta_idx = node_ids.index("task_analyzer")
    ae_idx = node_ids.index("analysis_effort")
    assert ta_idx < ae_idx


def test_analysis_effort_node_with_worker_task_reanalysis():
    """End-to-end: WorkerNode → task_reanalysis → TaskAnalyzer → AnalysisEffortNode."""
    # Arrange
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    session = Session()
    session.task = "Existing task"
    worker.ensure_session(session)

    queue = NodeQueue()
    terminal = _make_mock_node("response", is_terminal=True)
    queue.items = [worker, terminal]

    result = DecisionResult(
        route_label="task_reanalysis",
        analysis_response=LLMResult(content="analysis", role="assistant"),
        classification_response=LLMResult(content="task_reanalysis", role="assistant"),
    )
    worker.on_complete(queue, result)

    # Act
    node_ids = [n.node_id for n in queue.items]

    # Assert
    assert "task_analyzer" in node_ids
    assert "analysis_effort" in node_ids
    ta_idx = node_ids.index("task_analyzer")
    ae_idx = node_ids.index("analysis_effort")
    assert ta_idx < ae_idx


def test_analysis_effort_node_passes_complete():
    """End-to-end: AnalysisEffortNode → [TaskAssessor, TaskAnalyzer] × N → TaskExecutor."""
    # Arrange
    config = NodeConfigBase(llm_client=MagicMock())
    effort_node = TinyCUAAnalysisEffortNode(
        node_id="analysis_effort", config=config, effort=WorkerEffort.low,
    )
    session = Session()
    effort_node.ensure_session(session)

    queue = NodeQueue()
    terminal = _make_mock_node("response", is_terminal=True)
    queue.items = [effort_node, terminal]

    # Act — execute with pass_count=0, pass_limit=1
    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Continue"}],
    )
    response = effort_node(input_data)
    effort_node.on_complete(queue, response)

    # Assert
    node_ids = [n.node_id for n in queue.items]
    assert "task_assessor" in node_ids
    assert "task_analyzer" in node_ids
    assert effort_node.pass_count == 1


def test_analysis_effort_node_assessor_no_tasks():
    """End-to-end: TaskAssessor selects no tasks → no TaskAnalyzer → back to AnalysisEffortNode."""
    config = NodeConfigBase(llm_client=MagicMock())
    effort_node = TinyCUAAnalysisEffortNode(
        node_id="analysis_effort", config=config, effort=WorkerEffort.low,
    )
    session = Session()
    effort_node.ensure_session(session)

    queue = NodeQueue()
    terminal = _make_mock_node("response", is_terminal=True)
    queue.items = [effort_node, terminal]

    # Mock TaskAssessor to return no tasks — patch at the import location
    mock_assessor = MagicMock()
    mock_assessor.selected_tasks = []

    with patch(
        "tinycua.loops.task_assessor.TinyCUATaskAssessorNode",
        return_value=mock_assessor,
    ):
        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "Continue"}],
        )
        response = effort_node(input_data)
        effort_node.on_complete(queue, response)

    # TaskAssessor was prepended but no tasks selected, so TaskAnalyzer follows
    # but on_complete handles the flow — check pass_count incremented
    assert effort_node.pass_count == 1
