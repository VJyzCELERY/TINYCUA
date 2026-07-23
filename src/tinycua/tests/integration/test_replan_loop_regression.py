"""Integration regression test for the replan loop (Milestone 8, FR-049/050).

Simulates the full replan loop cycle that experiment-2 exhibited: a task
that the reviewer keeps sending back. Verifies the loop is bounded by
``max_replans`` and records failure at the cap instead of looping forever.

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
        ctrl.schedule_after_review(queue)
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

    return executor_runs, 0, "max_cycles_exceeded"


class TestReplanLoopBounded:
    """The replan loop is bounded by max_replans (FR-049/050)."""

    def test_loop_terminates_within_max_replans_plus_one(self):
        """With max_replans=3, the loop fails honestly (not loops forever)."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt 0"))
        ctrl = WorkerRuntimeController(store, replan_threshold=5, max_replans=3)

        executor_runs, replan_count, final_decision = _simulate_replan_cycle(
            store, child.task_id, ctrl
        )

        # The loop must terminate (not max_cycles_exceeded).
        assert final_decision != "max_cycles_exceeded", (
            f"Loop did not terminate: {executor_runs} executor runs, "
            f"final={final_decision}"
        )
        assert final_decision == "failed", f"Expected failure, got {final_decision}"
        # The loop is bounded: replan_count <= max_replans (3).
        # Executor runs are bounded by max_replans × (threshold + 1) = 3 × 6 = 18.
        # The key assertion is replan_count <= max_replans (the loop is capped).
        assert replan_count <= 3, f"Exceeded max_replans: {replan_count}"
        assert executor_runs <= 18, f"Too many executor runs: {executor_runs}"

    def test_loop_with_high_effort_allows_more_replans(self):
        """max_replans=6 (high effort) allows more replans before failure."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt 0"))
        ctrl = WorkerRuntimeController(store, replan_threshold=5, max_replans=6)

        executor_runs, replan_count, final_decision = _simulate_replan_cycle(
            store, child.task_id, ctrl
        )

        assert final_decision == "failed"
        assert replan_count <= 6
        # More replans allowed than the medium=3 case.
        assert replan_count > 3, f"High effort should allow >3 replans, got {replan_count}"

    def test_loop_with_zero_max_replans_fails_immediately(self):
        """max_replans=0 (none effort) fails on the first threshold crossing."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt 0"))
        ctrl = WorkerRuntimeController(store, replan_threshold=5, max_replans=0)

        executor_runs, replan_count, final_decision = _simulate_replan_cycle(
            store, child.task_id, ctrl
        )

        # With max_replans=0, the first threshold crossing (5 rejections)
        # should fail immediately — no replans, no extra executor runs.
        assert final_decision == "failed"
        assert replan_count == 0
        # Only the initial result; no executor re-runs from replans.
        assert executor_runs == 0

    def test_failure_rationale_records_budget(self):
        """The exhaustion failure records effort and cap for observability."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="attempt 0"))
        ctrl = WorkerRuntimeController(store, replan_threshold=5, max_replans=2)

        executor_runs, replan_count, final_decision = _simulate_replan_cycle(
            store, child.task_id, ctrl
        )

        assert final_decision == "failed"
        task = store.get_task(child.task_id)
        assert task.result is not None
        assert "replan budget exhausted" in task.result.content.lower()
        assert "cap=2" in task.result.content


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
