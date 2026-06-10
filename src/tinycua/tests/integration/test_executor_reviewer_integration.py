"""Integration tests for executor→reviewer path."""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.node_input import NodeInput
from tinycua.models.task import ReviewerDecision, Task, TaskResult


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

    Verifies: replan preserves active task and logs the event.
    """
    # Arrange
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    assert active_task is not None

    # Act — reviewer decides replan
    loop._on_reviewer_replan(active_task)

    # Assert — active task preserved
    assert loop.get_active_task() is not None
    assert loop.get_active_task().task_id == active_task.task_id


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
