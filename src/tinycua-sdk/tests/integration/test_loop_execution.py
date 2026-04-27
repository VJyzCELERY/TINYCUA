"""Integration tests for Loop execution."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from tinycua_sdk.agent.loop import BaseLoop, ReactLoop, DefaultLoop, resolve_loop


class TestLoopExecution:
    """Integration tests for loop execution."""

    def test_base_loop_init(self):
        """Test BaseLoop initializes correctly."""
        loop = BaseLoop()
        assert loop is not None
        assert loop.runner is None

    def test_react_loop_with_max_iterations(self):
        """Test ReactLoop respects max_iterations."""
        loop = ReactLoop(max_iterations=3)
        assert loop.max_iterations == 3

    def test_loop_with_runner_integration(self):
        """Test loop with runner integration."""
        mock_runner = MagicMock()
        mock_runner.execute = AsyncMock(return_value="executed")

        loop = BaseLoop(runner=mock_runner)
        assert loop.runner is mock_runner

    def test_resolve_loop_from_config_dict(self):
        """Test resolve_loop handles full config dict."""
        config = {
            "type": "react",
            "max_iterations": 10,
        }
        loop = resolve_loop(config)
        assert isinstance(loop, ReactLoop)
        assert loop.max_iterations == 10

    def test_default_loop_alias(self):
        """Test DefaultLoop is alias for BaseLoop."""
        assert DefaultLoop is BaseLoop

    def test_loop_state_transitions(self):
        """Test loop handles state transitions."""
        loop = ReactLoop()

        assert loop.max_iterations == 5

    def test_loop_with_custom_runner(self):
        """Test loop with custom runner implementation."""
        class CustomRunner:
            def __init__(self):
                self.executions = 0

        runner = CustomRunner()
        loop = ReactLoop(runner=runner)
        assert loop.runner is runner


class TestLoopErrorHandling:
    """Integration tests for loop error handling."""

    def test_resolve_loop_invalid_type_error(self):
        """Test resolve_loop raises on invalid type."""
        with pytest.raises(ValueError) as exc_info:
            resolve_loop("invalid_loop_type")
        assert "Invalid loop type" in str(exc_info.value)

    def test_resolve_loop_case_insensitive(self):
        """Test resolve_loop is case insensitive."""
        loop_lower = resolve_loop("react")
        loop_upper = resolve_loop("REACT")
        loop_mixed = resolve_loop("React")

        assert isinstance(loop_lower, ReactLoop)
        assert isinstance(loop_upper, ReactLoop)
        assert isinstance(loop_mixed, ReactLoop)

    def test_resolve_loop_with_invalid_dict(self):
        """Test resolve_loop raises ValueError for invalid dict."""
        with pytest.raises(ValueError):
            resolve_loop({"type": "invalid"})


class TestLoopPerformance:
    """Integration tests for loop performance."""

    def test_multiple_loop_creation(self):
        """Test creating multiple loops is efficient."""
        loops = [ReactLoop() for _ in range(100)]
        assert len(loops) == 100

    def test_resolve_loop_caching(self):
        """Test resolve_loop returns same instances for same types."""
        loop1 = resolve_loop("react")
        loop2 = resolve_loop("react")

        assert type(loop1) == type(loop2)