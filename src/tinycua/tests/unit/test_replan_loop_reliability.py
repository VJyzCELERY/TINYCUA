"""Unit tests for replan loop reliability (Milestone 8, FR-049/FR-050).

Covers:
- FR-049: ``consecutive_failures`` resets when ``schedule_replan`` inserts a
  ``replan_boundary`` entry into ``reviewer_decisions``.
- FR-050: ``max_replans`` caps replans per task (effort-profiled); at cap the
  next send-back records failure and queues a terminal response.
"""

from __future__ import annotations

from tinycua.config.session_config import SessionConfig
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.worker_runtime import WorkerRuntimeController
from tinycua.models.session import Session
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store_with_active_child() -> tuple[TaskStateStore, str]:
    """Create a store with a root + an in-progress child that has a result."""
    store = TaskStateStore()
    root = store.create_task("Root")
    child = store.create_task("Child", parent_id=root.task_id)
    store.transition(child.task_id, TaskStatus.IN_PROGRESS)
    store.record_result(child.task_id, TaskResult(content="attempt"))
    return store, child.task_id


def _reject(store: TaskStateStore, task_id: str, n: int = 1) -> None:
    """Record ``n`` needs_revision decisions on ``task_id``."""
    for _ in range(n):
        store.record_reviewer_decision(task_id, ReviewerDecision.NEEDS_REVISION)


# ---------------------------------------------------------------------------
# FR-049 — replan_boundary resets consecutive_failures
# ---------------------------------------------------------------------------


class TestReplanBoundaryResetsConsecutiveFailures:
    """schedule_replan inserts a replan_boundary that resets the derived counter."""

    def test_boundary_entry_is_recorded_on_replan(self):
        store, child_id = _make_store_with_active_child()
        _reject(store, child_id, 5)
        queue = NodeQueue()

        WorkerRuntimeController(store, max_replans=3).schedule_after_review(
            queue, reviewed_task_id=child_id, decision="needs_revision"
        )

        # The last entry should be a replan_boundary (inserted by schedule_replan).
        child = store.get_task(child_id)
        decisions = child.reviewer_decisions
        assert decisions[-1]["decision"] == "replan_boundary"

    def test_consecutive_failures_resets_after_replan(self):
        store, child_id = _make_store_with_active_child()
        _reject(store, child_id, 5)
        queue = NodeQueue()

        ctrl = WorkerRuntimeController(store, max_replans=3)
        ctrl.schedule_after_review(
            queue, reviewed_task_id=child_id, decision="needs_revision"
        )

        # After the boundary, consecutive_failures should be 0 (reset).
        child = store.get_task(child_id)
        assert child.consecutive_failures == 0

    def test_boundary_does_not_count_as_failure(self):
        """failure_count (total) should NOT count replan_boundary entries."""
        store, child_id = _make_store_with_active_child()
        _reject(store, child_id, 5)
        queue = NodeQueue()

        WorkerRuntimeController(store, max_replans=3).schedule_after_review(
            queue, reviewed_task_id=child_id, decision="needs_revision"
        )

        child = store.get_task(child_id)
        # 5 needs_revision + 1 replan_boundary → failure_count is 5 (boundary excluded)
        assert child.failure_count == 5

    def test_replan_does_not_reset_total_audit_trail(self):
        """The full reviewer_decisions audit trail is preserved across replans."""
        store, child_id = _make_store_with_active_child()
        _reject(store, child_id, 5)
        queue = NodeQueue()

        WorkerRuntimeController(store, max_replans=3).schedule_after_review(
            queue, reviewed_task_id=child_id, decision="needs_revision"
        )

        child = store.get_task(child_id)
        # 5 needs_revision + 1 replan_boundary = 6 entries total
        assert len(child.reviewer_decisions) == 6


# ---------------------------------------------------------------------------
# FR-050 — max_replans cap records terminal failure
# ---------------------------------------------------------------------------


