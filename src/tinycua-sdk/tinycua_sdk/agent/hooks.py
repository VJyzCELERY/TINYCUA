"""Hook system for agent loop customization."""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


class Hook:
    """Base interface for agent loop hooks.

    Hooks are async functions that receive a context dict and
    return a modified context dict. They can be used to modify
    behavior before or after agent execution.

    Example:
        async def my_hook(context: dict[str, Any]) -> dict[str, Any]:
            context["start_time"] = __import__("time").time()
            return context
    """

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute hook with context.

        Args:
            context: Execution context passed through hooks.

        Returns:
            Modified context after hook execution.
        """
        ...


HookFunc = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class HookConfig:
    """Configuration for a hook.

    Attributes:
        func: Async callable hook function
        order: Execution order (lower values execute first)
        name: Optional name for debugging
        enabled: Whether hook is active
    """

    func: HookFunc
    order: int = 0
    name: str | None = None
    enabled: bool = True

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the hook function.

        Args:
            context: Execution context.

        Returns:
            Modified context.
        """
        if self.enabled:
            return await self.func(context)
        return context


class HookManager:
    """Manages pre and post execution hooks for agent loops.

    Hooks are executed in order (lowest order first) before and after
    the main agent execution loop.

    Example:
        hook_manager = HookManager()

        async def my_pre_hook(context):
            context["start_time"] = time.time()
            return context

        hook_manager.add_pre_hook(my_pre_hook, order=10)
    """

    def __init__(self):
        """Initialize empty hook manager."""
        self._pre_hooks: list[HookConfig] = []
        self._post_hooks: list[HookConfig] = []

    def add_pre_hook(
        self,
        func: HookFunc,
        order: int = 0,
        name: str | None = None,
    ) -> None:
        """Add a pre-execution hook.

        Pre-execution hooks run before the main agent loop.

        Args:
            func: Async callable that accepts context dict and returns modified context
            order: Execution order (lower values execute first)
            name: Optional name for debugging/identification
        """
        config = HookConfig(func=func, order=order, name=name or func.__name__)
        self._pre_hooks.append(config)
        self._pre_hooks.sort(key=lambda h: h.order)

    def add_post_hook(
        self,
        func: HookFunc,
        order: int = 0,
        name: str | None = None,
    ) -> None:
        """Add a post-execution hook.

        Post-execution hooks run after the main agent loop.

        Args:
            func: Async callable that accepts context dict and returns modified context
            order: Execution order (lower values execute first)
            name: Optional name for debugging/identification
        """
        config = HookConfig(func=func, order=order, name=name or func.__name__)
        self._post_hooks.append(config)
        self._post_hooks.sort(key=lambda h: h.order)

    async def execute_pre_hooks(
        self, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute all pre-execution hooks in order.

        Args:
            context: Initial execution context.

        Returns:
            Context after all pre-hooks have run.
        """
        for hook in self._pre_hooks:
            context = await hook.execute(context)
        return context

    async def execute_post_hooks(
        self, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute all post-execution hooks in order.

        Args:
            context: Execution context after agent loop.

        Returns:
            Context after all post-hooks have run.
        """
        for hook in self._post_hooks:
            context = await hook.execute(context)
        return context

    def clear_pre_hooks(self) -> None:
        """Remove all pre-execution hooks."""
        self._pre_hooks.clear()

    def clear_post_hooks(self) -> None:
        """Remove all post-execution hooks."""
        self._post_hooks.clear()

    def clear_all(self) -> None:
        """Remove all hooks."""
        self.clear_pre_hooks()
        self.clear_post_hooks()

    @property
    def pre_hook_count(self) -> int:
        """Return number of registered pre-hooks."""
        return len(self._pre_hooks)

    @property
    def post_hook_count(self) -> int:
        """Return number of registered post-hooks."""
        return len(self._post_hooks)


__all__ = ["Hook", "HookFunc", "HookConfig", "HookManager"]
