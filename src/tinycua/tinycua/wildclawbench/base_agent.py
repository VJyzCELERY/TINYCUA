"""Local copies of WildClawBench BaseAgent ABC and dataclasses.

Avoids hard dependency on the WildClawBench package. These types mirror the
upstream interface so TinyCUAAgent can be used as a drop-in BaseAgent
implementation.
"""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentTaskSpec:
    """Specification for a single benchmark task execution."""

    task_id: str
    task: dict[str, Any]
    workspace_path: str
    prompt: str
    timeout_seconds: int
    output_dir: Path
    model: str
    thinking: str | None = None
    models_config: dict[str, Any] | None = None
    lobster: dict[str, Any] | None = None


@dataclass
class AgentExecution:
    """Result of a single agent task execution."""

    elapsed_time: float
    error: str | None = None
    gateway_proc: subprocess.Popen[str] | None = None
    agent_proc: subprocess.Popen[str] | None = None


class BaseAgent(ABC):
    """Abstract base class for WildClawBench-compatible agents.

    Agents implement this interface so they can be selected as backends
    for benchmark task execution.
    """

    @property
    @abstractmethod
    def expects_gateway(self) -> bool:
        """Return True if this agent expects a long-running gateway process."""

    @property
    @abstractmethod
    def transcript_container_path(self) -> str:
        """Return the path to the transcript container file."""

    def prepare_grading_transcript(self, task_id: str) -> str:
        """Prepare and return the transcript path for grading.

        Args:
            task_id: The task identifier.

        Returns:
            Path to the transcript container.
        """
        return self.transcript_container_path

    @abstractmethod
    def run_task(self, spec: AgentTaskSpec) -> AgentExecution:
        """Execute a single benchmark task.

        Args:
            spec: The task specification.

        Returns:
            Execution result with timing and optional error.
        """

    @abstractmethod
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
        """
