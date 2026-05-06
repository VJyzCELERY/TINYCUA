"""Agent executor base."""

from __future__ import annotations

from typing import Any

from tinycua_sdk.agent.config import AgentConfig


class AgentExecutor:
    """Base class providing config storage. Execution logic added in Stage 3."""

    def __init__(self, config: AgentConfig) -> None:
        """Initialize AgentExecutor.

        Args:
            config: Agent configuration model.
        """
        self.config = config
        self._cancelled = False

    @property
    def is_cancelled(self) -> bool:
        """Check if execution has been cancelled."""
        return self._cancelled

    def cancel(self) -> None:
        """Cancel current run/stream."""
        self._cancelled = True

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Run the agent.

        Raises:
            NotImplementedError: Execution implemented in Stage 3.
        """
        raise NotImplementedError("Agent.run() implemented in Stage 3")


__all__ = ["AgentExecutor"]
