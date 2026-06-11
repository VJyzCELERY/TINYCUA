"""Integration tests for TinyCUAResultAggregationNode."""

from tinycua.config.types import LLMResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.result_aggregation import (
    AggregatedResult,
    TinyCUAResultAggregationNode,
)
from tinycua.loops.response_node import TinyCUAResponseNode
from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import Task, TaskResult


def _build_completed_root_task_tree():
    """Build a completed root task tree with TaskResult on at least one child."""
    return Task(
        task_id="root",
        title="Root",
        status="done",
        children=[
            Task(
                task_id="child_1",
                title="Child 1",
                status="done",
                result=TaskResult(
                    task_id="child_1",
                    summary="Done successfully",
                    execution_status="succeeded",
                ),
            ),
        ],
    )


def _build_session(task):
    """Build a minimal Session for ensure_session."""
    from tinycua.models.session import Session

    session = Session()
    session.task = task
    return session


def test_aggregation_produces_aggregated_result():
    """Given a completed root task tree where root task is done,
    When TinyCUAResultAggregationNode is invoked,
    Then it produces an AggregatedResult with task summaries and artifacts."""
    # Arrange — build a completed root task tree
    root_task = _build_completed_root_task_tree()
    node = TinyCUAResultAggregationNode()
    node.ensure_session(_build_session(root_task))

    # Act
    result = node._consolidate(list(node._traverse_bfs_right_to_left(root_task)))

    # Assert
    assert isinstance(result, AggregatedResult)
    assert result.root_task_id == root_task.task_id
    assert len(result.task_summaries) >= 1
    assert any("not_executed" in s or ":" in s for s in result.task_summaries)
    assert len(result.accepted_results) >= 1


def test_bfs_right_to_left_traversal():
    """Given a root task tree with nested accepted tasks at multiple depths,
    When the aggregation node traverses,
    Then it visits children right-to-left / most-recent-first."""
    # Arrange — build tree: root -> [child_1 (older), child_2 (newer)]
    # Tree: root -> child_1 -> grandchild_1
    #            -> child_2 -> grandchild_2
    root = Task(
        task_id="root",
        title="Root",
        children=[
            Task(
                task_id="child_1",
                title="Child 1 (older)",
                status="done",
                children=[Task(task_id="grandchild_1", title="GC1", status="done")],
            ),
            Task(
                task_id="child_2",
                title="Child 2 (newer)",
                status="done",
                children=[Task(task_id="grandchild_2", title="GC2", status="done")],
            ),
        ],
        status="done",
    )
    node = TinyCUAResultAggregationNode()

    # Act — traverse and collect task IDs in order visited
    visited_ids = [t.task_id for t in node._traverse_bfs_right_to_left(root)]

    # Assert — right-to-left BFS: child_2 before child_1
    # Level 0: root
    # Level 1: child_2, child_1 (right-to-left)
    # Level 2: grandchild_2, grandchild_1
    child_2_idx = visited_ids.index("child_2")
    child_1_idx = visited_ids.index("child_1")
    assert child_2_idx < child_1_idx, (
        f"child_2 (newer) should be visited before child_1 (older), "
        f"got child_2 at {child_2_idx}, child_1 at {child_1_idx}"
    )

    gc_2_idx = visited_ids.index("grandchild_2")
    gc_1_idx = visited_ids.index("grandchild_1")
    assert gc_2_idx < gc_1_idx, (
        f"grandchild_2 should be visited before grandchild_1, "
        f"got gc_2 at {gc_2_idx}, gc_1 at {gc_1_idx}"
    )


