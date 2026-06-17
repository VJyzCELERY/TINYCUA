"""Session-bound task tool contracts."""

from __future__ import annotations

from tinycua.models.task import TaskStateStore
from tinycua.tools.task_tools import (
    TaskDecomposeTool,
    TaskExecuteTool,
    TaskInitTool,
    TaskInspectTool,
    TaskResultUpdateTool,
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
    assert inspect()["tasks"][second_store.root_task_id]["title"] == "Second session"


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
