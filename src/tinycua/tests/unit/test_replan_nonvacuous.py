"""Unit tests for non-vacuous replan (Milestone 8, FR-051).

Covers: when the analyzer confirms ``plan_unchanged`` via ``task_update``
metadata, the replan skips re-queueing the executor — the plan did not
change, so re-execution would duplicate work. Only the reviewer is
re-queued against the existing result.
"""

from __future__ import annotations

from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.task_nodes import (
    TinyCUAResultReviewerNode,
    TinyCUATaskAnalyzerNode,
    TinyCUATaskExecutorNode,
)
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


class TestPlanUnchangedSkipsExecutor:
    """Analyzer on_complete removes the queued executor when plan_unchanged is set."""

    def test_plan_unchanged_removes_executor_from_queue(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt"))
        # Simulate the analyzer setting plan_unchanged via task_update metadata.
        child.metadata["plan_unchanged"] = True

        # Queue state as it would be right after schedule_replan:
        # [task_assessor, task_analyzer, task_executor, result_reviewer]
        # The analyzer is the "current" node (index 0 after assessor done).
        from tinycua.config.node_config import create_node_config

        analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer", mode="local_replan"),
        )
        analyzer.session = _StubSession(store)  # noqa: SLF001
        queue = NodeQueue()
        queue.items.extend(
            [
                analyzer,
                TinyCUATaskExecutorNode(
                    node_id="task_executor",
                    config=create_node_config("task_executor"),
                ),
                TinyCUAResultReviewerNode(
                    node_id="result_reviewer",
                    config=create_node_config("result_reviewer"),
                ),
            ]
        )

        # Fire on_complete — the analyzer should remove the executor.
        analyzer.on_complete(queue, _StubResponse())

        ids = [n.node_id for n in queue.items]
        # Executor should be removed; reviewer should remain.
        assert "task_executor" not in ids
        assert "result_reviewer" in ids

    def test_plan_unchanged_false_keeps_executor(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt"))
        # plan_unchanged NOT set (or False)
        child.metadata["plan_unchanged"] = False

        from tinycua.config.node_config import create_node_config

        analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer", mode="local_replan"),
        )
        analyzer.session = _StubSession(store)  # noqa: SLF001
        queue = NodeQueue()
        queue.items.extend(
            [
                analyzer,
                TinyCUATaskExecutorNode(
                    node_id="task_executor",
                    config=create_node_config("task_executor"),
                ),
                TinyCUAResultReviewerNode(
                    node_id="result_reviewer",
                    config=create_node_config("result_reviewer"),
                ),
            ]
        )

        analyzer.on_complete(queue, _StubResponse())

        ids = [n.node_id for n in queue.items]
        # Executor stays — the plan changed (or was not confirmed unchanged).
        assert "task_executor" in ids

    def test_plan_unchanged_not_set_keeps_executor(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt"))
        # plan_unchanged key absent

        from tinycua.config.node_config import create_node_config

        analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer", mode="local_replan"),
        )
        analyzer.session = _StubSession(store)  # noqa: SLF001
        queue = NodeQueue()
        queue.items.extend(
            [
                analyzer,
                TinyCUATaskExecutorNode(
                    node_id="task_executor",
                    config=create_node_config("task_executor"),
                ),
                TinyCUAResultReviewerNode(
                    node_id="result_reviewer",
                    config=create_node_config("result_reviewer"),
                ),
            ]
        )

        analyzer.on_complete(queue, _StubResponse())

        ids = [n.node_id for n in queue.items]
        assert "task_executor" in ids


class TestPlanUnchangedLogsSkip:
    """The skip is observable via logging."""

    def test_skip_logged(self, caplog):
        import logging

        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt"))
        child.metadata["plan_unchanged"] = True

        from tinycua.config.node_config import create_node_config

        analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer", mode="local_replan"),
        )
        analyzer.session = _StubSession(store)  # noqa: SLF001
        queue = NodeQueue()
        queue.items.extend(
            [
                analyzer,
                TinyCUATaskExecutorNode(
                    node_id="task_executor",
                    config=create_node_config("task_executor"),
                ),
                TinyCUAResultReviewerNode(
                    node_id="result_reviewer",
                    config=create_node_config("result_reviewer"),
                ),
            ]
        )

        with caplog.at_level(logging.INFO):
            analyzer.on_complete(queue, _StubResponse())

        assert any("plan_unchanged" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubSession:
    """Minimal session stub for analyzer on_complete."""

    def __init__(self, store: TaskStateStore) -> None:
        self.task_store = store
        self.session_config = None


class _StubResponse:
    """Minimal response stub for on_complete."""

    content = "analyzer done"
    route_label = ""
    tool_calls: list = []