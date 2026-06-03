"""Integration tests verifying tools work through the SDK's ToolExecutor."""

import pytest


def test_tool_registers_with_agent():
    """All seven tools can be registered with an SDK Agent."""
    from tinycua_sdk.tools.decorators import Tool
    from tinycua.tools.native.shell import run_shell
    from tinycua.tools.native.files import read_file, write_file, list_files, edit_file
    from tinycua.tools.native.web import fetch_url
    from tinycua.tools.native.python_exec import run_python

    tools = [run_shell, read_file, write_file, list_files, fetch_url, run_python, edit_file]
    for tool_func in tools:
        assert isinstance(tool_func, Tool), f"{tool_func.name} should be a Tool instance"
    assert all(hasattr(t, "name") and hasattr(t, "parameters") for t in tools)


def test_tool_schemas_valid_json_schema():
    """Each tool generates valid JSON Schema for function calling."""
    from tinycua.tools.native.shell import run_shell
    from tinycua.tools.native.files import read_file, write_file

    for tool in [run_shell, read_file, write_file]:
        params = tool.parameters
        assert params["type"] == "object"
        assert "properties" in params
        for prop in params["properties"].values():
            assert "type" in prop


def test_tool_schemas_correct_types():
    """Tool schemas declare correct types for numeric and object parameters."""
    from tinycua.tools.native.shell import run_shell
    from tinycua.tools.native.files import read_file
    from tinycua.tools.native.web import fetch_url

    # run_shell: timeout should be number (int)
    timeout_type = run_shell.parameters["properties"]["timeout"]["type"]
    assert timeout_type == "number", f"run_shell.timeout type should be 'number', got '{timeout_type}'"

    # read_file: start and offset should be number (int)
    start_type = read_file.parameters["properties"]["start"]["type"]
    assert start_type == "number", f"read_file.start type should be 'number', got '{start_type}'"
    offset_type = read_file.parameters["properties"]["offset"]["type"]
    assert offset_type == "number", f"read_file.offset type should be 'number', got '{offset_type}'"

    # fetch_url: timeout and max_size should be number (int)
    fetch_timeout_type = fetch_url.parameters["properties"]["timeout"]["type"]
    assert fetch_timeout_type == "number", f"fetch_url.timeout type should be 'number', got '{fetch_timeout_type}'"
    max_size_type = fetch_url.parameters["properties"]["max_size"]["type"]
    assert max_size_type == "number", f"fetch_url.max_size type should be 'number', got '{max_size_type}'"

    # fetch_url: headers should be object (dict)
    headers_type = fetch_url.parameters["properties"]["headers"]["type"]
    assert headers_type == "object", f"fetch_url.headers type should be 'object', got '{headers_type}'"


@pytest.mark.asyncio
async def test_tool_executor_invokes_tool(tmp_path):
    """ToolExecutor.execute() successfully invokes a tool."""
    from tinycua_sdk import Agent, LanguageModel
    from tinycua_sdk.agent.executor import ToolExecutor
    from tinycua.tools.native.files import write_file

    agent = Agent(llm_model=LanguageModel())

    filepath = tmp_path / "executor_test.txt"
    result = await ToolExecutor.execute(
        write_file,
        {"path": str(filepath), "content": "executor test"},
        agent,
    )
    assert result["success"] is True
    assert filepath.exists()
