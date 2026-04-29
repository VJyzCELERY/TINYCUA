"""Tests for BaseLoop behavior and resolve_loop."""

import pytest


class TestBaseLoop:
    """Tests for BaseLoop class."""

    def test_base_loop_default_construction(self):
        """BaseLoop defaults to reasonable max_iterations."""
        from tinycua_sdk import BaseLoop

        loop = BaseLoop()
        assert loop.max_iterations == 5

    def test_base_loop_custom_max_iterations(self):
        """BaseLoop accepts custom max_iterations."""
        from tinycua_sdk import BaseLoop

        loop = BaseLoop(max_iterations=10)
        assert loop.max_iterations == 10

    def test_base_loop_extensible(self):
        """BaseLoop can be subclassed for custom behavior."""
        from tinycua_sdk import BaseLoop

        class CustomLoop(BaseLoop):
            async def run(self, agent, messages, tools):
                return "Custom result"

        loop = CustomLoop()
        assert loop.max_iterations == 5


class TestResolveLoop:
    """Tests for resolve_loop function."""

    def test_resolve_loop_none(self):
        """resolve_loop(None) returns a BaseLoop instance."""
        from tinycua_sdk.agent.loop import resolve_loop

        loop = resolve_loop(None)
        from tinycua_sdk import BaseLoop

        assert isinstance(loop, BaseLoop)

    def test_resolve_loop_instance_passthrough(self):
        """resolve_loop(BaseLoop()) returns the same instance."""
        from tinycua_sdk import BaseLoop
        from tinycua_sdk.agent.loop import resolve_loop

        original = BaseLoop()
        resolved = resolve_loop(original)
        assert resolved is original

    def test_resolve_loop_rejects_react_string(self):
        """resolve_loop('react') raises ValueError."""
        from tinycua_sdk.agent.loop import resolve_loop

        with pytest.raises(ValueError):
            resolve_loop("react")

    def test_resolve_loop_dict(self):
        """resolve_loop accepts a dict with max_iterations."""
        from tinycua_sdk.agent.loop import resolve_loop
        from tinycua_sdk import BaseLoop

        loop = resolve_loop({"max_iterations": 7})
        assert isinstance(loop, BaseLoop)
        assert loop.max_iterations == 7
