"""Session-bound task tool contracts."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from tinycua_sdk.agent.executor import ToolExecutor

from tinycua.loops.task_nodes import (
    _render_active_task_work_order,
    _render_task_tree_markdown,
    _task_context_snapshot_from_store,
)
from tinycua.models.session import Session
from tinycua.models.task import TaskResult, TaskStateStore
from tinycua.tools.task_tools import (
    TaskDecomposeTool,
    TaskExecuteTool,
    TaskInitTool,
    TaskInspectTool,
    TaskResultUpdateTool,
    TaskShrinkTool,
    TaskUpdateTool,
    TaskReviewDecisionTool,
    TerminateTool,
)


def test_task_tools_are_session_bound_and_do_not_leak_between_stores() -> None:
    """Bound tools mutate only the active session task store."""
    first_store = TaskStateStore()
    second_store = TaskStateStore()
    init = TaskInitTool()
    inspect = TaskInspectTool()

    init.bind_task_store(first_store)
    init("First session")

    init.bind_task_store(second_store)
    inspect.bind_task_store(second_store)
    init("Second session")

    assert len(first_store.tasks) == 1
    assert len(second_store.tasks) == 1
    # task_inspect (list mode) returns a compact list of {id,title,status,has_result}.
    listing = inspect()
    titles = [t["title"] for t in listing["tasks"]]
    assert "Second session" in titles
    assert second_store.root_task_id in {t["id"] for t in listing["tasks"]}


def test_task_tools_are_active_task_aware_and_error_safe() -> None:
    """Tool calls use active task defaults and return structured errors."""
    store = TaskStateStore()
    init = TaskInitTool()
    decompose = TaskDecomposeTool()
    execute = TaskExecuteTool()
    result_update = TaskResultUpdateTool()
    for tool in (init, decompose, execute, result_update):
        tool.bind_task_store(store)

    root = init("Root", acceptance_clauses=["First child is completed"])
    decompose(
        root["task_id"],
        [
            {"title": "First child", "clause_ids": ["acceptance-1"]},
            {"title": "Second child"},
        ],
    )

    executed = execute()
    assert executed["task_id"] == store.active_task_id
    assert executed["status"] == "in_progress"

    recorded = result_update(content="finished")
    assert recorded["status"] == "in_progress"
    assert store.get_active_task().title == "First child"

    missing = result_update(task_id="missing", content="nope")
    assert missing["success"] is False
    assert "missing" in missing["error"]


def test_task_init_retains_explicit_acceptance_clauses() -> None:
    """Root clauses remain required context without child ownership."""
    store = TaskStateStore()
    init = TaskInitTool()
    decompose = TaskDecomposeTool()
    for tool in (init, decompose):
        tool.bind_task_store(store)

    root = init("Deliver a CLI", acceptance_clauses=["CLI exits zero"])
    child_id = decompose(root["task_id"], ["Implement CLI"])["child_task_ids"][0]

    assert "acceptance_clauses" in init.parameters["required"]
    assert store.get_task(root["task_id"]).metadata["acceptance_clauses"] == [
        {"id": "acceptance-1", "text": "CLI exits zero"}
    ]
    assert store.get_task(child_id).metadata == {}
    store.record_result(child_id, TaskResult(content="CLI implemented", success=True))
    store.record_reviewer_decision(child_id, "approved")

    assert store.get_task(child_id).status.value == "completed"


def test_task_init_failure_preserves_existing_roadmap_and_can_retry_before_success() -> (
    None
):
    """Failed initialization never replaces a valid root task or its children."""
    store = TaskStateStore()
    init = TaskInitTool()
    decompose = TaskDecomposeTool()
    for tool in (init, decompose):
        tool.bind_task_store(store)

    assert init(title="", acceptance_clauses=["Deliver report"])["success"] is False
    root = init("Deliver report", acceptance_clauses=["Deliver report"])
    decompose(root["task_id"], ["Write report"])
    before = store.snapshot()

    repeated = init("Replace roadmap", acceptance_clauses=["Replace roadmap"])

    assert repeated["success"] is False
    assert "already initialized" in repeated["error"].lower()
    assert store.snapshot() == before


def test_task_init_executor_derives_clause_from_title_when_omitted() -> None:
    """Title-only SDK calls retain an acceptance clause instead of empty metadata."""
    store = TaskStateStore()
    init = TaskInitTool()
    init.bind_task_store(store)

    result = asyncio.run(
        ToolExecutor.execute(
            init,
            {"title": "Deliver a CLI that exits zero"},
            SimpleNamespace(tool_permissions={}),
        )
    )

    assert result["success"] is True
    assert store.get_task(result["task_id"]).metadata["acceptance_clauses"] == [
        {"id": "acceptance-1", "text": "Deliver a CLI that exits zero"}
    ]


def test_task_update_cannot_complete_without_execution_result() -> None:
    """TaskUpdate cannot mark work complete; execution result tool owns that."""
    store = TaskStateStore()
    init = TaskInitTool()
    update = TaskUpdateTool()
    for tool in (init, update):
        tool.bind_task_store(store)

    root = init("Root")
    result = update(task_id=root["task_id"], status="completed")

    assert result["success"] is False
    assert "not supported" in result["error"]
    assert store.get_task(root["task_id"]).status == "pending"


def test_analyzer_update_cannot_replace_initial_decomposition() -> None:
    """Analyzer must create actionable work before recording planning metadata."""
    store = TaskStateStore()
    init = TaskInitTool()
    update = TaskUpdateTool()
    for tool in (init, update):
        tool.bind_task_store(store)
    update.bind_source_node("task_analyzer")
    root = init("Root")

    result = update(task_id=root["task_id"], assessment="ready")

    assert result["success"] is False
    assert not store.get_task(root["task_id"]).children


def test_task_decompose_preserves_all_analyzer_subtasks() -> None:
    """Decomposition preserves every analyzer-provided subtask (no cap).

    Spec: ./specs/tinycua-runtime-invariants/spec.md:208-210, 246-249, 262.
    Source: src/tinycua/docs/design/loops/task_analyzer.md:23-31,
            src/tinycua/docs/design/models/task.md:10-28.
    The runtime must not truncate analyzer-created subtasks.
    """
    store = TaskStateStore()
    init = TaskInitTool()
    decompose = TaskDecomposeTool()
    for tool in (init, decompose):
        tool.bind_task_store(store)

    root = init("Build app", acceptance_clauses=["Build app"])
    result = decompose(
        root["task_id"],
        [
            {"title": "one", "clause_ids": ["acceptance-1"]},
            "two",
            "three",
            "four",
        ],
    )

    assert result["success"] is True
    assert len(result["child_task_ids"]) == 4
    assert [store.get_task(cid).title for cid in result["child_task_ids"]] == [
        "one",
        "two",
        "three",
        "four",
    ]


def test_task_decompose_schema_accepts_structured_children_and_strings() -> None:
    """The model can provide child context without breaking string callers."""
    schema = TaskDecomposeTool().parameters["properties"]["subtasks"]["items"]

    assert schema["oneOf"][0] == {"type": "string"}
    child_schema = schema["oneOf"][1]
    assert child_schema["required"] == ["title", "description"]
    assert set(child_schema["properties"]) == {"title", "description"}


def test_task_decompose_does_not_collapse_app_web_ui_to_vertical_slice() -> None:
    """App/web-ui subtasks are preserved, not collapsed to one vertical slice.

    Spec: ./specs/tinycua-runtime-invariants/spec.md:29-42, 246-249, 261.
    Source: src/tinycua/docs/design/loops/task_analyzer.md:6-17, 23-31.
    The app/web-ui collapse heuristic is a forbidden prompt-category forcing.
    """
    store = TaskStateStore()
    init = TaskInitTool()
    decompose = TaskDecomposeTool()
    for tool in (init, decompose):
        tool.bind_task_store(store)

    root = init(
        "Build note taking app with web UI",
        acceptance_clauses=["Build note taking app with web UI"],
    )
    result = decompose(
        root["task_id"],
        [{"title": "backend", "clause_ids": ["acceptance-1"]}, "frontend", "api"],
    )

    assert result["success"] is True
    assert len(result["child_task_ids"]) == 3
    titles = [store.get_task(cid).title for cid in result["child_task_ids"]]
    assert titles == ["backend", "frontend", "api"]
    assert not any("vertical-slice" in t.lower() for t in titles)


def test_task_update_can_correct_title() -> None:
    """TaskUpdate can fix a stale or mistaken title from task_init."""
    store = TaskStateStore()
    init = TaskInitTool()
    update = TaskUpdateTool()
    for tool in (init, update):
        tool.bind_task_store(store)

    root = init("original title")
    result = update(task_id=root["task_id"], title="corrected title")

    assert result["success"] is True
    assert store.get_task(root["task_id"]).title == "corrected title"

    # Regression guard: the existing description branch still mutates description.
    result_desc = update(
        task_id=root["task_id"], description="extra context from completed work"
    )
    assert result_desc["success"] is True
    assert (
        store.get_task(root["task_id"]).description
        == "extra context from completed work"
    )


def test_task_update_title_rejected_on_completed_task() -> None:
    """Title edits are rejected on completed tasks (immutable history)."""
    store = TaskStateStore()
    update = TaskUpdateTool()
    update.bind_task_store(store)

    root = store.create_task("Stale title")
    # Complete via the proven record_result + approve pattern.
    store.record_result(
        root.task_id,
        TaskResult(
            content="done",
            success=True,
        ),
    )
    store.record_reviewer_decision(root.task_id, "approved")
    assert store.get_task(root.task_id).status.value == "completed"

    result = update(task_id=root.task_id, title="new title")

    assert result["success"] is False
    assert "immutable" in result["error"]
    assert store.get_task(root.task_id).title == "Stale title"


def test_task_update_title_propagates_to_roadmap_rendering() -> None:
    """Corrected title shows up in the roadmap every node reads.

    _render_task_tree_markdown reads task.title verbatim, so an
    uncorrected stale title keeps re-infecting downstream prompts. The
    fix must propagate immediately.
    """
    store = TaskStateStore()
    init = TaskInitTool()
    update = TaskUpdateTool()
    for tool in (init, update):
        tool.bind_task_store(store)

    init("original title")
    update(title="corrected title")

    snapshot = _task_context_snapshot_from_store(store)
    rendered = _render_task_tree_markdown(snapshot)

    assert "corrected title" in rendered
    assert "original title" not in rendered


def test_task_shrink_cancels_and_supersedes_with_a_rationale() -> None:
    """Existing shrink tool exposes terminal local-replan operations."""
    store = TaskStateStore()
    init = TaskInitTool()
    decompose = TaskDecomposeTool()
    shrink = TaskShrinkTool()
    for tool in (init, decompose, shrink):
        tool.bind_task_store(store)

    root = init("Root", acceptance_clauses=["Remaining work"])
    children = decompose(
        root["task_id"],
        ["Impossible", {"title": "Remaining", "clause_ids": ["acceptance-1"]}],
    )["child_task_ids"]
    missing_rationale = shrink("cancel", children[0], "")
    cancelled = shrink("cancel", children[0], "source lacks required data")
    superseded = shrink(
        "supersede",
        children[1],
        "use an available source",
        replacement_title="Replacement",
    )

    assert missing_rationale["success"] is False
    assert cancelled["cancellation_state"] == "pending"
    assert superseded["replacement_task_id"] in store.tasks


def test_task_shrink_can_supersede_postponed_work() -> None:
    """Deferral does not remove the existing replacement escape hatch."""
    store = TaskStateStore()
    root = store.create_task("Root")
    blocked = store.create_task("Blocked", parent_id=root.task_id)
    store.record_result(blocked.task_id, TaskResult(content="blocked", success=False))
    store.record_reviewer_decision(
        blocked.task_id, "postpone_siblings", rationale="try another path"
    )
    shrink = TaskShrinkTool()
    shrink.bind_task_store(store)

    result = shrink(
        "supersede",
        blocked.task_id,
        "available alternative",
        replacement_title="Replacement",
    )

    assert result["success"] is True
    assert blocked.status.value == "superseded"


def test_root_acceptance_context_cannot_be_reassigned_through_metadata() -> None:
    """The original acceptance context remains immutable."""
    store = TaskStateStore()
    root = store.create_task("Root", acceptance_clauses=["behavior"])
    update = TaskUpdateTool()
    update.bind_task_store(store)

    result = update(task_id=root.task_id, acceptance_clauses="replacement")

    assert result["success"] is False
    assert root.metadata["acceptance_clauses"] == [
        {"id": "acceptance-1", "text": "behavior"}
    ]


def test_review_tool_stages_corrections_until_reviewer_termination() -> None:
    """Review decisions remain provisional while the reviewer can correct them."""
    store = TaskStateStore()
    init = TaskInitTool()
    review = TaskReviewDecisionTool()
    terminate = TerminateTool()
    for tool in (init, review, terminate):
        tool.bind_task_store(store)
    terminate.bind_source_node("result_reviewer")

    task_id = init("Root")["task_id"]
    store.record_result(task_id, TaskResult(content="evidence"))
    assert (
        review(decision="approved", rationale="The result is acceptable.")["staged"]
        is True
    )
    assert (
        review(decision="needs_revision", rationale="The report has a gap.")["staged"]
        is True
    )
    assert store.get_task(task_id).reviewer_decisions == []

    terminated = terminate()

    assert terminated["decision"] == "needs_revision"
    assert (
        store.get_task(task_id).reviewer_decisions[-1]["decision"] == "needs_revision"
    )


def test_reviewer_termination_commits_the_selected_staged_task() -> None:
    """Termination commits the active task's staged review decision."""
    store = TaskStateStore()
    root = store.create_task("Root")
    store.create_task("First", parent_id=root.task_id)
    second = store.create_task("Second", parent_id=root.task_id)
    store.record_result(second.task_id, TaskResult(content="evidence"))
    store.active_task_id = second.task_id
    review = TaskReviewDecisionTool()
    terminate = TerminateTool()
    for tool in (review, terminate):
        tool.bind_task_store(store)
        tool.bind_source_node("result_reviewer")

    assert review(
        task_id=second.task_id,
        decision="approved",
        rationale="The result is acceptable.",
    )["success"]
    assert terminate()["success"]

    assert (
        store.get_task(second.task_id).reviewer_decisions[-1]["decision"] == "approved"
    )


