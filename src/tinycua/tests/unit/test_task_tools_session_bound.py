"""Session-bound task tool contracts."""

from __future__ import annotations

from tinycua.loops.task_nodes import (
    _render_task_tree_markdown,
    _task_context_snapshot_from_store,
)
from tinycua.models.task import TaskResult, TaskStateStore
from tinycua.tools.task_tools import (
    TaskDecomposeTool,
    TaskExecuteTool,
    TaskInitTool,
    TaskInspectTool,
    TaskResultUpdateTool,
    TaskShrinkTool,
    TaskUpdateTool,
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

    root = init("Root")
    decompose(root["task_id"], ["First child", "Second child"])

    executed = execute()
    assert executed["task_id"] == store.active_task_id
    assert executed["status"] == "in_progress"

    recorded = result_update(content="finished")
    assert recorded["status"] == "in_progress"
    assert store.get_active_task().title == "First child"

    missing = result_update(task_id="missing", content="nope")
    assert missing["success"] is False
    assert "missing" in missing["error"]


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

    root = init("Build app")
    result = decompose(root["task_id"], ["one", "two", "three", "four"])

    assert result["success"] is True
    assert len(result["child_task_ids"]) == 4
    assert [store.get_task(cid).title for cid in result["child_task_ids"]] == [
        "one",
        "two",
        "three",
        "four",
    ]


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

    root = init("Build note taking app with web UI")
    result = decompose(root["task_id"], ["backend", "frontend", "api"])

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
        store.get_task(root["task_id"]).description == "extra context from completed work"
    )


def test_task_update_title_rejected_on_completed_task() -> None:
    """Title edits are rejected on completed tasks (immutable history)."""
    store = TaskStateStore()
    init = TaskInitTool()
    update = TaskUpdateTool()
    for tool in (init, update):
        tool.bind_task_store(store)

    root = init("Stale title")
    # Complete via the proven record_result + approve pattern.
    store.record_result(root["task_id"], TaskResult(content="done", success=True))
    store.record_reviewer_decision(root["task_id"], "approved")
    assert store.get_task(root["task_id"]).status.value == "completed"

    result = update(task_id=root["task_id"], title="new title")

    assert result["success"] is False
    assert "immutable" in result["error"]
    assert store.get_task(root["task_id"]).title == "Stale title"


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

    root = init("Root")
    children = decompose(root["task_id"], ["Impossible", "Remaining"])["child_task_ids"]
    missing_rationale = shrink("cancel", children[0], "")
    cancelled = shrink("cancel", children[0], "source lacks required data")
    superseded = shrink(
        "supersede", children[1], "use an available source", replacement_title="Replacement"
    )

    assert missing_rationale["success"] is False
    assert cancelled["status"] == "cancelled"
    assert superseded["replacement_task_id"] in store.tasks
