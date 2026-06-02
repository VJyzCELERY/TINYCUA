"""Unit tests for ToolResult model."""

from __future__ import annotations

import json

from tinycua.tools.result import ToolResult


def test_tool_result_defaults():
    """ToolResult has correct default values."""
    result = ToolResult(success=True, output="hello")
    assert result.success is True
    assert result.output == "hello"
    assert result.error is None
    assert result.metadata is None
    assert result.duration == 0.0


def test_tool_result_all_fields():
    """ToolResult accepts all fields explicitly."""
    result = ToolResult(
        success=False,
        output="",
        error="something went wrong",
        metadata={"exit_code": 1},
        duration=2.5,
    )
    assert result.success is False
    assert result.output == ""
    assert result.error == "something went wrong"
    assert result.metadata == {"exit_code": 1}
    assert result.duration == 2.5


def test_tool_result_to_dict():
    """to_dict returns a JSON-serializable dict."""
    result = ToolResult(
        success=True,
        output="test",
        metadata={"key": "value"},
        duration=1.0,
    )
    d = result.to_dict()
    assert isinstance(d, dict)
    assert d["success"] is True
    assert d["output"] == "test"
    assert d["error"] is None
    assert d["metadata"] == {"key": "value"}
    assert d["duration"] == 1.0


def test_tool_result_to_dict_json_serializable():
    """to_dict output can be serialized to JSON."""
    result = ToolResult(
        success=True,
        output="test",
        metadata={"nested": {"a": 1}},
        duration=0.5,
    )
    json_str = json.dumps(result.to_dict())
    assert json_str is not None
    parsed = json.loads(json_str)
    assert parsed["success"] is True
    assert parsed["metadata"]["nested"]["a"] == 1


def test_tool_result_with_none_metadata():
    """to_dict handles None metadata correctly."""
    result = ToolResult(success=True, output="ok")
    d = result.to_dict()
    assert d["metadata"] is None
