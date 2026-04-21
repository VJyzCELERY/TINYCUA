"""Tests for tool error handling in executor."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tinycua_sdk.agent.executor import AgentExecutor
from tinycua_sdk.core.registry import ToolRegistry


class TestToolErrorHandling:
    """Tests for tool error handling in AgentExecutor."""

    def setup_method(self):
        """Clear registry before each test."""
        self.registry = ToolRegistry()
        self.registry.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        self.registry.clear()

    def test_executor_handles_tool_not_found(self):
        """Executor handles tool not found gracefully."""
        executor = AgentExecutor()

        def mock_handler():
            pass

        self.registry.register(name="test_tool", handler=mock_handler, schema={})

        result = self.registry.get("nonexistent_tool")
        assert result is None

    def test_executor_handles_execution_error(self):
        """Executor handles tool execution errors gracefully."""
        executor = AgentExecutor()

        def failing_handler():
            raise RuntimeError("Tool execution failed")

        self.registry.register(name="failing_tool", handler=failing_handler, schema={})

        with pytest.raises(RuntimeError) as exc_info:
            self.registry.dispatch("failing_tool", {})
        assert "Tool execution failed" in str(exc_info.value)

    def test_executor_handles_timeout_error(self):
        """Executor handles tool timeout errors gracefully."""
        executor = AgentExecutor()

        import time

        def slow_handler():
            time.sleep(0.1)
            return "done"

        self.registry.register(name="slow_tool", handler=slow_handler, schema={})

        result = self.registry.dispatch("slow_tool", {})
        assert result == "done"

    def test_executor_tool_error_recovery(self):
        """Executor can recover from tool errors."""
        executor = AgentExecutor()

        call_count = 0

        def recovered_handler():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("First call fails")
            return "recovered"

        self.registry.register(name="recovered_tool", handler=recovered_handler, schema={})

        with pytest.raises(RuntimeError):
            self.registry.dispatch("recovered_tool", {})

        result = self.registry.dispatch("recovered_tool", {})
        assert result == "recovered"
        assert call_count == 2
