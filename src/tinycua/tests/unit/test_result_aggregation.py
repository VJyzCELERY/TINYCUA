"""Unit tests for TinyCUAResultAggregationNode and AggregatedResult."""

from typing import Any

import pytest

from tinycua.config.types import LLMResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.result_aggregation import (
    AggregatedResult,
    TinyCUAResultAggregationNode,
)
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import Task, TaskResult


# =========================================================================
# AggregatedResult construction tests
# =========================================================================


class TestAggregatedResult:
    """Unit tests for AggregatedResult dataclass."""

    def test_all_fields_populated(self):
        """Given all fields are provided,
        When an AggregatedResult is constructed,
        Then all fields have the expected values."""
        result = AggregatedResult(
            root_task_id="root-1",
            task_summaries=["Root: done", "Child: completed"],
            accepted_results=[
                TaskResult(task_id="child", summary="OK", execution_status="succeeded")
            ],
            artifacts=[{"file": "output.txt"}],
            final_context="Root: done\nChild: completed",
            response_continuation="No further action needed",
            metadata={"depth": 2, "count": 3},
        )
        assert result.root_task_id == "root-1"
        assert len(result.task_summaries) == 2
        assert len(result.accepted_results) == 1
        assert len(result.artifacts) == 1
        assert result.final_context == "Root: done\nChild: completed"
        assert result.response_continuation == "No further action needed"
        assert result.metadata == {"depth": 2, "count": 3}

    def test_empty_lists_and_strings(self):
        """Given no optional fields are provided,
        When an AggregatedResult is constructed with only required fields,
        Then optional fields default to empty lists/strings."""
        result = AggregatedResult(root_task_id="root-1")
        assert result.root_task_id == "root-1"
        assert result.task_summaries == []
        assert result.accepted_results == []
        assert result.artifacts == []
        assert result.final_context == ""
        assert result.response_continuation == ""
        assert result.metadata == {}

    def test_type_hints(self):
        """Given an AggregatedResult with various types,
        When fields are accessed,
        Then the types match expectations."""
        result = AggregatedResult(
            root_task_id="test",
            task_summaries=["a", "b"],
            accepted_results=[
                TaskResult(task_id="t1", summary="s1", execution_status="succeeded")
            ],
            artifacts=[{"key": "val"}],
            final_context="ctx",
            response_continuation="cont",
            metadata={"key": 42},
        )
        assert isinstance(result.root_task_id, str)
        assert isinstance(result.task_summaries, list)
        assert isinstance(result.accepted_results, list)
        assert isinstance(result.artifacts, list)
        assert isinstance(result.final_context, str)
        assert isinstance(result.response_continuation, str)
        assert isinstance(result.metadata, dict)
        # Check inner types
        assert all(isinstance(s, str) for s in result.task_summaries)
        assert all(isinstance(r, TaskResult) for r in result.accepted_results)
        assert all(isinstance(a, dict) for a in result.artifacts)


# =========================================================================
# _traverse_bfs_right_to_left tests
# =========================================================================


