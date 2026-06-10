"""Integration tests for executor→reviewer path."""

from __future__ import annotations

from unittest.mock import MagicMock

from tinycua.config.types import LLMResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import Task


def _build_loop_with_active_task() -> TinyCUALoop:
    """Build a TinyCUALoop with one active task for testing."""
    task = Task(task_id="test-1", title="Test Task", description="Test task", status="in_progress")
    queue = NodeQueue()
    loop = TinyCUALoop(queue=queue)
    loop.root_task = task
    loop._active_task_id = "test-1"
    return loop


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
    """Executor → reviewer → replan path.

    Verifies: replan preserves active task. Queue mutation (spawn) is owned
    by ResultReviewer.on_complete, not _on_reviewer_replan (design.md:397-408).
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

    # Assert — _on_reviewer_replan does NOT spawn (ownership moved to on_complete)
    mock_queue.spawn_after_current.assert_not_called()


def test_on_complete_dispatch_replan():
    """ResultReviewerNode.on_complete dispatches replan with queue mutations.

    Verifies: on_complete calls loop._on_reviewer_replan, clears queue
    after current, spawns replan nodes, and ensures terminal node.
    """
    # Arrange
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    mock_loop = MagicMock()
    mock_loop._on_reviewer_replan = MagicMock()
    mock_loop.session_config = MagicMock()
    mock_loop.default_terminal_node = MagicMock()

    reviewer = TinyCUAResultReviewerNode(loop=mock_loop)
    decision_data = {"outcome": "replan", "rationale": "Needs replanning", "active_task": active_task}
    response = LLMResult(
        content='{"outcome": "replan"}',
        metadata={"reviewer_decision": decision_data},
    )
    queue = NodeQueue()
    # Add a placeholder current node so spawn_after_current works
    from tinycua.loops.response_node import ResponseNode
    queue.items.append(ResponseNode())

    # Act
    reviewer.on_complete(queue, response)

    # Assert — loop handler called
    mock_loop._on_reviewer_replan.assert_called_once_with(active_task)

    # Assert — queue mutations happened (clear_after_current + spawn + ensure_terminal)
    # After clear_after_current, only current node remains; after spawn, 3 more added
    assert len(queue.items) >= 3  # current + assessor + analyzer + executor


def test_on_complete_replan_mutates_queue_regardless_of_session_config():
    """Replan mutates queue even when session_config has no llm_client.

    Verifies: on_complete calls _on_reviewer_replan AND mutates the queue
    (clear_after_current + spawn + ensure_terminal) regardless of session_config.
    """
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    mock_loop = MagicMock()
    mock_loop._on_reviewer_replan = MagicMock()
    mock_loop.session_config = None
    mock_loop.default_terminal_node = MagicMock()

    reviewer = TinyCUAResultReviewerNode(loop=mock_loop)
    decision_data = {"outcome": "replan", "rationale": "Needs replanning", "active_task": active_task}
    response = LLMResult(
        content='{"outcome": "replan"}',
        metadata={"reviewer_decision": decision_data},
    )
    queue = NodeQueue()
    from tinycua.loops.response_node import ResponseNode
    queue.items.append(ResponseNode())

    reviewer.on_complete(queue, response)

    mock_loop._on_reviewer_replan.assert_called_once_with(active_task)
    # Queue SHOULD be mutated — replan always proceeds
    assert len(queue.items) >= 3  # current + assessor + analyzer + executor


def test_on_complete_dispatch_all_outcomes():
    """ResultReviewerNode.on_complete dispatches all four outcomes correctly.

    Verifies: accept, retry, replan, open_question all route to the
    correct loop handler with the active_task.
    """
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    mock_loop = MagicMock()
    mock_loop.session_config = MagicMock()
    mock_loop.default_terminal_node = MagicMock()
    reviewer = TinyCUAResultReviewerNode(loop=mock_loop)

    for outcome in ("accept", "retry", "replan", "open_question"):
        mock_loop.reset_mock()
        decision_data = {"outcome": outcome, "rationale": f"Test {outcome}", "active_task": active_task}
        response = LLMResult(
            content=f'{{"outcome": "{outcome}"}}',
            metadata={"reviewer_decision": decision_data},
        )

        # replan requires a non-empty queue; use mock for that case
        if outcome == "replan":
            queue = MagicMock()
            reviewer.on_complete(queue, response)
            queue.clear_after_current.assert_called()
            queue.ensure_terminal.assert_called()
        else:
            queue = NodeQueue()
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
