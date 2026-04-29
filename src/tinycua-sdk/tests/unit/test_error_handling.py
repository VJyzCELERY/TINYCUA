"""Tests for tool error handling in executor."""

import pytest

from tinycua_sdk.agent.executor import ToolExecutor
from tinycua_sdk.tools.decorators import Tool


class TestToolErrorHandling:
    """Tests for tool error handling in ToolExecutor."""

    def test_executor_success(self):
        """ToolExecutor handles successful tool execution."""
        executor = ToolExecutor()

        tool = Tool(
            name="test_tool",
            description="A test tool",
            _fn=lambda: "success",
        )

        result = executor.execute("test_tool", tool)
        assert result["success"] is True
        assert result["result"] == "success"
        assert result["tool_name"] == "test_tool"

    def test_executor_handles_execution_error(self):
        """ToolExecutor handles tool execution errors gracefully."""
        executor = ToolExecutor()

        def failing_fn():
            raise RuntimeError("Tool execution failed")

        tool = Tool(
            name="failing_tool",
            description="A failing tool",
            _fn=failing_fn,
        )

        result = executor.execute("failing_tool", tool)
        assert result["success"] is False
        assert "error" in result
        assert result["tool_name"] == "failing_tool"
        assert "ref_id" in result

    def test_executor_handles_value_error(self):
        """ToolExecutor handles ValueError from tool."""
        executor = ToolExecutor()

        tool = Tool(
            name="value_error_tool",
            description="Raises ValueError",
            _fn=lambda: (_ for _ in ()).throw(ValueError("invalid value")),
        )

        result = executor.execute("value_error_tool", tool)
        assert result["success"] is False
        assert result["tool_name"] == "value_error_tool"

    def test_executor_handles_type_error(self):
        """ToolExecutor handles TypeError from tool."""
        executor = ToolExecutor()

        def bad_fn():
            raise TypeError("bad type")

        tool = Tool(
            name="type_error_tool",
            description="Raises TypeError",
            _fn=bad_fn,
        )

        result = executor.execute("type_error_tool", tool)
        assert result["success"] is False
        assert result["tool_name"] == "type_error_tool"

    def test_executor_tool_error_recovery(self):
        """ToolExecutor returns error dict without raising."""
        executor = ToolExecutor()

        call_count = 0

        def recovered_fn():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("First call fails")
            return "recovered"

        tool = Tool(
            name="recovered_tool",
            description="Recovers after first failure",
            _fn=recovered_fn,
        )

        result1 = executor.execute("recovered_tool", tool)
        assert result1["success"] is False
        assert call_count == 1

        result2 = executor.execute("recovered_tool", tool)
        assert result2["success"] is True
        assert result2["result"] == "recovered"
        assert call_count == 2

    def test_executor_with_arguments(self):
        """ToolExecutor passes arguments to tool."""
        executor = ToolExecutor()

        tool = Tool(
            name="adder",
            description="Adds two numbers",
            _fn=lambda x, y: x + y,
        )

        result = executor.execute("adder", tool, {"x": 2, "y": 3})
        assert result["success"] is True
        assert result["result"] == 5

    @pytest.mark.asyncio
    async def test_executor_async_success(self):
        """ToolExecutor.execute_async handles successful execution."""
        executor = ToolExecutor()

        async def async_fn():
            return "async result"

        tool = Tool(
            name="async_tool",
            description="An async tool",
            _fn=async_fn,
        )

        result = await executor.execute_async("async_tool", tool)
        assert result["success"] is True
        assert result["result"] == "async result"

    @pytest.mark.asyncio
    async def test_executor_async_error(self):
        """ToolExecutor.execute_async handles errors."""
        executor = ToolExecutor()

        async def async_fail():
            raise RuntimeError("async failure")

        tool = Tool(
            name="async_fail_tool",
            description="Fails asynchronously",
            _fn=async_fail,
        )

        result = await executor.execute_async("async_fail_tool", tool)
        assert result["success"] is False
        assert result["tool_name"] == "async_fail_tool"