class TestTraverseBFSRightToLeft:
    """Unit tests for _traverse_bfs_right_to_left generator."""

    def test_multi_level_tree_right_to_left_order(self):
        """Given a multi-level task tree,
        When traversing right-to-left BFS,
        Then tasks are visited in the correct order: root, then children
        right-to-left, then grandchildren right-to-left."""
        # Tree:
        #       root
        #      /    \
        #   child2  child1  (children order: left-to-right as declared)
        #    /  \     /  \
        #  gc4 gc3  gc2 gc1
        gc1 = Task(task_id="gc1", title="GC1", status="done")
        gc2 = Task(task_id="gc2", title="GC2", status="done")
        gc3 = Task(task_id="gc3", title="GC3", status="done")
        gc4 = Task(task_id="gc4", title="GC4", status="done")

        child1 = Task(
            task_id="child1", title="Child 1", children=[gc1, gc2], status="done"
        )
        child2 = Task(
            task_id="child2", title="Child 2", children=[gc3, gc4], status="done"
        )
        root = Task(
            task_id="root",
            title="Root",
            children=[child1, child2],
            status="done",
        )

        node = TinyCUAResultAggregationNode()
        visited_ids = [t.task_id for t in node._traverse_bfs_right_to_left(root)]

        # BFS right-to-left:
        # Level 0: root
        # Level 1: child2, child1 (right-to-left)
        # Level 2: gc4, gc3, gc2, gc1 (right-to-left)
        expected_order = ["root", "child2", "child1", "gc4", "gc3", "gc2", "gc1"]
        assert visited_ids == expected_order, (
            f"Expected {expected_order}, got {visited_ids}"
        )

    def test_early_termination_with_max_inspected(self):
        """Given a max_inspected_tasks threshold,
        When traversing,
        Then traversal stops after that many tasks are yielded."""
        # Tree with 5 tasks total
        child1 = Task(task_id="c1", title="C1", status="done")
        child2 = Task(task_id="c2", title="C2", status="done")
        child3 = Task(task_id="c3", title="C3", status="done")
        root = Task(
            task_id="root",
            title="Root",
            children=[child1, child2, child3],
            status="done",
        )

        node = TinyCUAResultAggregationNode()
        visited_ids = [
            t.task_id
            for t in node._traverse_bfs_right_to_left(root, max_inspected_tasks=3)
        ]

        # Should yield root + 2 children (3 total)
        assert len(visited_ids) == 3
        assert visited_ids[0] == "root"
        # c3 and c2 should be visited (right-to-left), c1 skipped
        assert "c3" in visited_ids
        assert "c2" in visited_ids
        assert "c1" not in visited_ids

    def test_early_termination_with_negative_max(self):
        """Given a negative max_inspected_tasks,
        When traversing,
        Then no tasks are yielded (negative threshold stops immediately)."""
        child = Task(task_id="c1", title="C1", status="done")
        root = Task(task_id="root", title="Root", children=[child], status="done")

        node = TinyCUAResultAggregationNode()
        visited_ids = [
            t.task_id
            for t in node._traverse_bfs_right_to_left(root, max_inspected_tasks=-1)
        ]

        assert len(visited_ids) == 0

    def test_early_termination_with_zero_max(self):
        """Given max_inspected_tasks=0,
        When traversing,
        Then no tasks are yielded (zero threshold stops immediately)."""
        child = Task(task_id="c1", title="C1", status="done")
        root = Task(task_id="root", title="Root", children=[child], status="done")

        node = TinyCUAResultAggregationNode()
        visited_ids = [
            t.task_id
            for t in node._traverse_bfs_right_to_left(root, max_inspected_tasks=0)
        ]

        assert len(visited_ids) == 0

    def test_empty_children(self):
        """Given a leaf task with no children (empty list),
        When traversing,
        Then only the root task is yielded."""
        leaf = Task(task_id="leaf", title="Leaf", status="done", children=[])
        node = TinyCUAResultAggregationNode()
        visited_ids = [t.task_id for t in node._traverse_bfs_right_to_left(leaf)]
        assert visited_ids == ["leaf"]

    def test_no_children_none(self):
        """Given a task with children=None,
        When traversing,
        Then only the root task is yielded (None treated as empty)."""
        task = Task(task_id="only", title="Only", status="done")
        # Note: Task dataclass field default is [], so children will be []
        # This tests the case where children is the default empty list
        node = TinyCUAResultAggregationNode()
        visited_ids = [t.task_id for t in node._traverse_bfs_right_to_left(task)]
        assert visited_ids == ["only"]

    def test_single_task_root_only(self):
        """Given a single root task with no children,
        When traversing,
        Then only the root task is yielded."""
        root = Task(task_id="root", title="Root", status="done")
        node = TinyCUAResultAggregationNode()
        visited_ids = [t.task_id for t in node._traverse_bfs_right_to_left(root)]
        assert visited_ids == ["root"]

    def test_read_only_guarantee(self):
        """Given a task tree,
        When traversing,
        Then no task is mutated."""
        child = Task(task_id="child", title="Child", status="done")
        root = Task(task_id="root", title="Root", children=[child], status="done")
        original_child_status = child.status
        original_child_result = child.result
        original_root_status = root.status

        node = TinyCUAResultAggregationNode()
        list(node._traverse_bfs_right_to_left(root))

        assert child.status == original_child_status
        assert child.result == original_child_result
        assert root.status == original_root_status

    def test_context_sufficient_fn_callback(self):
        """Given a context_sufficient_fn callback,
        When it returns True for a specific task,
        Then traversal stops early after that task is yielded."""
        # Build children in reverse order so the one we want to stop at
        # appears first in right-to-left traversal.
        # Children in declaration: [c1, c2]
        # Right-to-left BFS visits: c2 first, then c1
        # We stop when we see c1, so visited = [root, c2, c1]
        child1 = Task(task_id="c1", title="C1", status="done")
        child2 = Task(task_id="c2", title="C2", status="done")
        root = Task(
            task_id="root",
            title="Root",
            children=[child1, child2],
            status="done",
        )

        def is_sufficient(task: Task, partial: AggregatedResult) -> bool:
            return task.task_id == "c1"

        node = TinyCUAResultAggregationNode()
        visited_ids = [
            t.task_id
            for t in node._traverse_bfs_right_to_left(root, context_sufficient_fn=is_sufficient)
        ]

        # Right-to-left BFS: root -> c2 -> c1 (stop at c1)
        assert visited_ids == ["root", "c2", "c1"]
        # c1 triggered the stop, so we should have exactly 3 tasks visited
        assert len(visited_ids) == 3

    def test_context_sufficient_fn_none(self):
        """Given context_sufficient_fn=None,
        When traversing,
        Then all tasks are yielded (no early termination)."""
        child1 = Task(task_id="c1", title="C1", status="done")
        child2 = Task(task_id="c2", title="C2", status="done")
        root = Task(
            task_id="root",
            title="Root",
            children=[child1, child2],
            status="done",
        )

        node = TinyCUAResultAggregationNode()
        visited_ids = [
            t.task_id
            for t in node._traverse_bfs_right_to_left(root, context_sufficient_fn=None)
        ]

        assert len(visited_ids) == 3
        assert "c2" in visited_ids  # All tasks visited


