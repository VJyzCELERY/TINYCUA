"""BaseLoop - Base class for custom agent execution loops."""

from typing import TYPE_CHECKING, Any, AsyncIterator, Union

from tinycua_sdk.agent.hooks import HookManager, HookFunc

if TYPE_CHECKING:
    from tinycua_sdk.agent import Agent
    from tinycua_sdk.models.response import StreamEvent
    from tinycua_sdk.models import RunResult


# Valid built-in loop types
VALID_LOOP_TYPES = {"default"}


def _validate_loop_type(loop_type: str) -> None:
    """Validate loop type string.

    Args:
        loop_type: The loop type to validate

    Raises:
        ValueError: If loop_type is not valid
    """
    if loop_type.lower() not in VALID_LOOP_TYPES:
        raise ValueError(
            f"Invalid loop type '{loop_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_LOOP_TYPES))}"
        )


class BaseLoop:
    """Base class for custom agent execution loops.

    This is the base class used by default for all agents developed with tinycua-sdk.
    Users can extend this class to define custom execution strategies.

    Example:
        class MyLoop(BaseLoop):
            async def run(self, agent, user_input, **kwargs):
                # Custom logic
                return "result"

    Attributes:
        runner: Execution runner for basic execution (set by AgentExecutor)
    """

    def __init__(self, max_iterations: int = 5, runner: Any = None):
        """Initialize with optional runner.

        Runner will be injected by Agent when loop is loaded.

        Args:
            max_iterations: Maximum number of loop iterations.
            runner: Execution runner for basic execution (optional)
        """
        self.max_iterations = max_iterations
        self.runner = runner
        self._hooks = HookManager()

    def add_pre_hook(
        self,
        func: HookFunc,
        order: int = 0,
        name: str | None = None,
    ) -> None:
        """Add a pre-execution hook.

        Pre-execution hooks run before the main agent loop.
        Hooks execute in order (lowest order first).

        Args:
            func: Async callable that accepts context dict and returns modified context
            order: Execution order (lower values execute first)
            name: Optional name for debugging/identification
        """
        self._hooks.add_pre_hook(func, order, name)

    def add_post_hook(
        self,
        func: HookFunc,
        order: int = 0,
        name: str | None = None,
    ) -> None:
        """Add a post-execution hook.

        Post-execution hooks run after the main agent loop.
        Hooks execute in order (lowest order first).

        Args:
            func: Async callable that accepts context dict and returns modified context
            order: Execution order (lower values execute first)
            name: Optional name for debugging/identification
        """
        self._hooks.add_post_hook(func, order, name)

    async def run(
        self,
        agent: "Agent",
        messages: list[dict[str, Any]],
        tools: list[Any],
    ) -> str:
        """Execute the agent loop.

        Override to define custom execution strategy.

        Args:
            agent: The agent being run.
            messages: Full message history including system prompt.
            tools: Tools available to the agent.

        Returns:
            The final response string.
        """
        tool_schemas = [t.to_config() for t in tools] if tools else None
        return await agent._call_llm(messages, tools=tool_schemas)


# Keep DefaultLoop as alias for backwards compatibility
DefaultLoop = BaseLoop


def resolve_loop(loop_config: Any) -> BaseLoop:
    """Resolve loop configuration to a loop instance.

    Args:
        loop_config: Can be:
            - None: returns BaseLoop
            - dict: {max_iterations: 5}
            - BaseLoop instance: returns as-is

    Returns:
        BaseLoop subclass instance

    Raises:
        ValueError: If loop_type is not valid
    """
    if loop_config is None:
        return BaseLoop()

    if isinstance(loop_config, BaseLoop):
        return loop_config

    if isinstance(loop_config, str):
        raise ValueError(
            f"String loop configuration is not supported: {loop_config!r}. "
            "Use a BaseLoop instance or dict with max_iterations."
        )

    if isinstance(loop_config, dict):
        kwargs = {k: v for k, v in loop_config.items() if k != "type"}
        valid_kwargs = {k: v for k, v in kwargs.items() if k in ("max_iterations", "runner")}
        return BaseLoop(**valid_kwargs)

    raise ValueError(
        f"Invalid loop configuration: {loop_config}. "
        "Must be None, dict, or BaseLoop instance."
    )


__all__ = ["BaseLoop", "DefaultLoop", "resolve_loop"]
