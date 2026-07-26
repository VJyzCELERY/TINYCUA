"""Integration regression test for the replan loop (Milestone 8, FR-049/050).

Simulates the full replan loop cycle that experiment-2 exhibited: a task
that the reviewer keeps sending back. Verifies that ``max_replans`` remains
diagnostic and never fabricates terminal failure for unfinished work.

This is a focused integration test on ``WorkerRuntimeController`` — it does
not run the full TinyCUALoop with an LLM (that would require a live model).
The unit tests in ``test_replan_loop_reliability.py`` cover the individual
mechanics; this test covers the end-to-end loop behavior across multiple
replan cycles.
"""

from __future__ import annotations

from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.worker_runtime import WorkerRuntimeController
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


def _simulate_replan_cycle(
    store: TaskStateStore,
    task_id: str,
    ctrl: WorkerRuntimeController,
    max_cycles: int = 50,
) -> tuple[int, int, str]:
    """Simulate the reject→replan→reject loop until failure or max_cycles.

    Returns (executor_runs, replan_count, final_decision).
    """
    executor_runs = 0
    cycles = 0
    while cycles < max_cycles:
        cycles += 1
        task = store.get_task(task_id)
        if task is None or task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            # Task already terminated — return its final status.
            decisions = task.reviewer_decisions if task else []
            final = task.status.value if task else "completed"
            return executor_runs, sum(
                1 for d in decisions if d.get("decision") == "replan_boundary"
            ), final
        # The reviewer rejects the current result.
        store.record_reviewer_decision(task_id, ReviewerDecision.NEEDS_REVISION)
        queue = NodeQueue()
        ctrl.schedule_after_review(
            queue, reviewed_task_id=task_id, decision="needs_revision"
        )
        ids = [n.node_id for n in queue.items]

        # Check if the task exhausted its budget and failed.
        task = store.get_task(task_id)
        if task is not None and task.status == TaskStatus.FAILED:
            decisions = task.reviewer_decisions
            final = task.status.value
            return executor_runs, sum(
                1 for d in decisions if d.get("decision") == "replan_boundary"
            ), final

        if "task_executor" in ids or "task_analyzer" in ids:
            # Executor will run (either retry or after replan).
            executor_runs += 1
            store.record_result(task_id, TaskResult(content=f"attempt {executor_runs}"))
            continue

        # No executor/analyzer scheduled — unexpected.
        decisions = task.reviewer_decisions if task else []
        final = decisions[-1]["decision"] if decisions else "none"
        return executor_runs, sum(
            1 for d in decisions if d.get("decision") == "replan_boundary"
        ), final

    task = store.get_task(task_id)
    return executor_runs, sum(
        1 for d in task.reviewer_decisions if d.get("decision") == "replan_boundary"
    ), "max_cycles_exceeded"


class TestReplanLoopUnbounded:
    """The diagnostic max_replans value does not terminate unfinished work."""

    def test_loop_ignores_diagnostic_max_replans(self):
        """A reviewer that keeps requesting revision remains active."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt 0"))
        ctrl = WorkerRuntimeController(store, replan_threshold=5, max_replans=3)

        executor_runs, replan_count, final_decision = _simulate_replan_cycle(
            store, child.task_id, ctrl
        )

        assert final_decision == "max_cycles_exceeded"
        assert replan_count > 3
        assert executor_runs == 50

    def test_high_effort_value_also_remains_diagnostic(self):
        """Changing the diagnostic value does not create a terminal edge."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt 0"))
        ctrl = WorkerRuntimeController(store, replan_threshold=5, max_replans=6)

        executor_runs, replan_count, final_decision = _simulate_replan_cycle(
            store, child.task_id, ctrl
        )

        assert final_decision == "max_cycles_exceeded"
        assert replan_count > 6
        assert executor_runs == 50

    def test_zero_max_replans_does_not_fail_unfinished_work(self):
        """A zero diagnostic value still leaves recovery available."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt 0"))
        ctrl = WorkerRuntimeController(store, replan_threshold=5, max_replans=0)

        executor_runs, replan_count, final_decision = _simulate_replan_cycle(
            store, child.task_id, ctrl
        )

        assert final_decision == "max_cycles_exceeded"
        assert replan_count > 0
        assert executor_runs == 50

    def test_diagnostic_budget_does_not_replace_executor_result(self):
        """Recovery never fabricates a budget-exhaustion task result."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt 0"))
        ctrl = WorkerRuntimeController(store, replan_threshold=5, max_replans=2)

        _executor_runs, _replan_count, final_decision = _simulate_replan_cycle(
            store, child.task_id, ctrl
        )

        assert final_decision == "max_cycles_exceeded"
        task = store.get_task(child.task_id)
        assert task.result is not None
        assert task.result.content.startswith("attempt ")
        assert "replan budget exhausted" not in task.result.content.lower()


def test_impossible_leaf_is_disposed_once_and_never_dispatched_again() -> None:
    """Experiment 2-shaped replan advances after impossible evidence."""
    store = TaskStateStore()
    root = store.create_task("Write report")
    impossible = store.create_task("Fetch missing benchmark", parent_id=root.task_id)
    remaining = store.create_task("Write report from available evidence", parent_id=root.task_id)
    dispatched: list[str] = []

    store.cancel_task(impossible.task_id, "selected source contains no benchmark data")
    controller = WorkerRuntimeController(store)
    queue = NodeQueue()
    controller.schedule_next(queue)
    dispatched.append(store.active_task_id or "")

    assert impossible.status == TaskStatus.CANCELLED
    assert remaining.task_id in dispatched
    assert impossible.task_id not in dispatched