# =========================================================================
# _consolidate tests
# =========================================================================


class TestConsolidate:
    """Unit tests for _consolidate method."""

    def test_with_accepted_results(self):
        """Given traversal results with TaskResults,
        When consolidated,
        Then accepted_results and task_summaries are populated."""
        task_with_result = Task(
            task_id="t1",
            title="Task 1",
            status="done",
            result=TaskResult(
                task_id="t1",
                summary="Completed OK",
                execution_status="succeeded",
            ),
        )
        root = Task(
            task_id="root",
            title="Root",
            status="done",
            children=[task_with_result],
        )

        node = TinyCUAResultAggregationNode()
        traversal = list(node._traverse_bfs_right_to_left(root))
        result = node._consolidate(traversal)

        assert result.root_task_id == "root"
        assert len(result.task_summaries) == 2  # root + child
        assert len(result.accepted_results) == 1
        assert result.accepted_results[0].task_id == "t1"
        assert result.accepted_results[0].summary == "Completed OK"

    def test_with_artifacts(self):
        """Given tasks with artifacts in their results,
        When consolidated,
        Then artifacts are collected."""
        task_with_artifact = Task(
            task_id="t1",
            title="Task 1",
            status="done",
            result=TaskResult(
                task_id="t1",
                summary="Has artifacts",
                execution_status="succeeded",
                artifacts=[{"file": "output.txt"}, {"file": "log.txt"}],
            ),
        )
        root = Task(
            task_id="root",
            title="Root",
            status="done",
            children=[task_with_artifact],
        )

        node = TinyCUAResultAggregationNode()
        traversal = list(node._traverse_bfs_right_to_left(root))
        result = node._consolidate(traversal)

        assert len(result.artifacts) == 2
        assert {"file": "output.txt"} in result.artifacts
        assert {"file": "log.txt"} in result.artifacts

    def test_with_reviewer_decisions(self):
        """Given tasks with reviewer decisions,
        When consolidated,
        Then accepted_results include the decision metadata."""
        from tinycua.models.task import ReviewerDecision

        task_accepted = Task(
            task_id="t1",
            title="Task 1",
            status="done",
            result=TaskResult(
                task_id="t1",
                summary="Accepted",
                execution_status="succeeded",
                reviewer_decision=ReviewerDecision(outcome="accept"),
            ),
        )
        root = Task(
            task_id="root",
            title="Root",
            status="done",
            children=[task_accepted],
        )

        node = TinyCUAResultAggregationNode()
        traversal = list(node._traverse_bfs_right_to_left(root))
        result = node._consolidate(traversal)

        assert len(result.accepted_results) == 1
        assert result.accepted_results[0].reviewer_decision is not None
        assert result.accepted_results[0].reviewer_decision.outcome == "accept"

    def test_with_missing_results(self):
        """Given tasks with no result (not executed),
        When consolidated,
        Then they are recorded as 'not_executed' without failing."""
        task_no_result = Task(
            task_id="t1",
            title="Task 1",
            status="pending",
        )
        root = Task(
            task_id="root",
            title="Root",
            status="done",
            children=[task_no_result],
        )

        node = TinyCUAResultAggregationNode()
        traversal = list(node._traverse_bfs_right_to_left(root))
        result = node._consolidate(traversal)

        assert len(result.task_summaries) == 2
        # Task with no result should have "not_executed" in its summary
        t1_summary = [s for s in result.task_summaries if "Task 1" in s]
        assert len(t1_summary) >= 1
        assert "not_executed" in t1_summary[0].lower()

    def test_empty_traversal_list(self):
        """Given an empty traversal list,
        When consolidated,
        Then an AggregatedResult with only root_task_id is returned."""
        node = TinyCUAResultAggregationNode()
        result = node._consolidate([])

        assert result.root_task_id == ""
        assert result.task_summaries == []
        assert result.accepted_results == []
        assert result.artifacts == []

    def test_final_context_built_from_summaries(self):
        """Given tasks with summaries,
        When consolidated,
        Then final_context joins task summaries."""
        task1 = Task(
            task_id="t1",
            title="Task 1",
            status="done",
            result=TaskResult(
                task_id="t1",
                summary="First task",
                execution_status="succeeded",
            ),
        )
        root = Task(
            task_id="root",
            title="Root Task",
            status="done",
            children=[task1],
        )

        node = TinyCUAResultAggregationNode()
        traversal = list(node._traverse_bfs_right_to_left(root))
        result = node._consolidate(traversal)

        # final_context should contain both summaries
        assert len(result.final_context) > 0
        assert "Root Task" in result.final_context
        assert "Task 1" in result.final_context