class TestUnboundedReplans:
    """Replanning continues regardless of the configured diagnostic value."""

    def test_previous_cap_replans_instead_of_failing(self):
        store, child_id = _make_store_with_active_child()
        _reject(store, child_id, 5)
        # Insert 3 replan_boundary entries manually to simulate 3 prior replans.
        child = store.get_task(child_id)
        for _ in range(3):
            child.reviewer_decisions.append(
                {"decision": "replan_boundary", "rationale": "prior replan", "metadata": {}}
            )
        # Now reject once more so the latest decision is needs_revision.
        store.record_reviewer_decision(child_id, ReviewerDecision.NEEDS_REVISION)
        queue = NodeQueue()

        WorkerRuntimeController(store, max_replans=3).schedule_after_review(
            queue, reviewed_task_id=child_id, decision="needs_revision"
        )

        child = store.get_task(child_id)
        assert child.status == TaskStatus.IN_PROGRESS
        assert [node.node_id for node in queue.items] == [
            "task_executor",
            "result_reviewer",
        ]

    def test_previous_cap_never_queues_response(self):
        store, child_id = _make_store_with_active_child()
        _reject(store, child_id, 5)
        child = store.get_task(child_id)
        for _ in range(3):
            child.reviewer_decisions.append(
                {"decision": "replan_boundary", "rationale": "prior replan", "metadata": {}}
            )
        store.record_reviewer_decision(child_id, ReviewerDecision.NEEDS_REVISION)
        queue = NodeQueue()

        WorkerRuntimeController(store, max_replans=3).schedule_after_review(
            queue, reviewed_task_id=child_id, decision="needs_revision"
        )

        ids = [n.node_id for n in queue.items]
        assert ids == ["task_executor", "result_reviewer"]

    def test_below_cap_still_replans(self):
        store, child_id = _make_store_with_active_child()
        _reject(store, child_id, 5)
        # 1 prior replan boundary → below cap of 3. The boundary resets
        # consecutive_failures, so we need 5 more rejections to re-trigger.
        child = store.get_task(child_id)
        child.reviewer_decisions.append(
            {"decision": "replan_boundary", "rationale": "prior replan", "metadata": {}}
        )
        _reject(store, child_id, 5)
        queue = NodeQueue()

        WorkerRuntimeController(store, max_replans=3).schedule_after_review(
            queue, reviewed_task_id=child_id, decision="needs_revision"
        )

        # Should replan (not force-approve): replan_count=1 < cap=3.
        child = store.get_task(child_id)
        assert child.reviewer_decisions[-1]["decision"] == "replan_boundary"
        ids = [n.node_id for n in queue.items]
        assert "task_analyzer" in ids


# ---------------------------------------------------------------------------
# FR-050 — effort-profiled max_replans default mapping
# ---------------------------------------------------------------------------


class TestMaxReplansEffortMapping:
    """max_replans defaults from worker_effort when not explicitly set."""

    def test_medium_effort_defaults_to_3(self):
        session = Session(session_config=SessionConfig(worker_effort="medium"))
        assert session.session_config.max_replans == 3

    def test_high_effort_defaults_to_6(self):
        session = Session(session_config=SessionConfig(worker_effort="high"))
        assert session.session_config.max_replans == 6

    def test_low_effort_defaults_to_1(self):
        session = Session(session_config=SessionConfig(worker_effort="low"))
        assert session.session_config.max_replans == 1

    def test_none_effort_defaults_to_0(self):
        session = Session(session_config=SessionConfig(worker_effort="none"))
        assert session.session_config.max_replans == 0

    def test_explicit_max_replans_overrides_effort(self):
        session = Session(
            session_config=SessionConfig(worker_effort="medium", max_replans=10)
        )
        assert session.session_config.max_replans == 10


# ---------------------------------------------------------------------------
# FR-050 — WorkerRuntimeController picks up max_replans from session
# ---------------------------------------------------------------------------


class TestControllerMaxReplansFromSession:
    """WorkerRuntimeController resolves max_replans from the session config."""

    def test_controller_uses_session_max_replans(self):
        session = Session(session_config=SessionConfig(worker_effort="low"))
        ctrl = WorkerRuntimeController(store=session.task_store, session=session)
        assert ctrl.max_replans == 1

    def test_controller_explicit_max_replans_overrides_session(self):
        session = Session(session_config=SessionConfig(worker_effort="low"))
        ctrl = WorkerRuntimeController(
            store=session.task_store, session=session, max_replans=5
        )
        assert ctrl.max_replans == 5

    def test_controller_defaults_to_medium_when_no_session(self):
        ctrl = WorkerRuntimeController(store=TaskStateStore())
        assert ctrl.max_replans == 3
