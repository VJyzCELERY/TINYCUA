"""DefaultLoop - Base class for custom agent execution loops."""

from typing import TYPE_CHECKING, AsyncIterator, Union

if TYPE_CHECKING:
    from tinycua_sdk.agent import Agent
    from tinycua_sdk.runner import Runner
    from tinycua_sdk.models.response import StreamEvent
    from tinycua_sdk.models import RunResult


class DefaultLoop:
    """Base class for custom agent execution loops.

    Users extend this class to define custom execution strategies.
    Provides access to Runner helpers for tool execution and LLM calls.

    Example:
        class MyLoop(DefaultLoop):
            async def run(self, agent, user_input, **kwargs):
                # Custom logic
                result = await self.runner.call_llm(messages)
                return result
    """

    def __init__(self, runner: "Runner" = None):
        """Initialize with optional runner.

        Runner will be injected by Agent when loop is loaded.

        Args:
            runner: Runner instance for basic execution (optional)
        """
        self.runner = runner

    async def run(
        self,
        agent: "Agent",
        user_input: str,
        plan_mode: bool = False,
        trace: bool = False,
        verbose: bool = False,
        stream_sse: bool = False,
        **kwargs,
    ) -> Union["RunResult", str, AsyncIterator["StreamEvent"]]:
        """Execute the agent loop.

        Default implementation wraps Runner.run() or Runner.run_sse().
        Override to define custom execution strategy.

        Args:
            agent: The agent instance with tools
            user_input: The user's input
            plan_mode: If True, only allow plan-mode tools
            trace: If True, return RunResult with trace
            verbose: If True, log raw events
            stream_sse: If True, yield StreamEvents
            **kwargs: Additional parameters for custom loops

        Returns:
            RunResult if trace=True, string if not, AsyncIterator if stream_sse=True
        """
        self.runner.trace = trace
        self.runner.verbose = verbose
        self.runner.stream_sse = stream_sse
        self.runner.plan_mode = plan_mode

        if stream_sse:
            return self.runner.run_sse(user_input)

        return await self.runner.run(user_input, trace=trace)


__all__ = ["DefaultLoop"]