# =========================================================================
# TinyCUAResultAggregationNode.__call__ tests
# =========================================================================


class TestAggregationNodeCall:
    """Unit tests for TinyCUAResultAggregationNode.__call__."""

    def test_guard_raises_when_session_not_attached(self):
        """Given no session is attached,
        When __call__ is invoked,
        Then it raises NodeExecutionError."""
        from tinycua.loops.node import NodeExecutionError

        node = TinyCUAResultAggregationNode()
        with pytest.raises(NodeExecutionError, match="no session"):
            node.__call__({})  # type: ignore[arg-type]

    def test_guard_raises_when_root_task_not_done(self):
        """Given session is attached but root task is not done,
        When __call__ is invoked,
        Then it raises NodeExecutionError."""
        from tinycua.loops.node import NodeExecutionError
        from tinycua.models.session import Session

        node = TinyCUAResultAggregationNode()
        session = Session()
        session.task = Task(task_id="root", title="Root", status="in_progress")
        node.ensure_session(session)

        with pytest.raises(NodeExecutionError, match="root task is not done"):
            node.__call__({})  # type: ignore[arg-type]

    def test_guard_raises_when_no_task_in_session(self):
        """Given session has no task set,
        When __call__ is invoked,
        Then it raises NodeExecutionError."""
        from tinycua.loops.node import NodeExecutionError
        from tinycua.models.session import Session

        node = TinyCUAResultAggregationNode()
        session = Session()
        node.ensure_session(session)

        with pytest.raises(NodeExecutionError, match="no root task"):
            node.__call__({})  # type: ignore[arg-type]

    def test_returns_llm_result_with_aggregated_result(self):
        """Given a completed root task tree,
        When __call__ is invoked,
        Then it returns an LLMResult with AggregatedResult in metadata."""
        from tinycua.models.session import Session

        root = Task(
            task_id="root",
            title="Root",
            status="done",
            children=[
                Task(
                    task_id="child",
                    title="Child",
                    status="done",
                    result=TaskResult(
                        task_id="child",
                        summary="Done",
                        execution_status="succeeded",
                    ),
                )
            ],
        )
        node = TinyCUAResultAggregationNode()
        session = Session()
        session.task = root
        node.ensure_session(session)

        result = node.__call__({})  # type: ignore[arg-type]

        assert isinstance(result, LLMResult)
        assert "aggregated_result" in result.metadata
        agg_result = result.metadata["aggregated_result"]
        assert isinstance(agg_result, AggregatedResult)
        assert agg_result.root_task_id == "root"
        assert len(agg_result.task_summaries) >= 1


