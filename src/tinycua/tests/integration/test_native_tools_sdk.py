"""Integration tests verifying tools work through the SDK's ToolExecutor."""

import pytest


def test_tool_registers_with_agent():
    """All native tools can be registered with an SDK Agent."""
    from tinycua_sdk.tools.decorators import Tool

    from tinycua.agent.tools.native import (
        append_file,
        fetch_url,
        list_files,
        read_file,
        run_python,
        run_shell,
        search_files,
        str_replace,
        web_search,
        write_file,
    )

    tools = [
        run_shell,
        read_file,
        write_file,
        str_replace,
        append_file,
        list_files,
        search_files,
        fetch_url,
        web_search,
        run_python,
    ]
    for tool_func in tools:
        assert isinstance(tool_func, Tool), (
            f"{tool_func.name} should be a Tool instance"
        )
    assert all(hasattr(t, "name") and hasattr(t, "parameters") for t in tools)


def test_tool_schemas_valid_json_schema():
    """Each tool generates valid JSON Schema for function calling."""
    from tinycua.agent.tools.native.shell import run_shell
    from tinycua.agent.tools.native.files import read_file, write_file

    for tool in [run_shell, read_file, write_file]:
        params = tool.parameters
        assert params["type"] == "object"
        assert "properties" in params
        for prop in params["properties"].values():
            assert "type" in prop


@pytest.mark.asyncio
async def test_tool_executor_invokes_tool(tmp_path):
    """ToolExecutor.execute() successfully invokes a tool."""
    from tinycua_sdk import Agent, LanguageModel
    from tinycua_sdk.agent.executor import ToolExecutor

    from tinycua.agent.tools.native.context import bind_workspace
    from tinycua.agent.tools.native.files import write_file

    agent = Agent(llm_model=LanguageModel())

    bind_workspace(tmp_path)
    try:
        result = await ToolExecutor.execute(
            write_file,
            {"path": "executor_test.txt", "content": "executor test"},
            agent,
        )
    finally:
        bind_workspace(None)

    assert result["success"] is True
    assert (tmp_path / "executor_test.txt").exists()
