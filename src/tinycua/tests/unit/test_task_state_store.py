"""Task tree state contracts for the finalized runtime."""

from __future__ import annotations

import pytest

from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


def test_task_store_advances_after_reviewer_approval() -> None:
    """Executor result alone does not advance; reviewer approval does."""
    store = TaskStateStore()
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    second = store.create_task("Second", parent_id=root.task_id)

    assert store.active_task_id == first.task_id
    assert store.get_active_task() is first

    store.record_result(first.task_id, TaskResult(content="done"))
    assert first.status == TaskStatus.IN_PROGRESS
    assert store.active_task_id == first.task_id

    store.record_reviewer_decision(first.task_id, ReviewerDecision.APPROVED)

    assert store.active_task_id == second.task_id
    assert store.get_active_task() is second


def test_approved_result_does_not_propagate_context_to_next_sibling() -> None:
    """Reviewer approval keeps result context on the reviewed task."""
    store = TaskStateStore()
    root = store.create_task("Build app")
    scaffold = store.create_task("Create project scaffold", parent_id=root.task_id)
    module = store.create_task("Create module x", parent_id=root.task_id)

    store.record_result(
        scaffold.task_id,
        TaskResult(content="Created backend/app.py and frontend/index.html."),
    )
    store.record_reviewer_decision(scaffold.task_id, ReviewerDecision.APPROVED)

    assert scaffold.status == TaskStatus.COMPLETED
    assert module.metadata == {}


@pytest.mark.parametrize(
    "result",
    [
        None,
        TaskResult(content="failed", success=False),
        TaskResult(content="   "),
        TaskResult(content="generated", metadata={"auto_generated": True}),
    ],
)
def test_approval_without_successful_executor_report_leaves_task_in_progress(
    result: TaskResult | None,
) -> None:
    """Invalid approval cannot mutate review, task, parent, or sibling state."""
    store = TaskStateStore()
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    second = store.create_task("Second", parent_id=root.task_id)

    if result is not None:
        store.record_result(first.task_id, result)
    with pytest.raises(
        ValueError, match="requires a successful non-empty executor report"
    ):
        store.record_reviewer_decision(first.task_id, ReviewerDecision.APPROVED)

    assert first.status == TaskStatus.IN_PROGRESS
    assert first.result is result
    assert first.reviewer_decisions == []
    assert root.status == TaskStatus.PENDING
    assert second.status == TaskStatus.PENDING
    assert "context" not in second.metadata
    assert store.active_task_id == first.task_id
    assert store.get_active_task() is first
    assert store.all_done() is False


def test_failed_leaf_can_be_retried_and_completed() -> None:
    """A failed leaf reopens when a new executor report is recorded."""
    store = TaskStateStore()
    task = store.create_task("Retry me")

    store.record_result(task.task_id, TaskResult(content="failed", success=False))
    with pytest.raises(
        ValueError, match="requires a successful non-empty executor report"
    ):
        store.record_reviewer_decision(task.task_id, ReviewerDecision.APPROVED)
    assert task.status == TaskStatus.IN_PROGRESS

    store.record_result(task.task_id, TaskResult(content="fixed", success=True))
    store.record_reviewer_decision(task.task_id, ReviewerDecision.APPROVED)

    assert task.status == TaskStatus.COMPLETED
    assert store.active_task_id is None
    assert store.all_done() is True


def test_decompose_existing_parent_is_idempotent() -> None:
    """Reanalysis can append missing work without replacing prior children."""
    store = TaskStateStore()
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)

    child_ids = store.decompose_task(root.task_id, ["Second"])

    assert child_ids == [first.task_id, store.tasks[root.task_id].children[1]]
    assert [store.tasks[task_id].title for task_id in child_ids] == ["First", "Second"]


def test_task_store_validates_status_transitions_and_records_reviewer_decisions() -> (
    None
):
    """Invalid lifecycle transitions fail instead of silently mutating state."""
    store = TaskStateStore()
    task = store.create_task("Write report")

    with pytest.raises(ValueError, match="Invalid task transition"):
        store.transition(task.task_id, TaskStatus.COMPLETED)

    store.transition(task.task_id, TaskStatus.IN_PROGRESS)
    store.record_reviewer_decision(
        task.task_id,
        ReviewerDecision.NEEDS_REVISION,
        rationale="Missing evidence",
    )

    task_snapshot = store.snapshot()["tasks"][task.task_id]
    assert task.status == TaskStatus.IN_PROGRESS
    assert task_snapshot["reviewer_decisions"][-1]["decision"] == "needs_revision"
    assert task_snapshot["reviewer_decisions"][-1]["rationale"] == "Missing evidence"


