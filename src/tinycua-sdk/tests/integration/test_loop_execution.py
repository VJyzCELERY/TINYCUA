"""Integration tests for Loop execution."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from tinycua_sdk.agent.loop import BaseLoop, DefaultLoop, resolve_loop


class TestLoopExecution:
    """Integration tests for loop execution."""

    def test_base_loop_init(self):
        """Test BaseLoop initializes correctly."""
        loop = BaseLoop()
        assert loop is not None
        assert loop.runner is None

    def test_loop_with_runner_integration(self):
        """Test loop with runner integration."""
        mock_runner = MagicMock()
        mock_runner.execute = AsyncMock(return_value="executed")

        loop = BaseLoop(runner=mock_runner)
        assert loop.runner is mock_runner

    def test_resolve_loop_from_config_dict(self):
        """Test resolve_loop handles full config dict."""
        config = {
            "max_iterations": 10,
        }
        loop = resolve_loop(config)
        assert isinstance(loop, BaseLoop)
        assert loop.max_iterations == 10

    def test_default_loop_alias(self):
        """Test DefaultLoop is alias for BaseLoop."""
        assert DefaultLoop is BaseLoop

    def test_loop_state_transitions(self):
        """Test loop handles state transitions."""
        loop = BaseLoop()
        assert loop.max_iterations == 5

    def test_loop_with_custom_runner(self):
        """Test loop with custom runner implementation."""
        class CustomRunner:
            def __init__(self):
                self.executions = 0

        runner = CustomRunner()
        loop = BaseLoop(runner=runner)
        assert loop.runner is runner


class TestLoopErrorHandling:
    """Integration tests for loop error handling."""

    def test_resolve_loop_invalid_string_error(self):
        """Test resolve_loop raises on invalid string."""
        with pytest.raises(ValueError) as exc_info:
            resolve_loop("invalid_loop_type")
        assert "String loop configuration is not supported" in str(exc_info.value)

    def test_resolve_loop_case_insensitive_default(self):
        """Test resolve_loop rejects strings regardless of case."""
        with pytest.raises(ValueError):
            resolve_loop("default")
        with pytest.raises(ValueError):
            resolve_loop("DEFAULT")

    def test_resolve_loop_with_invalid_dict(self):
        """Test resolve_loop ignores unknown type in dict and returns BaseLoop."""
        loop = resolve_loop({"type": "invalid", "max_iterations": 3})
        assert isinstance(loop, BaseLoop)
        assert loop.max_iterations == 3


class TestLoopPerformance:
    """Integration tests for loop performance."""

    def test_multiple_loop_creation(self):
        """Test creating multiple loops is efficient."""
        loops = [BaseLoop() for _ in range(100)]
        assert len(loops) == 100

    def test_resolve_loop_caching(self):
        """Test resolve_loop returns same instances for same types."""
        loop1 = resolve_loop(None)
        loop2 = resolve_loop(None)

        assert type(loop1) == type(loop2)