def test_early_termination():
    """Given sufficient response-ready context is found early,
    When the aggregation node inspects tasks,
    Then it may stop early without exhaustive BFS."""
    root = Task(
        task_id="root",
        title="Root",
        status="done",
        children=[
            Task(task_id="child_1", title="Child 1", status="done"),
            Task(task_id="child_2", title="Child 2", status="done"),
            Task(task_id="child_3", title="Child 3", status="done"),
        ],
    )
    # Threshold of 1 — stop after first node is inspected (root itself)
    node = TinyCUAResultAggregationNode()
    result = node._consolidate(
        list(node._traverse_bfs_right_to_left(root, max_inspected_tasks=1))
    )
    assert len(result.task_summaries) == 1  # Only root inspected, children skipped
    assert all(":" in s or "not_executed" in s for s in result.task_summaries)
    # Traversal stopped early (not exhaustive) — verified by exact count


def test_on_complete_advances_queue():
    """Given TinyCUAResultAggregationNode produces an AggregatedResult,
    When on_complete is called,
    Then the queue advances to the next node."""
    queue = NodeQueue(
        items=[
            TinyCUAResultAggregationNode(),
            TinyCUAResponseNode(),
        ]
    )
    response = LLMResult(
        content="",
        metadata={
            "aggregated_result": AggregatedResult(
                root_task_id="test",
                task_summaries=[],
                accepted_results=[],
                artifacts=[],
                final_context="",
                response_continuation="",
                metadata={},
            )
        },
    )

    current_before = queue.current
    node = queue.current
    node.on_complete(queue, response)

    assert queue.current is not None
    assert queue.current.node_id != current_before.node_id


def test_read_only_guarantee():
    """Given a completed task tree,
    When the aggregation node traverses,
    Then it does NOT mutate any task's status, result, or children."""
    child = Task(task_id="child", title="Child", status="done")
    root = Task(task_id="root", title="Root", children=[child], status="done")
    original_child_status = child.status
    original_child_result = child.result

    node = TinyCUAResultAggregationNode()
    list(node._traverse_bfs_right_to_left(root))  # Materialize the generator

    assert child.status == original_child_status
    assert child.result == original_child_result


def test_empty_task_tree():
    """Given a root task with no children,
    When the aggregation node is invoked,
    Then it produces an AggregatedResult from the single root task."""
    root = Task(task_id="root", title="Root only", status="done")
    node = TinyCUAResultAggregationNode()

    result = node._consolidate(list(node._traverse_bfs_right_to_left(root)))
    assert result.root_task_id == "root"
    assert len(result.task_summaries) == 1
    assert all(":" in s or "not_executed" in s for s in result.task_summaries)


def test_tasks_with_missing_results():
    """Given some tasks have no result (were never executed),
    When the aggregation node traverses,
    Then it records 'not_executed' status instead of failing."""
    child_executed = Task(
        task_id="executed",
        title="Executed",
        status="done",
        result=TaskResult(
            task_id="executed", summary="Done", execution_status="succeeded"
        ),
    )
    child_not_executed = Task(
        task_id="not_exec",
        title="Not Executed",
        status="pending",
    )
    root = Task(
        task_id="root",
        title="Root",
        children=[child_executed, child_not_executed],
        status="done",
    )

    node = TinyCUAResultAggregationNode()
    result = node._consolidate(list(node._traverse_bfs_right_to_left(root)))
    # Should not raise; not_executed tasks are skipped gracefully
    assert len(result.task_summaries) >= 1
    assert all(":" in s or "not_executed" in s for s in result.task_summaries)


def _build_loop_with_active_task() -> TinyCUALoop:
    """Build a TinyCUALoop with one active task for testing.

    Replicates the helper pattern from
    tests/integration/test_executor_reviewer_integration.py.
    """
    task = Task(
        task_id="test-1",
        title="Test Task",
        description="Test task",
        status="in_progress",
    )
    queue = NodeQueue()
    loop = TinyCUALoop(queue=queue)
    loop.root_task = task
    loop._active_task_id = "test-1"
    return loop