def test_update_task_invalidates_render_and_records_auditable_event() -> None:
    """Store-owned edits immediately update rendering and snapshots."""
    store = TaskStateStore()
    task = store.create_task("Stale title")
    before = store.version
    assert "Stale title" in store.render_markdown()

    store.update_task(
        task.task_id, title="Corrected title", metadata={"source": "review"}
    )

    assert store.version > before
    assert "Corrected title" in store.render_markdown()
    assert store.snapshot()["transition_log"][-1]["action"] == "update_task"
    assert task.metadata["source"] == "review"


def test_cancel_and_supersede_terminal_tasks_advance_selection_and_preserve_lineage() -> (
    None
):
    """Disposed leaves remain auditable but cannot be scheduled again."""
    store = TaskStateStore()
    root = store.create_task("Root")
    impossible = store.create_task("Impossible", parent_id=root.task_id)
    remaining = store.create_task("Remaining", parent_id=root.task_id)

    request = store.request_task_cancellation(
        impossible.task_id, "source has no benchmark data"
    )
    store.assess_task_cancellation(
        request["request_id"], approved=True, rationale="The task is unnecessary."
    )
    assert impossible.status == TaskStatus.CANCELLED
    assert store.active_task_id == remaining.task_id

    replacement = store.supersede_task(
        remaining.task_id, "Replacement", "use available data"
    )
    assert remaining.status == TaskStatus.SUPERSEDED
    assert replacement.parent_id == root.task_id
    assert replacement.metadata["supersedes"] == remaining.task_id
    assert remaining.metadata["superseded_by"] == replacement.task_id
    assert store.active_task_id == replacement.task_id


def test_tree_validation_rejects_duplicate_links_before_mutation() -> None:
    """Malformed retained trees cannot be mutated further."""
    store = TaskStateStore()
    root = store.create_task("Root")
    child = store.create_task("Child", parent_id=root.task_id)
    root.children.append(child.task_id)

    with pytest.raises(ValueError, match="duplicate"):
        store.update_task(child.task_id, title="Never applied")

    assert child.title == "Child"


def test_acceptance_clauses_are_advisory_context() -> None:
    """Acceptance clauses remain root context without gating task completion."""
    store = TaskStateStore()
    root = store.create_task(
        "Root",
        acceptance_clauses=["CLI exits zero", "UI renders the result"],
    )
    first, second = store.decompose_task(
        root.task_id,
        ["Run CLI", "Check UI"],
    )

    assert root.metadata["acceptance_clauses"] == [
        {"id": "acceptance-1", "text": "CLI exits zero"},
        {"id": "acceptance-2", "text": "UI renders the result"},
    ]
    store.record_result(first, TaskResult(content="source inspected", metadata={}))
    store.record_reviewer_decision(first, ReviewerDecision.APPROVED)
    store.record_result(second, TaskResult(content="UI inspected", metadata={}))
    store.record_reviewer_decision(second, ReviewerDecision.APPROVED)

    store.record_result(root.task_id, TaskResult(content="verified root"))
    store.record_reviewer_decision(root.task_id, ReviewerDecision.APPROVED)

    assert root.status == TaskStatus.COMPLETED


def test_root_decomposition_does_not_assign_acceptance_ownership() -> None:
    """Decomposition stays independent from advisory acceptance context."""
    store = TaskStateStore()
    root = store.create_task(
        "Root",
        acceptance_clauses=["CLI exits zero", "UI renders the result"],
    )

    first = store.decompose_task(
        root.task_id,
        ["Run CLI"],
    )
    second = store.decompose_task(
        root.task_id,
        ["Check UI"],
    )

    assert store.get_task(first[0]).metadata == {}
    assert store.get_task(second[-1]).metadata == {}


def test_decomposition_rejects_duplicate_sibling_titles() -> None:
    """Repeated analyzer calls cannot append equivalent direct child work."""
    store = TaskStateStore()
    root = store.create_task("Root")
    store.decompose_task(root.task_id, ["Research sources"])

    with pytest.raises(ValueError, match="duplicate"):
        store.decompose_task(root.task_id, ["  research   SOURCES  "])

    assert len(root.children) == 1

    with pytest.raises(ValueError, match="duplicate"):
        store.decompose_task(root.task_id, ["New task", "Research sources"])

    assert len(root.children) == 1


def test_decomposition_preserves_child_descriptions_and_rejects_no_op() -> None:
    """Structured decomposition keeps context and cannot silently do nothing."""
    store = TaskStateStore()
    root = store.create_task("Root")

    child_ids = store.decompose_task(
        root.task_id,
        [{"title": "Inspect API", "description": "Confirm the response contract."}],
    )

    child = store.get_task(child_ids[0])
    assert child.title == "Inspect API"
    assert child.description == "Confirm the response contract."
    with pytest.raises(ValueError, match="valid subtask"):
        store.decompose_task(root.task_id, [])
    with pytest.raises(ValueError, match="valid subtask"):
        store.decompose_task(root.task_id, [{"description": "Missing title"}])
    with pytest.raises(ValueError, match="valid subtask"):
        store.decompose_task(root.task_id, [{"title": None}])


