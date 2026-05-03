"""BaseLoop - Base class for custom agent execution loops."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tinycua_sdk.agent import Agent


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
        max_iterations: Maximum number of loop iterations.
    """

    def __init__(self, max_iterations: int = 5):
        """Initialize with optional max iterations.

        Args:
            max_iterations: Maximum number of loop iterations.
        """
        self.max_iterations = max_iterations

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
        # Stub for now — implemented in Stage 3
        pass


__all__ = ["BaseLoop"]
