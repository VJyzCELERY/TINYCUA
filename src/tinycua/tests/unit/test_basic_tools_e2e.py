"""Integration tests for M1 Basic Tools — end-to-end through the SDK."""

from __future__ import annotations

from tinycua_sdk.tools.decorators import Tool


def test_tool_result_model_importable():
    """ToolResult is importable from tinycua.tools and has all required fields."""
    from tinycua.tools.result import ToolResult

    result = ToolResult(success=True, output="hello")
    assert result.success is True
    assert result.output == "hello"
    assert result.error is None
    assert isinstance(result.metadata, dict) or result.metadata is None
    assert isinstance(result.duration, float)


def test_all_native_tools_register_with_agent():
    """All M1 native tools can be registered with an SDK Agent as Tool instances."""
    from tinycua.tools.native.files import list_files, read_file, write_file
    from tinycua.tools.native.python_exec import run_python
    from tinycua.tools.native.shell import run_shell
    from tinycua.tools.native.web import fetch_url

    tools = [
        run_shell,
        read_file,
        write_file,
        list_files,
        fetch_url,
        run_python,
    ]
    for t in tools:
        assert isinstance(t, Tool), f"{t.name} should be a Tool instance"
    assert all(hasattr(t, "name") and hasattr(t, "parameters") for t in tools)


def test_native_tools_integration(tmp_path):
    """Native execution tools work and return structured results."""
    from tinycua.tools.native.files import list_files, read_file, write_file
    from tinycua.tools.native.python_exec import run_python
    from tinycua.tools.native.shell import run_shell

    # File tools
    test_file = tmp_path / "test_m1_integration.txt"
    result = write_file(path=str(test_file), content="hello world")
    assert result["success"] is True

    content = read_file(path=str(test_file))
    assert "hello world" in content

    # list_files
    files = list_files(path=str(tmp_path), pattern="*.txt")
    assert str(test_file) in files

    # Shell execution
    shell_result = run_shell(command="echo hello")
    assert shell_result["exit_code"] == 0
    assert "hello" in shell_result["stdout"]

    # Python execution
    py_result = run_python(code="print('hello')")
    assert py_result["exit_code"] == 0
    assert "hello" in py_result["stdout"]


def test_native_tools_integration_fetch_url():
    """HTTP fetch tool works with mocked response."""
    from unittest.mock import MagicMock, patch

    from tinycua.tools.native.web import fetch_url

    with patch("tinycua.tools.native.web.httpx.Client") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "hello from web"
        mock_response.content = b"hello from web"
        mock_client.return_value.__enter__.return_value.request.return_value = (
            mock_response
        )
        url_result = fetch_url(url="http://example.com")
        assert "hello from web" in url_result


def test_tool_result_to_dict():
    """ToolResult has a to_dict method for JSON serialization."""
    from tinycua.tools.result import ToolResult

    result = ToolResult(
        success=True,
        output="test output",
        metadata={"exit_code": 0},
        duration=1.5,
    )
    d = result.to_dict()
    assert d["success"] is True
    assert d["output"] == "test output"
    assert d["error"] is None
    assert d["metadata"] == {"exit_code": 0}
    assert d["duration"] == 1.5


def test_tool_constants_importable():
    """NATIVE_BASE_TOOLS is importable and contains the six native tools."""
    from tinycua.constants.tools import NATIVE_BASE_TOOLS

    assert len(NATIVE_BASE_TOOLS) == 6
    tool_names = [t.name for t in NATIVE_BASE_TOOLS]
    assert "run_shell" in tool_names
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "list_files" in tool_names
    assert "fetch_url" in tool_names
    assert "run_python" in tool_names
