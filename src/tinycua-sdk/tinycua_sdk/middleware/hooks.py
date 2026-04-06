"""Middleware and hooks system."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from tinycua_sdk.storage.models import Message


@dataclass
class HookContext:
    """Context passed to hooks.

    Attributes:
        tool_name: Name of the tool being called
        parameters: Tool call parameters
        session_id: Session ID if available
        messages: Current message list
    """

    tool_name: str
    parameters: dict[str, Any]
    session_id: uuid.UUID | None = None
    messages: list[Message] = field(default_factory=list)


@dataclass
class HookResult:
    """Result from hook execution.

    Attributes:
        modified: Whether the hook modified the context
        parameters: Modified parameters (for pre-hooks)
        result: Modified result (for post-hooks)
        error: Error message if hook failed
    """

    modified: bool = False
    parameters: dict[str, Any] | None = None
    result: Any = None
    error: str | None = None


class HookError(Exception):
    """Raised when hook execution fails."""

    pass


class Hook:
    """Base hook class.

    Subclass this to implement custom hooks that execute
    before or after tool calls.
    """

    def pre_call(self, context: HookContext) -> HookResult:
        """Execute before tool call.

        Args:
            context: Hook context

        Returns:
            Hook result (can modify parameters)

        Raises:
            HookError: If hook execution fails
        """
        return HookResult(modified=False, parameters=None, result=None, error=None)

    def post_call(self, context: HookContext, result: Any) -> HookResult:
        """Execute after tool call.

        Args:
            context: Hook context
            result: Tool execution result

        Returns:
            Hook result (can modify result)

        Raises:
            HookError: If hook execution fails
        """
        return HookResult(modified=False, parameters=None, result=result, error=None)


class HookRegistry:
    """Registry for managing hooks.

    Manages pre and post hooks with priority ordering.
    """

    def __init__(self):
        """Initialize the registry."""
        self._pre_hooks: list[tuple[int, Hook]] = []
        self._post_hooks: list[tuple[int, Hook]] = []

    def register_pre_hook(self, hook: Hook, priority: int = 100) -> None:
        """Register a pre-call hook.

        Args:
            hook: Hook instance
            priority: Execution priority (lower runs first)
        """
        self._pre_hooks.append((priority, hook))
        self._pre_hooks.sort(key=lambda x: x[0])

    def register_post_hook(self, hook: Hook, priority: int = 100) -> None:
        """Register a post-call hook.

        Args:
            hook: Hook instance
            priority: Execution priority (lower runs first)
        """
        self._post_hooks.append((priority, hook))
        self._post_hooks.sort(key=lambda x: x[0])

    def execute_pre_hooks(self, context: HookContext) -> HookContext:
        """Execute all pre-call hooks in priority order.

        Args:
            context: Initial context

        Returns:
            Modified context

        Raises:
            HookError: If any hook fails
        """
        for _, hook in self._pre_hooks:
            try:
                result = hook.pre_call(context)

                if result.error:
                    raise HookError(f"Pre-hook error: {result.error}")

                # Apply modifications
                if result.modified and result.parameters is not None:
                    context.parameters = result.parameters

            except HookError:
                raise
            except Exception as e:
                raise HookError(f"Pre-hook failed: {e}")

        return context

    def execute_post_hooks(
        self,
        context: HookContext,
        result: Any,
    ) -> Any:
        """Execute all post-call hooks in priority order.

        Args:
            context: Hook context
            result: Tool result

        Returns:
            Modified result

        Raises:
            HookError: If any hook fails
        """
        for _, hook in self._post_hooks:
            try:
                hook_result = hook.post_call(context, result)

                if hook_result.error:
                    raise HookError(f"Post-hook error: {hook_result.error}")

                # Apply modifications
                if hook_result.modified and hook_result.result is not None:
                    result = hook_result.result

            except HookError:
                raise
            except Exception as e:
                raise HookError(f"Post-hook failed: {e}")

        return result

    def clear(self) -> None:
        """Clear all registered hooks."""
        self._pre_hooks.clear()
        self._post_hooks.clear()

    @property
    def pre_hook_count(self) -> int:
        """Get number of registered pre-hooks."""
        return len(self._pre_hooks)

    @property
    def post_hook_count(self) -> int:
        """Get number of registered post-hooks."""
        return len(self._post_hooks)
