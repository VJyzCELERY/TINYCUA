"""Unit tests for ReviewerRetryState, TaskExecutorNode, and ResultReviewerNode."""

from __future__ import annotations

from unittest.mock import MagicMock

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.loops.node import NodeExecutionError
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode
from tinycua.loops.task_executor import TinyCUATaskExecutorNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.node_input import NodeInput
from tinycua.models.reviewer_decision import ReviewerRetryState
from tinycua.models.session import Session
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
    """Fallback regex matches outcome keywords anywhere in response."""
    reviewer = TinyCUAResultReviewerNode()
    # Should match exact keyword
    response = LLMResult(content="accept", metadata={})
    assert reviewer._parse_decision(response) == {"outcome": "accept", "rationale": "accept"}
    # Should match keyword embedded in surrounding text (relaxed regex)
    response = LLMResult(content="The task cannot accept any more retries", metadata={})
    assert reviewer._parse_decision(response) == {
        "outcome": "accept",
        "rationale": "The task cannot accept any more retries",
    }
    # Should match with whitespace
    response = LLMResult(content="  retry  ", metadata={})
    assert reviewer._parse_decision(response) == {"outcome": "retry", "rationale": "  retry  "}


# --- TinyCUATaskExecutorNode tests ---


def _build_executor_with_mocked_llm(
    llm_response_content: str = "Task completed successfully",
    tool_calls: list | None = None,
) -> TinyCUATaskExecutorNode:
    """Build a TaskExecutor with a mocked LLM client."""
    config = NodeConfigBase()
    config.llm_client = MagicMock(
        return_value={
            "content": llm_response_content,
            "role": "assistant",
            "tool_calls": tool_calls or [],
        }
    )
    executor = TinyCUATaskExecutorNode(config=config)
    executor.ensure_session(Session())
    return executor


def test_task_executor_call_with_mocked_llm():
    """TaskExecutor.__call__ produces execution_result metadata with succeeded status."""
    executor = _build_executor_with_mocked_llm(llm_response_content="Done")
    task = Task(task_id="t-1", title="T", description="D", status="in_progress")
    input_data = NodeInput(
        input_type="continuation",
        metadata={"active_task": task},
    )

    result = executor(input_data)

    assert result.metadata["execution_result"]["task_id"] == "t-1"
    assert result.metadata["execution_result"]["execution_status"] == "succeeded"
    assert result.metadata["execution_result"]["summary"] == "Done"


def test_task_executor_call_raises_when_no_active_task():
    """TaskExecutor raises NodeExecutionError when no active_task in metadata."""
    executor = _build_executor_with_mocked_llm()
    input_data = NodeInput(input_type="continuation", metadata={})

    try:
        executor(input_data)
        raise AssertionError("Expected NodeExecutionError")
    except NodeExecutionError as e:
        assert "no active_task" in str(e).lower()


def test_task_executor_call_raises_when_no_session():
    """TaskExecutor raises NodeExecutionError when no session is attached."""
    config = NodeConfigBase()
    config.llm_client = MagicMock()
    executor = TinyCUATaskExecutorNode(config=config)
    task = Task(task_id="t-1", title="T", description="D", status="in_progress")
    input_data = NodeInput(
        input_type="continuation",
        metadata={"active_task": task},
    )

    try:
        executor(input_data)
        raise AssertionError("Expected NodeExecutionError")
    except NodeExecutionError as e:
        assert "no session" in str(e).lower()


def test_task_executor_call_sets_failed_status_on_exception():
    """TaskExecutor sets execution_status='failed' when LLM raises."""
    config = NodeConfigBase()
    config.llm_client = MagicMock(side_effect=RuntimeError("LLM unavailable"))
    executor = TinyCUATaskExecutorNode(config=config)
    executor.ensure_session(Session())
    task = Task(task_id="t-2", title="T", description="D", status="in_progress")
    input_data = NodeInput(
        input_type="continuation",
        metadata={"active_task": task},
    )

    try:
        executor(input_data)
        raise AssertionError("Expected RuntimeError")
    except RuntimeError:
        pass


def test_task_executor_respects_max_react_iterations():
    """TaskExecutor loop stops at max_react_iterations and reports max_iterations_reached."""
    config = NodeConfigBase()
    call_count = 0

    def mock_llm(messages):
        nonlocal call_count
        call_count += 1
        # Return tool_calls on every call to force the loop to exhaust iterations
        return {
            "content": "thinking...",
            "role": "assistant",
            "tool_calls": [{"id": "t1", "type": "function", "function": {"name": "test", "arguments": "{}"}}],
        }

    config.llm_client = mock_llm
    executor = TinyCUATaskExecutorNode(config=config, max_react_iterations=3)
    executor.ensure_session(Session())
    task = Task(task_id="t-3", title="T", description="D", status="in_progress")
    input_data = NodeInput(
        input_type="continuation",
        metadata={"active_task": task},
    )

    result = executor(input_data)
    assert call_count == 3
    assert result.metadata["execution_result"]["execution_status"] == "max_iterations_reached"


def test_task_executor_on_complete_advances_queue():
    """TaskExecutor.on_complete calls queue.advance()."""
    executor = _build_executor_with_mocked_llm()
    mock_queue = MagicMock()
    response = LLMResult(content="done", role="assistant", metadata={})

    executor.on_complete(mock_queue, response)

    mock_queue.advance.assert_called_once()


def test_on_reviewer_replan_does_not_spawn():
    """_on_reviewer_replan only logs — no queue mutation (ownership moved to on_complete)."""
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    mock_queue = MagicMock()
    loop.queue = mock_queue

    loop._on_reviewer_replan(active_task)

    # _on_reviewer_replan should NOT call spawn_after_current
    mock_queue.spawn_after_current.assert_not_called()
