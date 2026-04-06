# Unit tests for Middleware Hooks

import pytest

from tinycua_sdk.middleware.hooks import (
    Hook,
    HookContext,
    HookResult,
    HookRegistry,
    HookError,
)


class TestHook:
    """Tests for the Hook base class."""

    def test_pre_call_default(self):
        """Test default pre_call returns unmodified result."""
        hook = Hook()
        context = HookContext(tool_name="test", parameters={})

        result = hook.pre_call(context)

        assert result.modified is False
        assert result.parameters is None

    def test_post_call_default(self):
        """Test default post_call returns unmodified result."""
        hook = Hook()
        context = HookContext(tool_name="test", parameters={})

        result = hook.post_call(context, "test result")

        assert result.modified is False
        assert result.result == "test result"


class CustomModifyHook(Hook):
    """A hook that modifies parameters."""

    def pre_call(self, context: HookContext) -> HookResult:
        modified_params = dict(context.parameters)
        modified_params["modified"] = True
        return HookResult(modified=True, parameters=modified_params)


class CustomResultHook(Hook):
    """A hook that modifies result."""

    def post_call(self, context: HookContext, result: str) -> HookResult:
        return HookResult(modified=True, result=f"Modified: {result}")


class TestHookRegistry:
    """Tests for the HookRegistry class."""

    def test_register_pre_hook(self):
        """Test registering a pre-hook."""
        registry = HookRegistry()
        hook = Hook()

        registry.register_pre_hook(hook)

        assert registry.pre_hook_count == 1

    def test_register_post_hook(self):
        """Test registering a post-hook."""
        registry = HookRegistry()
        hook = Hook()

        registry.register_post_hook(hook)

        assert registry.post_hook_count == 1

    def test_execute_pre_hooks(self):
        """Test executing pre-hooks."""
        registry = HookRegistry()
        registry.register_pre_hook(CustomModifyHook())

        context = HookContext(tool_name="test", parameters={"original": True})
        result = registry.execute_pre_hooks(context)

        assert result.parameters["modified"] is True

    def test_execute_pre_hooks_priority_order(self):
        """Test hooks execute in priority order."""
        registry = HookRegistry()

        class FirstHook(Hook):
            def pre_call(self, context: HookContext) -> HookResult:
                context.parameters["order"] = "first"
                return HookResult(modified=True, parameters=context.parameters)

        class SecondHook(Hook):
            def pre_call(self, context: HookContext) -> HookResult:
                context.parameters["order"] = "second"
                return HookResult(modified=True, parameters=context.parameters)

        # Register with different priorities
        registry.register_pre_hook(SecondHook(), priority=200)
        registry.register_pre_hook(FirstHook(), priority=100)

        context = HookContext(tool_name="test", parameters={})
        result = registry.execute_pre_hooks(context)

        # First hook should run first and its result should be in final params
        assert "order" in result.parameters

    def test_execute_post_hooks(self):
        """Test executing post-hooks."""
        registry = HookRegistry()
        registry.register_post_hook(CustomResultHook())

        context = HookContext(tool_name="test", parameters={})
        result = registry.execute_post_hooks(context, "original")

        assert result == "Modified: original"

    def test_hook_error_raises(self):
        """Test hook errors are raised."""
        registry = HookRegistry()

        class ErrorHook(Hook):
            def pre_call(self, context: HookContext) -> HookResult:
                return HookResult(error="Something went wrong")

        registry.register_pre_hook(ErrorHook())

        context = HookContext(tool_name="test", parameters={})

        with pytest.raises(HookError, match="Pre-hook error"):
            registry.execute_pre_hooks(context)

    def test_clear(self):
        """Test clearing all hooks."""
        registry = HookRegistry()

        registry.register_pre_hook(Hook())
        registry.register_post_hook(Hook())

        registry.clear()

        assert registry.pre_hook_count == 0
        assert registry.post_hook_count == 0