# =========================================================================
# on_complete tests
# =========================================================================


class TestOnComplete:
    """Unit tests for on_complete method."""

    def test_queue_advances(self):
        """Given a queue with aggregation node followed by response node,
        When on_complete is called,
        Then the queue advances to the next node."""
        queue = NodeQueue(
            items=[
                TinyCUAResultAggregationNode(),
                ResponseNode(),
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

    def test_logs_completion(self, caplog: pytest.LogCaptureFixture):
        """Given on_complete is called,
        When it completes,
        Then a completion message is logged."""
        import logging

        caplog.set_level(logging.INFO)

        node = TinyCUAResultAggregationNode()
        queue = NodeQueue(items=[node, ResponseNode()])
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

        node.on_complete(queue, response)

        assert any(
            "result_aggregation" in record.message and "complete" in record.message
            for record in caplog.records
        )


# =========================================================================
# Loop wiring unit tests
# =========================================================================


class TestLoopWiring:
    """Unit tests for loop wiring (route_to_aggregation)."""

    def test_route_to_aggregation_spawns_nodes(self):
        """Given _route_to_aggregation is called,
        When the queue has a current node,
        Then it spawns ResultAggregationNode and ResponseNode after current."""
        queue = NodeQueue(
            items=[
                TinyCUAResultReviewerNode(),
            ]
        )
        loop = TinyCUALoop(queue=queue)

        # Act
        loop._route_to_aggregation(queue)

        # Assert — aggregation + response nodes were spawned after current
        assert len(queue.items) >= 3  # reviewer + aggregation + response
        spawned_ids = [item.node_id for item in queue.items]
        assert "result_aggregation" in spawned_ids
        assert "response" in spawned_ids
        # ResponseNode should be terminal
        assert queue.items[-1].is_terminal

    def test_on_reviewer_accept_returns_true_for_root(self):
        """Given a root task with all children done,
        When _on_reviewer_accept is called,
        Then it returns True (root done)."""
        loop = TinyCUALoop()
        root = Task(
            task_id="root",
            title="Root",
            status="in_progress",
            children=[Task(task_id="child", title="Child", status="done")],
        )
        loop.root_task = root
        loop._active_task_id = "root"

        is_root_done = loop._on_reviewer_accept(root)

        assert is_root_done is True
        assert root.status == "done"

    def test_on_reviewer_accept_returns_false_for_non_root(self):
        """Given a non-root task is accepted but siblings still pending,
        When _on_reviewer_accept is called,
        Then it returns False (root not done because siblings remain)."""
        loop = TinyCUALoop()
        child1 = Task(task_id="child1", title="Child 1", status="in_progress")
        child2 = Task(task_id="child2", title="Child 2", status="pending")
        root = Task(
            task_id="root",
            title="Root",
            status="in_progress",
            children=[child1, child2],
        )
        loop.root_task = root
        loop._active_task_id = "child1"

        is_root_done = loop._on_reviewer_accept(child1)

        assert is_root_done is False
        assert child1.status == "done"
        assert child2.status == "pending"
        assert root.status == "in_progress"  # Root not done yet (child2 still pending)

    def test_non_root_accept_path_unchanged(self):
        """Given a non-root task is accepted but siblings remain,
        When _on_reviewer_accept is called,
        Then the non-root accept behavior is preserved (parent chain walk but
        root is not done, so _route_to_aggregation is NOT called)."""
        from unittest.mock import MagicMock

        loop = TinyCUALoop()
        child1 = Task(task_id="child1", title="Child 1", status="in_progress")
        child2 = Task(task_id="child2", title="Child 2", status="pending")
        root = Task(
            task_id="root",
            title="Root",
            status="in_progress",
            children=[child1, child2],
        )
        loop.root_task = root
        loop._active_task_id = "child1"

        # Mock _route_to_aggregation to verify it's NOT called
        loop._route_to_aggregation = MagicMock()  # type: ignore[method-assign]

        is_root_done = loop._on_reviewer_accept(child1)

        assert is_root_done is False
        loop._route_to_aggregation.assert_not_called()  # type: ignore[attr-defined]
