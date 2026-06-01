"""Integration tests verifying tools work through the SDK's ToolExecutor."""

import os
import tempfile

import pytest


def test_tool_registers_with_agent():
    """All seven tools can be registered with an SDK Agent."""
    from tinycua_sdk.tools.decorators import Tool
    from tinycua.agent.tools.native.shell import run_shell
    from tinycua.agent.tools.native.files import read_file, write_file, list_files, edit_file
    from tinycua.agent.tools.native.web import fetch_url
    from tinycua.agent.tools.native.python_exec import run_python

    tools = [run_shell, read_file, write_file, list_files, fetch_url, run_python, edit_file]
    for tool_func in tools:
        assert isinstance(tool_func, Tool), f"{tool_func.name} should be a Tool instance"
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
async def test_tool_executor_invokes_tool():
    """ToolExecutor.execute() successfully invokes a tool."""
    from tinycua_sdk import Agent, LanguageModel
    from tinycua_sdk.agent.executor import ToolExecutor
    from tinycua.agent.tools.native.files import write_file

    agent = Agent(llm_model=LanguageModel())

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "executor_test.txt")
        result = await ToolExecutor.execute(
            write_file,
            {"path": filepath, "content": "executor test"},
            agent,
        )
        assert result["success"] is True
        assert os.path.exists(filepath)
