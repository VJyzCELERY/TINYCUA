"""OpenClaw adapter — stub implementing BaseAgent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents_benchmark.base_agent import AgentExecution, AgentTaskSpec, BaseAgent


class OpenClawAdapter(BaseAgent):
    """Stub adapter for OpenClaw agent.

    Implements the BaseAgent interface. Returns error executions
    until real Docker integration is implemented.
    """

    @property
    def name(self) -> str:
        """Return the agent identifier."""
        return "openclaw"

    @property
    def expects_gateway(self) -> bool:
        """Return False — no long-running process needed."""
        return False

    @property
    def transcript_container_path(self) -> str:
        """Return path to the transcript file inside the container."""
        return "/workspace/transcript.jsonl"

    def run_task(self, _spec: AgentTaskSpec) -> AgentExecution:
        """Execute a single benchmark task.

        Args:
            _spec: The task specification (unused in stub).

        Returns:
            Execution result with error indicating stub is not implemented.
        """
        return AgentExecution(
            elapsed_time=0.0,
            error="OpenClaw adapter not yet implemented",
        )

    def collect_usage(
        self,
        _task_id: str,
        _output_dir: Path,
        _elapsed_time: float,
    ) -> dict[str, Any]:
        """Collect usage statistics from a completed task.

        Args:
            _task_id: The task identifier (unused in stub).
            _output_dir: Directory containing task output artifacts (unused in stub).
            _elapsed_time: Time taken for execution (unused in stub).

        Returns:
            Dict with keys: requests, total_tokens, cost.
        """
        return {"requests": 0, "total_tokens": None, "cost": 0.0}
