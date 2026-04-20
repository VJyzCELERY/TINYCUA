"""Tests for built-in loop types."""

import pytest
from unittest.mock import MagicMock

from tinycua_sdk.agent.loop import (
    BaseLoop,
    DefaultLoop,
    ReactLoop,
    resolve_loop,
)


class TestReactLoop:
    """Test ReactLoop class."""

    def test_react_loop_init(self):
        """ReactLoop initializes with default max_iterations."""
        loop = ReactLoop()
        assert loop is not None
        assert loop.max_iterations == 5

    def test_react_loop_custom_max(self):
        """ReactLoop accepts custom max_iterations."""
        loop = ReactLoop(max_iterations=10)
        assert loop.max_iterations == 10

    def test_react_loop_with_runner(self):
        """ReactLoop accepts runner."""
        mock_runner = MagicMock()
        loop = ReactLoop(runner=mock_runner)
        assert loop.runner is mock_runner


class TestResolveLoop:
    """Test resolve_loop function."""

    def test_resolve_loop_default_string(self):
        """resolve_loop('default') returns DefaultLoop."""
        loop = resolve_loop("default")
        assert isinstance(loop, DefaultLoop)

    def test_resolve_loop_react_string(self):
        """resolve_loop('react') returns ReactLoop."""
        loop = resolve_loop("react")
        assert isinstance(loop, ReactLoop)

    def test_resolve_loop_dict_default(self):
        """resolve_loop({type: 'default'}) returns DefaultLoop."""
        loop = resolve_loop({"type": "default"})
        assert isinstance(loop, DefaultLoop)

    def test_resolve_loop_dict_react(self):
        """resolve_loop({type: 'react', max_iterations: 3}) returns ReactLoop."""
        loop = resolve_loop({"type": "react", "max_iterations": 3})
        assert isinstance(loop, ReactLoop)
        assert loop.max_iterations == 3

    def test_resolve_loop_none(self):
        """resolve_loop(None) returns DefaultLoop."""
        loop = resolve_loop(None)
        assert isinstance(loop, DefaultLoop)

    def test_resolve_loop_instance(self):
        """resolve_loop(DefaultLoop()) returns same instance."""
        original_loop = DefaultLoop()
        loop = resolve_loop(original_loop)
        assert loop is original_loop

    def test_resolve_loop_invalid_type(self):
        """resolve_loop('invalid') raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            resolve_loop("invalid")
        assert "Invalid loop type" in str(exc_info.value)

    def test_resolve_loop_case_insensitive(self):
        """resolve_loop is case insensitive."""
        loop = resolve_loop("DEFAULT")
        assert isinstance(loop, DefaultLoop)
        loop = resolve_loop("React")
        assert isinstance(loop, ReactLoop)

    def test_resolve_loop_empty_dict(self):
        """resolve_loop({}) returns DefaultLoop."""
        loop = resolve_loop({})
        assert isinstance(loop, DefaultLoop)