def test_on_reviewer_accept_returns_true_for_root():
    """Given a root task with all children done,
    When _on_reviewer_accept is called on the root task,
    Then it returns True (root task is done).

    Queue mutation is NOT the responsibility of _on_reviewer_accept —
    that happens in ResultReviewer.on_complete (see
    test_root_accept_routes_to_aggregation).
    """
    # Use the helper to set up a loop with an active task, then replace it
    # with a proper root + child tree
    loop = _build_loop_with_active_task()
    root = Task(
        task_id="root",
        title="Root",
        status="in_progress",
        children=[Task(task_id="child", title="Child", status="done")],
    )
    loop.root_task = root
    loop._active_task_id = "root"

    # Act
    is_root_done = loop._on_reviewer_accept(root)

    # Assert — root is done
    assert is_root_done is True


def test_root_accept_routes_to_aggregation():
    """Given a root task is accepted,
    When ResultReviewer.on_complete is called with outcome=accept,
    Then _on_reviewer_accept is called and _route_to_aggregation is invoked
    to mutate the queue with aggregation -> response nodes.

    Tests the full routing path via ResultReviewer.on_complete, not the
    low-level _on_reviewer_accept handler.
    """
    from unittest.mock import MagicMock

    # Build loop with active root task (all children done so root becomes
    # done when accepted)
    root = Task(
        task_id="root",
        title="Root",
        status="in_progress",
        children=[Task(task_id="child", title="Child", status="done")],
    )
    queue = NodeQueue()
    loop = TinyCUALoop(queue=queue)
    loop.root_task = root
    loop._active_task_id = "root"

    # Mock the loop so we can intercept _route_to_aggregation without
    # requiring TinyCUAResultAggregationNode or ResponseNode to exist yet
    mock_loop = MagicMock()
    # Wrap the real _on_reviewer_accept as a side effect so it runs but
    # we can verify it was called via the MagicMock
    real_on_reviewer_accept = loop._on_reviewer_accept
    mock_loop._on_reviewer_accept = MagicMock(side_effect=real_on_reviewer_accept)
    mock_loop._route_to_aggregation = MagicMock()
    mock_loop._reviewer_retry_state = loop._reviewer_retry_state

    reviewer = TinyCUAResultReviewerNode(loop=mock_loop)
    decision_data = {"outcome": "accept", "rationale": "Root complete"}
    response = LLMResult(
        content='{"outcome": "accept"}',
        metadata={"reviewer_decision": decision_data, "active_task": root},
    )

    # Act
    reviewer.on_complete(queue, response)

    # Assert — _on_reviewer_accept was called (handles task status changes)
    mock_loop._on_reviewer_accept.assert_called_once_with(root)
    # Assert — _route_to_aggregation was invoked (queue mutation: clear + spawn)
    mock_loop._route_to_aggregation.assert_called_once_with(queue)


def test_force_accept_on_threshold_routes_to_aggregation():
    """Given retry threshold is reached,
    When ResultReviewer.on_complete is called with outcome=retry,
    Then _on_reviewer_accept is called (force-accept) and _route_to_aggregation
    is invoked when root task is done."""
    from unittest.mock import MagicMock

    root = Task(
        task_id="root",
        title="Root",
        status="in_progress",
        children=[Task(task_id="child", title="Child", status="done")],
    )
    queue = NodeQueue()
    loop = TinyCUALoop(queue=queue)
    loop.root_task = root
    loop._active_task_id = "root"
    # Exhaust retry threshold
    loop._reviewer_retry_state.retry_count = loop._reviewer_retry_state.threshold

    mock_loop = MagicMock()
    real_on_reviewer_accept = loop._on_reviewer_accept
    mock_loop._on_reviewer_accept = MagicMock(side_effect=real_on_reviewer_accept)
    mock_loop._route_to_aggregation = MagicMock()
    mock_loop._reviewer_retry_state = loop._reviewer_retry_state

    reviewer = TinyCUAResultReviewerNode(loop=mock_loop)
    decision_data = {"outcome": "retry", "rationale": "Threshold reached"}
    response = LLMResult(
        content='{"outcome": "retry"}',
        metadata={"reviewer_decision": decision_data, "active_task": root},
    )

    reviewer.on_complete(queue, response)

    mock_loop._on_reviewer_accept.assert_called_once_with(root)
    mock_loop._route_to_aggregation.assert_called_once_with(queue)
