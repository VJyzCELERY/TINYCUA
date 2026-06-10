"""Unit tests for ReviewerRetryState, TaskExecutorNode, and ResultReviewerNode."""

from __future__ import annotations


from tinycua.config.types import LLMResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.reviewer_decision import ReviewerRetryState
from tinycua.models.task import Task


# --- ReviewerRetryState tests ---


def test_reviewer_retry_state_defaults():
    """ReviewerRetryState initializes with zero count and threshold 5."""
    state = ReviewerRetryState()
    assert state.retry_count == 0
    assert state.threshold == 5


def test_reviewer_retry_state_custom_threshold():
    """ReviewerRetryState accepts a custom threshold."""
    state = ReviewerRetryState(threshold=3)
    assert state.threshold == 3
    assert state.retry_count == 0


def test_reviewer_retry_state_increment():
    """ReviewerRetryState.increment() returns new count."""
    state = ReviewerRetryState()
    result = state.increment()
    assert result == 1
    assert state.retry_count == 1


def test_reviewer_retry_state_increment_multiple():
    """ReviewerRetryState.increment() accumulates across calls."""
    state = ReviewerRetryState()
    state.increment()
    state.increment()
    state.increment()
    assert state.retry_count == 3


def test_reviewer_retry_state_reset():
    """ReviewerRetryState.reset() clears retry count to 0."""
    state = ReviewerRetryState()
    state.increment()
    state.increment()
    state.reset()
    assert state.retry_count == 0


def test_reviewer_retry_state_can_retry():
    """ReviewerRetryState.can_retry() returns True below threshold."""
    state = ReviewerRetryState(threshold=3)
    state.increment()
    assert state.can_retry()


def test_reviewer_retry_state_can_retry_at_threshold():
    """ReviewerRetryState.can_retry() returns False at threshold."""
    state = ReviewerRetryState(threshold=3)
    state.increment()
    state.increment()
    state.increment()
    assert not state.can_retry()


def test_reviewer_retry_state_is_threshold_reached():
    """ReviewerRetryState.is_threshold_reached() returns True at threshold."""
    state = ReviewerRetryState(threshold=3)
    state.increment()
    state.increment()
    state.increment()
    assert state.is_threshold_reached()


def test_reviewer_retry_state_is_threshold_not_reached():
    """ReviewerRetryState.is_threshold_reached() returns False below threshold."""
    state = ReviewerRetryState(threshold=3)
    state.increment()
    assert not state.is_threshold_reached()


def test_reviewer_retry_state_threshold_one():
    """ReviewerRetryState with threshold=1 fails on first retry."""
    state = ReviewerRetryState(threshold=1)
    state.increment()
    assert state.is_threshold_reached()
    assert not state.can_retry()


# --- TinyCUALoop reviewer handlers tests ---


def _build_loop_with_active_task() -> TinyCUALoop:
    """Build a TinyCUALoop with one active task for testing."""
    task = Task(task_id="test-1", title="Test Task", description="Test task", status="in_progress")
    queue = NodeQueue()
    loop = TinyCUALoop(queue=queue)
    loop.root_task = task
    loop._active_task_id = "test-1"
    return loop


def test_loop_has_reviewer_retry_state():
    """TinyCUALoop initializes ReviewerRetryState in __init__."""
    loop = TinyCUALoop()
    assert hasattr(loop, "_reviewer_retry_state")
    assert isinstance(loop._reviewer_retry_state, ReviewerRetryState)


def test_on_reviewer_retry_increments_count():
    """_on_reviewer_retry() increments the retry counter."""
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    loop._on_reviewer_retry(active_task)
    assert loop._reviewer_retry_state.retry_count == 1

    loop._on_reviewer_retry(active_task)
    assert loop._reviewer_retry_state.retry_count == 2


def test_on_reviewer_retry_preserves_task():
    """_on_reviewer_retry() preserves the active task."""
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    loop._on_reviewer_retry(active_task)
    assert loop.get_active_task() is not None
    assert loop.get_active_task().task_id == active_task.task_id


def test_on_reviewer_replan_preserves_task():
    """_on_reviewer_replan() preserves the active task."""
    from unittest.mock import MagicMock

    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    mock_queue = MagicMock()
    loop.queue = mock_queue

    loop._on_reviewer_replan(active_task)
    assert loop.get_active_task() is not None
    assert loop.get_active_task().task_id == active_task.task_id


def test_on_reviewer_open_question_preserves_task():
    """_on_reviewer_open_question() preserves the active task."""
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    loop._on_reviewer_open_question(active_task)
    assert loop.get_active_task() is not None
    assert loop.get_active_task().task_id == active_task.task_id


def test_on_reviewer_accept_resets_retry_counter():
    """_on_reviewer_accept() resets the retry counter."""
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    # Build up some retries
    for _ in range(3):
        loop._on_reviewer_retry(active_task)
    assert loop._reviewer_retry_state.retry_count == 3

    # Accept should reset
    loop._on_reviewer_accept(active_task)
    assert loop._reviewer_retry_state.retry_count == 0


def test_parse_decision_word_boundary():
    """Fallback regex matches only exact keywords, not substrings."""
    reviewer = TinyCUAResultReviewerNode()
    # Should match exact keyword
    response = LLMResult(content="accept", metadata={})
    assert reviewer._parse_decision(response) == {"outcome": "accept", "rationale": "accept"}
    # Should NOT match substring
    response = LLMResult(content="The task cannot accept any more retries", metadata={})
    # Should fall back to retry (default)
    assert reviewer._parse_decision(response)["outcome"] == "retry"
    # Should match with whitespace
    response = LLMResult(content="  retry  ", metadata={})
    assert reviewer._parse_decision(response) == {"outcome": "retry", "rationale": "  retry  "}