def test_reviewer_cannot_decide_a_sibling_task() -> None:
    """Reviewer task-state mutations are confined to the active task."""
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    sibling = store.create_task("Sibling", parent_id=root.task_id)
    store.record_result(active.task_id, TaskResult(content="active evidence"))
    store.record_result(sibling.task_id, TaskResult(content="sibling evidence"))
    store.active_task_id = active.task_id
    review = TaskReviewDecisionTool()
    review.bind_task_store(store)
    review.bind_source_node("result_reviewer")

    result = review(
        task_id=sibling.task_id,
        decision="approved",
        rationale="The result is acceptable.",
    )

    assert result["success"] is False
    assert "active task" in result["error"].lower()
    assert sibling.task_id not in store._staged_reviewer_decisions


def test_reviewer_decision_atomically_curates_future_task_context() -> None:
    """One review commit records its verdict and future-task handoff together."""
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    future = store.create_task("Future", parent_id=root.task_id)
    store.record_result(active.task_id, TaskResult(content="evidence"))
    store.active_task_id = active.task_id
    review = TaskReviewDecisionTool()
    review.bind_task_store(store)
    review.bind_source_node("result_reviewer")

    staged = review(
        decision="approved",
        rationale="The result is acceptable.",
        context_updates=[
            {
                "task_id": future.task_id,
                "context": "Existing output already satisfies this task; validate it.",
            }
        ],
    )
    store.commit_staged_reviewer_decision(active.task_id)

    assert staged["success"]
    assert active.reviewer_decisions[-1]["decision"] == "approved"
    assert "Existing output already satisfies this task" in future.metadata["context"]
    assert future.metadata["suggested_mode"] == "verify_only"


