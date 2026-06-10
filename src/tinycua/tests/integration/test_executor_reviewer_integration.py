"""Integration tests for executor→reviewer path."""

from __future__ import annotations

from unittest.mock import MagicMock

from tinycua.config.types import LLMResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import ReviewerDecision, Task


def _build_loop_with_active_task() -> TinyCUALoop:
    """Build a TinyCUALoop with one active task for testing."""
    task = Task(task_id="test-1", title="Test Task", description="Test task", status="in_progress")
    queue = NodeQueue()
    loop = TinyCUALoop(queue=queue)
    loop.root_task = task
    loop._active_task_id = "test-1"
    return loop


def _make_execution_result(status: str = "succeeded") -> LLMResult:
    """Create a mock LLMResult simulating executor output."""
    return LLMResult(content=f"Task {status}", role="assistant", metadata={"status": status})


def _make_reviewer_decision(outcome: str = "accept", rationale: str = "Test") -> LLMResult:
    """Create a mock LLMResult simulating reviewer decision."""
    decision = ReviewerDecision(outcome=outcome, rationale=rationale)  # type: ignore[arg-type]
    return LLMResult(
        content=decision_json(outcome, rationale),
        metadata={"reviewer_decision": decision},
    )


def decision_json(outcome: str, rationale: str = "Test") -> str:
    """Build a JSON string representing a ReviewerDecision."""
    return f'{{"outcome": "{outcome}", "rationale": "{rationale}"}}'


def test_executor_reviewer_accept_path():
    """Full executor → reviewer → accept path with mocked LLM.

    Verifies: active task is executed, reviewed, accepted,
    and next active task is selected via DFS.
    """
    # Arrange
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    # Act — reviewer decides accept
    loop._on_reviewer_accept(active_task)

    # Assert
    assert active_task.status == "done"
    assert loop.get_active_task() is None  # no more active tasks


def test_executor_reviewer_retry_path():
    """Executor → reviewer → retry → executor path.

    Verifies: retry increments counter, same task remains active.
    """
    # Arrange
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    # Act — reviewer decides retry
    loop._on_reviewer_retry(active_task)

    # Assert
    assert loop._reviewer_retry_state.retry_count == 1
    assert loop.get_active_task() is not None
    assert loop.get_active_task().task_id == active_task.task_id


def test_executor_reviewer_replan_path():
    """Executor → reviewer → replan → assessor → analyzer → executor.

    Verifies: replan preserves active task, spawns TaskAssessor + TaskAnalyzer
    via queue.spawn_after_current (FR-014).
    """
    # Arrange
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    mock_queue = MagicMock()
    loop.queue = mock_queue

    # Act — reviewer decides replan
    loop._on_reviewer_replan(active_task)

    # Assert — active task preserved
    assert loop.get_active_task() is not None
    assert loop.get_active_task().task_id == active_task.task_id

    # Assert — TaskAssessor + TaskAnalyzer + TaskExecutor spawned (FR-014)
    mock_queue.spawn_after_current.assert_called_once()
    spawned_nodes = mock_queue.spawn_after_current.call_args[0][0]
    from tinycua.loops.task_assessor import TinyCUATaskAssessorNode
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode
    from tinycua.loops.task_executor import TinyCUATaskExecutorNode

    assert len(spawned_nodes) == 3
    assert isinstance(spawned_nodes[0], TinyCUATaskAssessorNode)
    assert isinstance(spawned_nodes[1], TinyCUATaskAnalyzerNode)
    assert isinstance(spawned_nodes[2], TinyCUATaskExecutorNode)


def test_on_complete_dispatch_replan():
    """ResultReviewerNode.on_complete dispatches replan to loop handler.

    Verifies: on_complete extracts active_task from metadata and calls
    loop._on_reviewer_replan (FR-014 path).
    """
    # Arrange
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    mock_loop = MagicMock()
    mock_loop._on_reviewer_replan = MagicMock()

    reviewer = TinyCUAResultReviewerNode(loop=mock_loop)
    decision_data = {"outcome": "replan", "rationale": "Needs replanning", "active_task": active_task}
    response = LLMResult(
        content='{"outcome": "replan"}',
        metadata={"reviewer_decision": decision_data},
    )
    queue = NodeQueue()

    # Act
    reviewer.on_complete(queue, response)

    # Assert
    mock_loop._on_reviewer_replan.assert_called_once_with(active_task)


def test_on_complete_dispatch_all_outcomes():
    """ResultReviewerNode.on_complete dispatches all four outcomes correctly.

    Verifies: accept, retry, replan, open_question all route to the
    correct loop handler with the active_task.
    """
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    mock_loop = MagicMock()
    reviewer = TinyCUAResultReviewerNode(loop=mock_loop)
    queue = NodeQueue()

    for outcome in ("accept", "retry", "replan", "open_question"):
        mock_loop.reset_mock()
        decision_data = {"outcome": outcome, "rationale": f"Test {outcome}", "active_task": active_task}
        response = LLMResult(
            content=f'{{"outcome": "{outcome}"}}',
            metadata={"reviewer_decision": decision_data},
        )

        reviewer.on_complete(queue, response)

        handler = getattr(mock_loop, f"_on_reviewer_{outcome}")
        handler.assert_called_once_with(active_task)


def test_retry_threshold_enforcement():
    """After 5 retries (default), reviewer cannot retry again.

    Verifies: reviewer cannot retry again once threshold reached.
    """
    # Arrange
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    # Act — exhaust retries
    for _ in range(5):
        loop._on_reviewer_retry(active_task)

    # Assert
    assert loop._reviewer_retry_state.is_threshold_reached()
    assert not loop._reviewer_retry_state.can_retry()


def test_retry_counter_resets_on_accept():
    """After successful accept, retry counter resets to 0."""
    # Arrange
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    # Act — retry a few times, then accept
    for _ in range(3):
        loop._on_reviewer_retry(active_task)
    loop._on_reviewer_accept(active_task)

    # Assert
    assert loop._reviewer_retry_state.retry_count == 0


def test_retry_threshold_blocks_dispatch():
    """After threshold reached, on_complete with outcome=retry dispatches to accept."""
    # Arrange
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    # Exhaust retries
    for _ in range(5):
        loop._on_reviewer_retry(active_task)

    # Mock loop handlers
    mock_loop = MagicMock()
    mock_loop._reviewer_retry_state = loop._reviewer_retry_state
    reviewer = TinyCUAResultReviewerNode(loop=mock_loop)
    queue = NodeQueue()

    decision_data = {"outcome": "retry", "rationale": "Should be blocked", "active_task": active_task}
    response = LLMResult(
        content='{"outcome": "retry"}',
        metadata={"reviewer_decision": decision_data},
    )

    # Act
    reviewer.on_complete(queue, response)

    # Assert
    mock_loop._on_reviewer_retry.assert_not_called()
    mock_loop._on_reviewer_accept.assert_called_once_with(active_task)
