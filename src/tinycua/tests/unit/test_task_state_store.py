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


def test_approved_result_propagates_context_to_next_sibling() -> None:
    """Reviewer approval propagates result summary to the next pending sibling.

    Milestone 8 Stream A: when a task is approved, its result summary is
    appended to the next pending sibling's metadata["context"] so the
    downstream task sees the approved result in its "Useful Prior Context".
    """
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
    # Context IS propagated to the next pending sibling (Milestone 8)
    assert "context" in module.metadata
    assert "Create project scaffold" in module.metadata["context"]
    assert "backend/app.py" in module.metadata["context"]


@pytest.mark.parametrize(
    "result",
    [
        None,
        TaskResult(content="failed", success=False),
        TaskResult(content="   "),
        TaskResult(content="generated", metadata={"auto_generated": True}),
    ],
)
def test_approval_without_executor_evidence_leaves_task_in_progress(
    result: TaskResult | None,
) -> None:
    """Invalid approval cannot mutate review, task, parent, or sibling state."""
    store = TaskStateStore()
    root = store.create_task("Root")
    first = store.create_task("First", parent_id=root.task_id)
    second = store.create_task("Second", parent_id=root.task_id)

    if result is not None:
        store.record_result(first.task_id, result)
    with pytest.raises(ValueError, match="requires successful executor evidence"):
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
    """A failed leaf reopens when new executor evidence is recorded."""
    store = TaskStateStore()
    task = store.create_task("Retry me")

    store.record_result(task.task_id, TaskResult(content="failed", success=False))
    with pytest.raises(ValueError, match="requires successful executor evidence"):
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


def test_task_store_validates_status_transitions_and_records_reviewer_decisions() -> None:
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

    store.update_task(task.task_id, title="Corrected title", metadata={"source": "review"})

    assert store.version > before
    assert "Corrected title" in store.render_markdown()
    assert store.snapshot()["transition_log"][-1]["action"] == "update_task"
    assert task.metadata["source"] == "review"


def test_cancel_and_supersede_terminal_tasks_advance_selection_and_preserve_lineage() -> None:
    """Disposed leaves remain auditable but cannot be scheduled again."""
    store = TaskStateStore()
    root = store.create_task("Root")
    impossible = store.create_task("Impossible", parent_id=root.task_id)
    remaining = store.create_task("Remaining", parent_id=root.task_id)

    store.cancel_task(impossible.task_id, "source has no benchmark data")
    assert impossible.status == TaskStatus.CANCELLED
    assert store.active_task_id == remaining.task_id

    replacement = store.supersede_task(remaining.task_id, "Replacement", "use available data")
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


def test_acceptance_clauses_require_coverage_and_passing_evidence() -> None:
    """A root cannot complete until every explicit clause has current evidence."""
    store = TaskStateStore()
    root = store.create_task(
        "Root",
        acceptance_clauses=["CLI exits zero", "UI renders the result"],
    )
    first, second = store.decompose_task(
        root.task_id,
        [
            {"title": "Run CLI", "clause_ids": ["acceptance-1"]},
            {"title": "Check UI", "clause_ids": ["acceptance-2"]},
        ],
    )

    assert root.metadata["acceptance_clauses"] == [
        {"id": "acceptance-1", "text": "CLI exits zero"},
        {"id": "acceptance-2", "text": "UI renders the result"},
    ]
    assert store.get_task(first).metadata["acceptance_clause_ids"] == ["acceptance-1"]
    assert store.get_task(second).metadata["acceptance_clause_ids"] == ["acceptance-2"]

    store.record_result(first, TaskResult(content="source inspected", metadata={}))
    with pytest.raises(ValueError, match="passing evidence"):
        store.record_reviewer_decision(first, ReviewerDecision.APPROVED)

    store.record_result(
        first,
        TaskResult(
            content="CLI passed",
            metadata={"clause_evidence": {"acceptance-1": [{"passed": True}]}},
        ),
    )
    store.record_reviewer_decision(first, ReviewerDecision.APPROVED)
    store.record_result(
        second,
        TaskResult(
            content="UI passed",
            metadata={"clause_evidence": {"acceptance-2": [{"passed": True}]}},
        ),
    )
    store.record_reviewer_decision(second, ReviewerDecision.APPROVED)

    store.record_result(root.task_id, TaskResult(content="verified root"))
    store.record_reviewer_decision(root.task_id, ReviewerDecision.APPROVED)

    assert root.status == TaskStatus.COMPLETED


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
        {"decision": "needs_revision", "rationale": "", "metadata": {}}
    ]


def test_invalid_staged_approval_is_retained_for_correction() -> None:
    """A failed approval commit leaves the provisional decision available."""
    store = TaskStateStore()
    task = store.create_task("Review me", acceptance_clauses=["verify behavior"])
    store.record_result(task.task_id, TaskResult(content="evidence"))
    store.stage_reviewer_decision(task.task_id, ReviewerDecision.APPROVED)

    with pytest.raises(ValueError, match="passing evidence"):
        store.commit_staged_reviewer_decision(task.task_id)

    assert task.task_id in store._staged_reviewer_decisions


def test_malformed_clause_evidence_does_not_approve_child() -> None:
    """Acceptance evidence must be a list of passing mappings."""
    store = TaskStateStore()
    root = store.create_task("Root", acceptance_clauses=["verify behavior"])
    child = store.create_task("Child", parent_id=root.task_id, clause_ids=["acceptance-1"])
    store.record_result(
        child.task_id,
        TaskResult(
            content="done",
            metadata={"clause_evidence": {"acceptance-1": "malformed"}},
        ),
    )

    with pytest.raises(ValueError, match="passing evidence"):
        store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)

    assert child.status is not TaskStatus.COMPLETED