def test_review_tool_exposes_deferred_decisions_but_not_rejected() -> None:
    """Model-facing review choices use one revision verdict plus defer states."""
    decisions = TaskReviewDecisionTool().parameters["properties"]["decision"]["enum"]

    assert decisions == [
        "approved",
        "needs_revision",
        "replan",
        "postpone_siblings",
        "postpone_final",
        "compromise",
    ]


def test_invalid_reviewer_context_update_commits_nothing() -> None:
    """Invalid future-task curation cannot partially commit a verdict."""
    store = TaskStateStore()
    active = store.create_task("Active")
    store.record_result(active.task_id, TaskResult(content="evidence"))
    review = TaskReviewDecisionTool()
    review.bind_task_store(store)
    review.bind_source_node("result_reviewer")

    staged = review(
        decision="approved",
        rationale="The result is acceptable.",
        context_updates=[{"task_id": "missing", "context": "validate existing work"}],
    )

    assert staged["success"] is False
    assert active.reviewer_decisions == []
    assert active.task_id not in store._staged_reviewer_decisions


def test_executor_result_is_immediately_visible_to_reviewer() -> None:
    """Executor commit immediately persists its active task report for review."""
    store = TaskStateStore()
    init = TaskInitTool()
    result_update = TaskResultUpdateTool()
    terminate = TerminateTool()
    for tool in (init, result_update, terminate):
        tool.bind_task_store(store)
    for tool in (result_update, terminate):
        tool.bind_source_node("task_executor")

    task_id = init("Root")["task_id"]
    recorded = result_update(content="completed")

    assert "staged" not in recorded
    assert recorded["recorded_for_review"] is True
    assert "awaiting downstream review" in recorded["message"]
    assert store.get_task(task_id).result is not None
    assert store.get_task(task_id).status.value == "in_progress"
    assert terminate()["success"] is True
    assert store.get_task(task_id).result is not None