def test_only_first_in_progress_leaf_remains_active() -> None:
    """Conflicting planning updates retain the first executable task only."""
    store = TaskStateStore()
    root = store.create_task("Root")
    first, second = store.decompose_task(root.task_id, ["First", "Second"])

    store.update_task(first, status=TaskStatus.IN_PROGRESS)
    store.update_task(second, status=TaskStatus.IN_PROGRESS)

    assert store.get_task(first).status is TaskStatus.IN_PROGRESS
    assert store.get_task(second).status is TaskStatus.PENDING
    assert store.active_task_id == first


def test_reviewer_decision_is_replaceable_until_committed() -> None:
    """Only termination commits the final staged reviewer decision."""
    store = TaskStateStore()
    task = store.create_task("Review me")
    store.record_result(task.task_id, TaskResult(content="evidence"))

    store.stage_reviewer_decision(task.task_id, ReviewerDecision.APPROVED)
    store.stage_reviewer_decision(task.task_id, ReviewerDecision.NEEDS_REVISION)

    assert task.status == TaskStatus.IN_PROGRESS
    assert task.reviewer_decisions == []
    assert store.commit_staged_reviewer_decision(task.task_id).reviewer_decisions == [
        {
            "event_id": "review-1",
            "review_summary": "needs_revision",
            "decision": "needs_revision",
            "rationale": "",
            "new_findings": [],
            "finding_updates": [],
            "metadata": {"context_updates": []},
        }
    ]


def test_staged_approval_ignores_advisory_acceptance_clauses() -> None:
    """A review report can approve without machine-readable clause evidence."""
    store = TaskStateStore()
    task = store.create_task("Review me", acceptance_clauses=["verify behavior"])
    store.record_result(task.task_id, TaskResult(content="evidence"))
    store.stage_reviewer_decision(
        task.task_id,
        ReviewerDecision.APPROVED,
        rationale="The result satisfies the requested behavior.",
    )

    store.commit_staged_reviewer_decision(task.task_id)

    assert task.status is TaskStatus.COMPLETED
    assert task.reviewer_decisions[-1]["rationale"] == (
        "The result satisfies the requested behavior."
    )


def test_result_metadata_does_not_gate_approval() -> None:
    """Reviewer decisions depend on the report, not structured proof metadata."""
    store = TaskStateStore()
    root = store.create_task("Root", acceptance_clauses=["verify behavior"])
    child = store.create_task("Child", parent_id=root.task_id)
    store.record_result(
        child.task_id,
        TaskResult(
            content="done",
            metadata={"notes": "free-form execution details"},
        ),
    )

    store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)

    assert child.status is TaskStatus.COMPLETED


def test_postponement_progresses_monotonically_and_revisit_resumes_work() -> None:
    """Deferred work advances through sibling and final drains exactly once."""
    store = TaskStateStore()
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    second = store.create_task("Second", parent_id=root.task_id)

    store.record_result(first.task_id, TaskResult(content="blocked", success=False))
    store.record_reviewer_decision(
        first.task_id, "postpone_siblings", rationale="try sibling"
    )

    assert first.status is TaskStatus.POSTPONED
    assert store.active_task_id == second.task_id
    with pytest.raises(ValueError, match="postpone_siblings"):
        store.record_reviewer_decision(first.task_id, "postpone_siblings")

    store.record_result(
        second.task_id, TaskResult(content="blocked too", success=False)
    )
    store.record_reviewer_decision(
        second.task_id, "postpone_siblings", rationale="drain"
    )

    assert store.active_task_id == first.task_id
    store.record_result(
        first.task_id, TaskResult(content="still blocked", success=False)
    )
    assert first.status is TaskStatus.IN_PROGRESS
    store.record_reviewer_decision(
        first.task_id, "postpone_final", rationale="last pass"
    )

    assert store.active_task_id == second.task_id
    with pytest.raises(ValueError, match="postpone_siblings"):
        store.record_reviewer_decision(first.task_id, "postpone_siblings")
    with pytest.raises(ValueError, match="postpone_final"):
        store.record_reviewer_decision(first.task_id, "postpone_final")


def test_postponement_requires_a_fresh_unsuccessful_result() -> None:
    """Each postponement follows an unsuccessful execution or revisit."""
    store = TaskStateStore()
    root = store.create_task("Root")
    task = store.create_task("Task", parent_id=root.task_id)
    store.create_task("Sibling", parent_id=root.task_id)

    with pytest.raises(ValueError, match="non-empty unsuccessful"):
        store.record_reviewer_decision(
            task.task_id, "postpone_siblings", rationale="later"
        )

    store.record_result(task.task_id, TaskResult(content="done", success=True))
    with pytest.raises(ValueError, match="non-empty unsuccessful"):
        store.record_reviewer_decision(
            task.task_id, "postpone_siblings", rationale="later"
        )

    store.record_result(task.task_id, TaskResult(content="blocked", success=False))
    store.record_reviewer_decision(task.task_id, "postpone_siblings", rationale="later")

    with pytest.raises(ValueError, match="fresh unsuccessful"):
        store.record_reviewer_decision(
            task.task_id, "postpone_final", rationale="final"
        )


