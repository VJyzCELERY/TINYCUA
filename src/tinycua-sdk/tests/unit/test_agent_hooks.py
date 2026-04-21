"""Unit tests for agent hooks."""

import pytest
from tinycua_sdk.agent.hooks import HookManager, HookConfig


class TestHookManager:
    """Tests for HookManager class."""

    def test_hook_manager_init(self):
        """HookManager initializes empty."""
        manager = HookManager()
        assert manager.pre_hook_count == 0
        assert manager.post_hook_count == 0

    def test_add_pre_hook(self):
        """Can add pre-execution hooks."""
        manager = HookManager()

        async def my_hook(context):
            return context

        manager.add_pre_hook(my_hook, order=10)
        assert manager.pre_hook_count == 1

    def test_add_post_hook(self):
        """Can add post-execution hooks."""
        manager = HookManager()

        async def my_hook(context):
            return context

        manager.add_post_hook(my_hook, order=10)
        assert manager.post_hook_count == 1

    def test_pre_hooks_execute_in_order(self):
        """Pre-hooks execute in order (lowest order first)."""
        manager = HookManager()
        execution_order = []

        async def hook1(context):
            execution_order.append(1)
            return context

        async def hook2(context):
            execution_order.append(2)
            return context

        manager.add_pre_hook(hook2, order=20)
        manager.add_pre_hook(hook1, order=10)

        import asyncio
        asyncio.run(manager.execute_pre_hooks({}))

        assert execution_order == [1, 2]

    def test_post_hooks_execute_in_order(self):
        """Post-hooks execute in order (lowest order first)."""
        manager = HookManager()
        execution_order = []

        async def hook1(context):
            execution_order.append(1)
            return context

        async def hook2(context):
            execution_order.append(2)
            return context

        manager.add_post_hook(hook2, order=20)
        manager.add_post_hook(hook1, order=10)

        import asyncio
        asyncio.run(manager.execute_post_hooks({}))

        assert execution_order == [1, 2]

    def test_clear_pre_hooks(self):
        """Can clear pre-hooks."""
        manager = HookManager()

        async def my_hook(context):
            return context

        manager.add_pre_hook(my_hook)
        manager.clear_pre_hooks()
        assert manager.pre_hook_count == 0

    def test_clear_post_hooks(self):
        """Can clear post-hooks."""
        manager = HookManager()

        async def my_hook(context):
            return context

        manager.add_post_hook(my_hook)
        manager.clear_post_hooks()
        assert manager.post_hook_count == 0

    def test_clear_all(self):
        """Can clear all hooks."""
        manager = HookManager()

        async def my_hook(context):
            return context

        manager.add_pre_hook(my_hook)
        manager.add_post_hook(my_hook)
        manager.clear_all()
        assert manager.pre_hook_count == 0
        assert manager.post_hook_count == 0

    def test_hook_modifies_context(self):
        """Hook can modify execution context."""
        manager = HookManager()

        async def modify_hook(context):
            context["modified"] = True
            return context

        manager.add_pre_hook(modify_hook)

        import asyncio
        result = asyncio.run(manager.execute_pre_hooks({}))

        assert result["modified"] is True

    def test_hook_with_name(self):
        """Hook can have a custom name."""
        manager = HookManager()

        async def my_hook(context):
            return context

        manager.add_pre_hook(my_hook, name="custom_name")
        assert manager._pre_hooks[0].name == "custom_name"


class TestHookConfig:
    """Tests for HookConfig dataclass."""

    def test_hook_config_defaults(self):
        """HookConfig has sensible defaults."""

        async def my_func(context):
            return context

        config = HookConfig(func=my_func)
        assert config.order == 0
        assert config.name is None
        assert config.enabled is True

    def test_hook_config_disabled(self):
        """Disabled hooks don't execute."""

        async def my_func(context):
            context["executed"] = True
            return context

        config = HookConfig(func=my_func, enabled=False)
        import asyncio
        result = asyncio.run(config.execute({}))

        assert "executed" not in result
