"""BaseLoop - Base class for custom agent execution loops."""

from typing import TYPE_CHECKING, Any, AsyncIterator, Union

from tinycua_sdk.agent.hooks import HookManager, HookFunc

if TYPE_CHECKING:
    from tinycua_sdk.agent import Agent
    from tinycua_sdk.runner import Runner
    from tinycua_sdk.models.response import StreamEvent
    from tinycua_sdk.models import RunResult


# Valid built-in loop types
VALID_LOOP_TYPES = {"default", "react"}


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
    Provides access to Runner helpers for tool execution and LLM calls.

    Example:
        class MyLoop(BaseLoop):
            async def run(self, agent, user_input, **kwargs):
                # Custom logic
                result = await self.runner.call_llm(messages)
                return result

    Attributes:
        runner: Runner instance for basic execution (set by AgentExecutor)
    """

    def __init__(self, runner: "Runner" = None):
        """Initialize with optional runner.

        Runner will be injected by Agent when loop is loaded.

        Args:
            runner: Runner instance for basic execution (optional)
        """
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
        user_input: str,
        trace: bool = False,
        verbose: bool = False,
        stream_sse: bool = False,
        **kwargs,
    ) -> Union["RunResult", str, AsyncIterator["StreamEvent"]]:
        """Execute the agent loop.

        Default implementation wraps Runner.run() or Runner.run_sse().
        Override to define custom execution strategy.

        Pre-execution hooks run before main loop.
        Post-execution hooks run after main loop.

        Args:
            agent: The agent instance with tools
            user_input: The user's input
            trace: If True, return RunResult with trace
            verbose: If True, log raw events
            stream_sse: If True, yield StreamEvents
            **kwargs: Additional parameters for custom loops

        Returns:
            RunResult if trace=True, string if not, AsyncIterator if stream_sse=True
        """
        context = {
            "agent": agent,
            "user_input": user_input,
            "trace": trace,
            "verbose": verbose,
            "stream_sse": stream_sse,
            **kwargs,
        }

        context = await self._hooks.execute_pre_hooks(context)

        self.runner.trace = context.get("trace", trace)
        self.runner.verbose = context.get("verbose", verbose)
        self.runner.stream_sse = context.get("stream_sse", stream_sse)

        if context.get("stream_sse"):
            result = self.runner.run_sse(context.get("user_input", user_input))
        else:
            result = await self.runner.run(
                context.get("user_input", user_input),
                trace=context.get("trace", trace),
            )

        context["result"] = result
        context = await self._hooks.execute_post_hooks(context)

        return context.get("result", result)


class ReactLoop(BaseLoop):
    """ReAct (Reason + Act) loop implementation.

    Implements the ReAct pattern where the agent explicitly reasons about each step.
    Each iteration: Call LLM -> Extract tool calls -> Execute tools -> Add results -> Repeat.

    Args:
        runner: Runner instance for LLM calls and tool execution
        max_iterations: Maximum number of reasoning iterations (default: 5)
    """

    def __init__(self, runner: "Runner" = None, max_iterations: int = 5):
        """Initialize ReactLoop.

        Args:
            runner: Runner instance for LLM calls and tool execution
            max_iterations: Maximum number of reasoning iterations
        """
        super().__init__(runner=runner)
        self.max_iterations = max_iterations

    async def run(
        self,
        agent: "Agent",
        user_input: str,
        trace: bool = False,
        verbose: bool = False,
        stream_sse: bool = False,
        **kwargs,
    ) -> Union["RunResult", str, AsyncIterator["StreamEvent"]]:
        """Execute the ReAct loop.

        Args:
            agent: The agent instance with tools
            user_input: The user's input
            trace: If True, return RunResult with trace
            verbose: If True, log raw events
            stream_sse: If True, yield StreamEvents
            **kwargs: Additional parameters

        Returns:
            RunResult if trace=True, string if not, AsyncIterator if stream_sse=True
        """
        self.runner.trace = trace
        self.runner.verbose = verbose
        self.runner.stream_sse = stream_sse

        # Build initial messages
        messages = self.runner.build_messages(user_input)
        tools = self.runner.get_tool_configs()

        # Iterate up to max_iterations
        for iteration in range(self.max_iterations):
            # Call LLM
            response = await self.runner.call_llm(messages, tools)

            # Extract tool calls from response
            tool_calls = self._extract_tool_calls(response)

            # Log iteration
            self.runner.emit_loop_log(
                f"ReAct Iteration {iteration + 1}: {len(tool_calls)} tool calls",
                "info",
            )

            # If no tool calls, return the content
            if not tool_calls:
                content = self._extract_content(response)
                if content:
                    return content
                return "No response content"

            # Execute tools
            tool_messages, results = await self.runner.execute_tool_loop(tool_calls)

            # Add tool results to messages
            messages.extend(tool_messages)

        return "Max iterations reached"

    def _extract_tool_calls(self, response: Any) -> list[dict[str, Any]]:
        """Extract tool calls from LLM response.

        Args:
            response: Response from Runner.call_llm()

        Returns:
            List of tool call dicts
        """
        tool_calls = []
        # Handle Response object with choices
        if hasattr(response, "choices"):
            for choice in response.choices:
                if isinstance(choice, dict) and "message" in choice:
                    msg = choice["message"]
                    if isinstance(msg, dict) and "tool_calls" in msg:
                        for tc in msg["tool_calls"]:
                            tool_calls.append(
                                {
                                    "id": tc.get("id", ""),
                                    "type": "function",
                                    "function": {
                                        "name": tc.get("function", {}).get("name", ""),
                                        "arguments": tc.get("function", {}).get(
                                            "arguments", "{}"
                                        ),
                                    },
                                }
                            )
        return tool_calls

    def _extract_content(self, response: Any) -> str:
        """Extract content from LLM response.

        Args:
            response: Response from Runner.call_llm()

        Returns:
            Content string or empty string
        """
        # Handle Response object with choices
        if hasattr(response, "choices"):
            for choice in response.choices:
                if isinstance(choice, dict):
                    msg = choice.get("message", {})
                    if isinstance(msg, dict):
                        content = msg.get("content", "")
                        if content:
                            return content
        return ""


# Keep DefaultLoop as alias for backwards compatibility
DefaultLoop = BaseLoop


def resolve_loop(loop_config: Any) -> BaseLoop:
    """Resolve loop configuration to a loop instance.

    Args:
        loop_config: Can be:
            - None: returns BaseLoop
            - str: "default" or "react"
            - dict: {type: "react", max_iterations: 5, ...}
            - BaseLoop instance: returns as-is

    Returns:
        BaseLoop subclass instance (runner NOT set - set by AgentExecutor)

    Raises:
        ValueError: If loop_type is not valid
    """
    # If None, return BaseLoop
    if loop_config is None:
        return BaseLoop()

    # If already a BaseLoop instance, return as-is
    if isinstance(loop_config, BaseLoop):
        return loop_config

    # If string, normalize and resolve
    if isinstance(loop_config, str):
        loop_type = loop_config.lower()
        _validate_loop_type(loop_type)

        if loop_type == "default":
            return BaseLoop()
        elif loop_type == "react":
            return ReactLoop()

    # If dict, extract type and resolve
    if isinstance(loop_config, dict):
        loop_type = loop_config.get("type", "default").lower()
        _validate_loop_type(loop_type)

        # Extract kwargs (everything except 'type')
        kwargs = {k: v for k, v in loop_config.items() if k != "type"}

        # Filter kwargs to only include valid constructor parameters
        if loop_type == "default":
            valid_kwargs = {k: v for k, v in kwargs.items() if k == "runner"}
            return BaseLoop(**valid_kwargs)
        elif loop_type == "react":
            valid_kwargs = {
                k: v for k, v in kwargs.items() if k in ("runner", "max_iterations")
            }
            return ReactLoop(**valid_kwargs)

    # If we get here, config is invalid
    raise ValueError(
        f"Invalid loop configuration: {loop_config}. "
        f"Must be None, str, dict, or BaseLoop instance."
    )


__all__ = ["BaseLoop", "ReactLoop", "DefaultLoop", "resolve_loop"]
