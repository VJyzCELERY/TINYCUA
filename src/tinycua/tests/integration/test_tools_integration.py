"""Integration tests for basic tools — SDK registration and execution.

These tests cover the acceptance criteria defined in the M1 Basic Tools spec.
They are written FIRST (RED phase) and will fail until implementation is complete.
"""

from __future__ import annotations


import pytest

import tinycua.agent.tools as _tools_mod

from tinycua_sdk import Agent, LanguageModel  # noqa: E402
from tinycua_sdk.tools.decorators import Tool  # noqa: E402


# ---------------------------------------------------------------------------
# register_all
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_default_context():
    _tools_mod._DEFAULT_CONTEXT = None


def test_register_all_returns_all_tools():
    """register_all() should return a list of all basic tool functions."""
    from tinycua.agent.tools import register_all

    tools = register_all()
    tool_names = {t.name for t in tools}
    assert "run_shell" in tool_names
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "edit_file" in tool_names
    assert "list_files" in tool_names
    assert "fetch_url" in tool_names
    assert "run_python" in tool_names
    assert "todo_list" in tool_names


def test_register_all_returns_tool_instances():
    """register_all() should return Tool instances (not raw functions)."""
    from tinycua.agent.tools import register_all

    tools = register_all()
    for t in tools:
        assert isinstance(t, Tool), "{t.name} should be a Tool instance"
    assert len(tools) == 8


@pytest.mark.asyncio
async def test_tools_work_through_sdk_executor(tmp_path):
    """Tools should be invocable through the SDK's ToolExecutor."""
    from tinycua.agent.tools import register_all
    from tinycua_sdk.agent.executor import ToolExecutor

    tools = register_all()
    # Build a name→Tool mapping
    tool_map = {t.name: t for t in tools}
    agent = Agent(llm_model=LanguageModel())

    # Write a file and read it back
    test_file = tmp_path / "hello.txt"
    write_result = await ToolExecutor.execute(
        tool_map["write_file"],
        {"path": str(test_file), "content": "Hello, World!"},
        agent,
    )
    assert write_result["success"] is True

    read_result = await ToolExecutor.execute(
        tool_map["read_file"],
        {"path": str(test_file)},
        agent,
    )
    assert "Hello, World!" in read_result

    # Edit the file
    edit_result = await ToolExecutor.execute(
        tool_map["edit_file"],
        {
            "path": str(test_file),
            "start": 1,
            "content": "Edited line",
        },
        agent,
    )
    assert edit_result["success"] is True
    assert edit_result["lines_replaced"] >= 1

    # List files (covers spec.md Acceptance Scenario 4)
    list_result = await ToolExecutor.execute(
        tool_map["list_files"],
        {"path": str(tmp_path), "pattern": "*.txt"},
        agent,
    )
    assert "hello.txt" in list_result or any("hello.txt" in p for p in list_result)


# ---------------------------------------------------------------------------
# Todo list full workflow
# ---------------------------------------------------------------------------


def test_todo_list_full_workflow():
    """Todo list add/list/update/clear should work as a full workflow."""
    from tinycua.agent.tools import register_all

    tools = register_all()
    todo_tool = next(t for t in tools if t.name == "todo_list")

    # Add items
    r1 = todo_tool(command="add", item="First task")
    assert r1["success"] is True
    assert r1["id"] == 1

    r2 = todo_tool(command="add", item="Second task")
    assert r2["id"] == 2

    # List items
    items = todo_tool(command="list")
    assert len(items) == 2

    # Update first item to completed
    update_r = todo_tool(command="update", item_id=1, status="completed")
    assert update_r["success"] is True

    # Clear
    clear_r = todo_tool(command="clear")
    assert clear_r["success"] is True
    assert clear_r["cleared_count"] == 2

    items_after = todo_tool(command="list")
    assert len(items_after) == 0


# ---------------------------------------------------------------------------
# Context injection
# ---------------------------------------------------------------------------


def test_context_injection():
    """Tools created with a shared context should share state."""
    from tinycua.agent.tools.context import ExecutorContext, ExecutorConfig
    from tinycua.agent.tools import register_all

    config = ExecutorConfig(shell_timeout=10, enable_fetch=False)
    ctx = ExecutorContext(config=config)
    tools = register_all(context=ctx)

    # Tools bound to this context should use the config
    todo_tool = next(t for t in tools if t.name == "todo_list")
    todo_tool(command="add", item="Context test")
    items = todo_tool(command="list")
    assert len(items) == 1
    assert items[0]["item"] == "Context test"


# ---------------------------------------------------------------------------
# Timeout enforcement (these tests sleep and are intentionally slow)
# ---------------------------------------------------------------------------


def test_shell_timeout_enforcement():
    """A shell command exceeding the configured timeout should be killed."""
    from tinycua.agent.tools.context import ExecutorContext, ExecutorConfig
    from tinycua.agent.tools import register_all

    config = ExecutorConfig(shell_timeout=1)
    ctx = ExecutorContext(config=config)
    tools = register_all(context=ctx)

    shell_tool = next(t for t in tools if t.name == "run_shell")
    # timeout=30 exceeds shell_timeout=1 → should be clamped to 1
    result = shell_tool(command="sleep 10", timeout=30)
    assert result["timed_out"] is True
    assert result["exit_code"] == -1


def test_timeout_is_clamped_by_context_config():
    """Tool timeout parameter should be clamped to context config max."""
    from tinycua.agent.tools.context import ExecutorContext, ExecutorConfig
    from tinycua.agent.tools import register_all

    config = ExecutorConfig(shell_timeout=2)
    ctx = ExecutorContext(config=config)
    tools = register_all(context=ctx)

    shell_tool = next(t for t in tools if t.name == "run_shell")
    result = shell_tool(command="sleep 10", timeout=30)
    assert result["timed_out"] is True
    assert result["exit_code"] == -1


def test_timeout_parameter_underrides_context():
    """Tool timeout below the context config should be respected (not clamped up)."""
    from tinycua.agent.tools.context import ExecutorContext, ExecutorConfig
    from tinycua.agent.tools import register_all

    config = ExecutorConfig(shell_timeout=30)
    ctx = ExecutorContext(config=config)
    tools = register_all(context=ctx)

    shell_tool = next(t for t in tools if t.name == "run_shell")
    # timeout=1 is below shell_timeout=30 → should NOT be clamped, should actually time out
    result = shell_tool(command="sleep 10", timeout=1)
    assert result["timed_out"] is True
    assert result["exit_code"] == -1


# ---------------------------------------------------------------------------
# Feature gating
# ---------------------------------------------------------------------------


def test_feature_flags_disable_tools():
    """Disabling a feature flag should make the corresponding tool unavailable."""
    from tinycua.agent.tools.context import ExecutorContext, ExecutorConfig
    from tinycua.agent.tools import register_all

    config = ExecutorConfig(enable_fetch=False, enable_python_exec=False)
    ctx = ExecutorContext(config=config)
    tools = register_all(context=ctx)

    fetch_tool = next(t for t in tools if t.name == "fetch_url")
    result = fetch_tool(url="http://placeholder.local/not-reached")
    assert "error" in result or "disabled" in result

    python_tool = next(t for t in tools if t.name == "run_python")
    result = python_tool(code="print('hello')")
    assert "error" in result or "disabled" in result