def test_executor_termination_does_not_commit_a_task_result() -> None:
    """Terminate ends the executor turn without selecting a task result."""
    store = TaskStateStore()
    terminate = TerminateTool()
    terminate.bind_task_store(store)
    terminate.bind_source_node("task_executor")

    result = terminate()

    assert result["success"] is True
    assert "task_id" not in result


def test_executor_cannot_report_a_sibling_task_result() -> None:
    """Executor task-state mutations are confined to the active task."""
    store = TaskStateStore()
    root = store.create_task("Root")
    active = store.create_task("Active", parent_id=root.task_id)
    sibling = store.create_task("Sibling", parent_id=root.task_id)
    result_update = TaskResultUpdateTool()
    result_update.bind_task_store(store)
    result_update.bind_source_node("task_executor")

    result = result_update(task_id=sibling.task_id, content="not mine")

    assert result["success"] is False
    assert "active task" in result["error"].lower()
    assert store.get_task(active.task_id).result is None
    assert store.get_task(sibling.task_id).result is None


def test_executor_work_order_renders_acceptance_context() -> None:
    """Executor prompts retain root acceptance criteria as context."""
    session = Session()
    root = session.task_store.create_task(
        "Root", acceptance_clauses=["CLI exits zero", "UI renders"]
    )
    session.task_store.decompose_task(
        root.task_id,
        [
            {"title": "CLI", "clause_ids": ["acceptance-1"]},
            {"title": "UI", "clause_ids": ["acceptance-2"]},
        ],
    )

    work_order = _render_active_task_work_order(session)

    assert "CLI exits zero" in work_order
    assert "UI renders" in work_order