def test_final_postponement_waits_for_normal_and_sibling_deferred_work_globally() -> (
    None
):
    """The final drain starts only after all earlier scheduling classes are empty."""
    store = TaskStateStore()
    root = store.create_task("Root")
    left = store.create_task("Left", parent_id=root.task_id)
    right = store.create_task("Right", parent_id=root.task_id)
    left_leaf = store.create_task("Left leaf", parent_id=left.task_id)
    right_leaf = store.create_task("Right leaf", parent_id=right.task_id)

    store.record_result(left_leaf.task_id, TaskResult(content="blocked", success=False))
    store.record_reviewer_decision(
        left_leaf.task_id, "postpone_siblings", rationale="later"
    )
    store.record_result(left_leaf.task_id, TaskResult(content="blocked", success=False))
    store.record_reviewer_decision(
        left_leaf.task_id, "postpone_final", rationale="final"
    )

    assert store.active_task_id == right_leaf.task_id


def test_compromise_requires_final_postponement_failed_result_and_rationale() -> None:
    """A compromise is terminal but remains an explicit unsuccessful outcome."""
    store = TaskStateStore()
    root = store.create_task("Root")
    task = store.create_task("Limited", parent_id=root.task_id)

    store.record_result(task.task_id, TaskResult(content="blocked", success=False))
    with pytest.raises(ValueError, match="final postponement"):
        store.record_reviewer_decision(
            task.task_id, "compromise", rationale="known gap"
        )
    store.record_reviewer_decision(
        task.task_id, "postpone_siblings", rationale="try later"
    )
    store.record_result(
        task.task_id, TaskResult(content="still blocked", success=False)
    )
    store.record_reviewer_decision(
        task.task_id, "postpone_final", rationale="last pass"
    )
    store.record_result(
        task.task_id, TaskResult(content="known limitation", success=False)
    )

    with pytest.raises(ValueError, match="rationale"):
        store.record_reviewer_decision(task.task_id, "compromise")
    store.record_reviewer_decision(
        task.task_id, "compromise", rationale="source unavailable"
    )

    assert task.status is TaskStatus.COMPROMISED
    assert task.result is not None and task.result.success is False
    assert store.active_task_id == root.task_id
    assert "known limitation" in store.render_markdown()


def test_root_skips_sibling_postponement_but_can_enter_final_drain() -> None:
    """The root has no siblings, so only final postponement is meaningful."""
    store = TaskStateStore()
    root = store.create_task("Root")
    store.record_result(root.task_id, TaskResult(content="blocked", success=False))

    with pytest.raises(ValueError, match="root"):
        store.record_reviewer_decision(
            root.task_id, "postpone_siblings", rationale="later"
        )
    store.record_reviewer_decision(
        root.task_id, "postpone_final", rationale="last pass"
    )

    assert root.status is TaskStatus.POSTPONED
    store.record_result(
        root.task_id, TaskResult(content="known root gap", success=False)
    )
    store.record_reviewer_decision(
        root.task_id, "compromise", rationale="cannot resolve"
    )
    assert store.all_done() is True


@pytest.mark.parametrize("status", [TaskStatus.POSTPONED, TaskStatus.COMPROMISED])
def test_deferred_statuses_require_reviewer_decisions(status: TaskStatus) -> None:
    """Generic transitions cannot bypass deferred-decision validation."""
    store = TaskStateStore()
    task = store.create_task("Task")
    store.transition(task.task_id, TaskStatus.IN_PROGRESS)

    with pytest.raises(ValueError, match="Invalid task transition"):
        store.transition(task.task_id, status)


@pytest.mark.parametrize(
    "result",
    [
        TaskResult(content="", success=False),
        TaskResult(content="looks done", success=True),
    ],
)
def test_compromise_rejects_empty_or_successful_results(result: TaskResult) -> None:
    """Compromise cannot disguise missing evidence or successful work as a limitation."""
    store = TaskStateStore()
    root = store.create_task("Root")
    store.record_result(root.task_id, TaskResult(content="blocked", success=False))
    store.record_reviewer_decision(
        root.task_id, "postpone_final", rationale="last pass"
    )
    store.record_result(root.task_id, result)

    with pytest.raises(ValueError, match="non-empty unsuccessful"):
        store.record_reviewer_decision(
            root.task_id, "compromise", rationale="known gap"
        )
