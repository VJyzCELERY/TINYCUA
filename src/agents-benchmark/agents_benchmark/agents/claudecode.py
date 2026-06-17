"""Claude Code adapter — stub implementing BaseAgent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents_benchmark.base_agent import AgentExecution, AgentTaskSpec, BaseAgent


class ClaudeCodeAdapter(BaseAgent):
    """Stub adapter for Claude Code agent.

    Implements the BaseAgent interface. Methods raise NotImplementedError
    until real Docker integration is implemented.
    """

    @property
    def name(self) -> str:
        """Return the agent identifier."""
        return "claudecode"

    @property
    def expects_gateway(self) -> bool:
        """Return False — no long-running process needed."""
        return False

    @property
    def transcript_container_path(self) -> str:
        """Return path to the transcript file inside the container."""
        return "/workspace/transcript.jsonl"

    def run_task(self, spec: AgentTaskSpec) -> AgentExecution:
        """Execute a single benchmark task.

        Args:
            spec: The task specification.

        Returns:
            Execution result.

        Raises:
            NotImplementedError: Stub — not yet implemented.
        """
        raise NotImplementedError("TODO: implement Claude Code adapter")

    def collect_usage(
        self, task_id: str, output_dir: Path, elapsed_time: float
    ) -> dict[str, Any]:
        """Collect usage statistics from a completed task.

        Args:
            task_id: The task identifier.
            output_dir: Directory containing task output artifacts.
            elapsed_time: Time taken for execution.

        Returns:
            Dict with keys: requests, total_tokens, cost.

        Raises:
            NotImplementedError: Stub — not yet implemented.
        """
        raise NotImplementedError("TODO: implement Claude Code adapter")
