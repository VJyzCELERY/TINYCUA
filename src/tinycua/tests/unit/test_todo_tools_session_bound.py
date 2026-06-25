"""Session-bound todo tool contracts."""

from __future__ import annotations

from tinycua.tools.todo_tools import TodoReadTool, TodoWriteTool


def test_todo_tools_bind_to_session_owned_lists_without_global_leakage() -> None:
    """Todo tools mutate the bound session list only."""
    first: list[dict] = []
    second: list[dict] = []
    read = TodoReadTool()
    write = TodoWriteTool()

    read.bind_todo_store(first)
    write.bind_todo_store(first)
    write(descriptions=["first item"])

    read.bind_todo_store(second)
    write.bind_todo_store(second)
    write(descriptions=["second item"])
    write(done_index=0)

    assert first == [{"description": "first item", "status": "pending"}]
    assert read() == [{"description": "second item", "status": "done", "done": True}]
