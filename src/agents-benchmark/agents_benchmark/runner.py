"""Pipeline orchestrator — runs agents sequentially, collects results."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents_benchmark.agent_registry import AgentRegistry
from agents_benchmark.base_agent import AgentTaskSpec

logger = logging.getLogger(__name__)

AGENT_ORDER = ["hermes", "claudecode", "codex", "openclaw"]


@dataclass
class BenchmarkResult:
    """Result of running a single agent across tasks."""

    agent_name: str
    task_id: str
    score: float | None
    status: str
    elapsed_time: float
    token_usage: dict[str, Any]
    output_dir: Path


@dataclass
class PipelineResult:
    """Result of running the full benchmark pipeline."""

    agent_results: dict[str, list[BenchmarkResult]] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    comparison: dict[str, Any] | None = None


class BenchmarkRunner:
    """Pipeline orchestrator for running agents sequentially.

    Runs agents in fixed order: hermes, claudecode, codex, openclaw.
    Failed agents are skipped; remaining agents continue.

    Args:
        registry: Agent registry with registered adapters.
        results_dir: Base directory for results output.
    """

    def __init__(self, registry: AgentRegistry, results_dir: str = "output") -> None:
        self._registry = registry
        self._results_dir = Path(results_dir)

    def run_pipeline(
        self,
        agents: list[str],
        model: str,
    ) -> PipelineResult:
        """Run the benchmark pipeline for the specified agents.

        Args:
            agents: List of agent names to run, or ["all"] for all agents.
            model: Model name/path to use.

        Returns:
            PipelineResult with per-agent results and summary.
        """
        result = PipelineResult()

        if agents == ["all"]:
            agent_names = list(AGENT_ORDER)
        else:
            agent_names = [a for a in agents if a in self._registry.list_all()]

        for agent_name in agent_names:
            try:
                adapter_cls = self._registry.get(agent_name)
                adapter = adapter_cls()
                self._run_single_agent(adapter, agent_name, model, result)
            except Exception as exc:
                logger.error("Agent %s failed: %s", agent_name, exc)
                result.summary[agent_name] = {
                    "status": "error",
                    "error": str(exc),
                }

        return result

    def _run_single_agent(
        self,
        adapter: Any,
        agent_name: str,
        model: str,
        result: PipelineResult,
    ) -> None:
        """Run a single agent and collect results.

        Args:
            adapter: Instantiated agent adapter.
            agent_name: Name of the agent.
            model: Model name/path.
            result: PipelineResult to populate.
        """
        logger.info("Running agent: %s", agent_name)
        agent_results: list[BenchmarkResult] = []

        # Placeholder for actual task execution
        # In production, this would iterate over task specs from the task suite
        try:
            # Create a placeholder task to demonstrate the pipeline
            task_spec = AgentTaskSpec(
                task_id=f"{agent_name}-task-001",
                task={"type": "placeholder"},
                workspace_path=str(self._results_dir / agent_name / "workspace"),
                prompt="Benchmark task",
                timeout_seconds=300,
                output_dir=self._results_dir / agent_name / "output",
                model=model,
            )

            execution = adapter.run_task(task_spec)
            status = "success" if execution.error is None else "error"

            usage = adapter.collect_usage(
                task_spec.task_id,
                Path(task_spec.output_dir),
                execution.elapsed_time,
            )

            agent_results.append(
                BenchmarkResult(
                    agent_name=agent_name,
                    task_id=task_spec.task_id,
                    score=1.0 if status == "success" else 0.0,
                    status=status,
                    elapsed_time=execution.elapsed_time,
                    token_usage=usage,
                    output_dir=Path(task_spec.output_dir),
                )
            )

            result.agent_results[agent_name] = agent_results
            result.summary[agent_name] = {
                "status": status,
                "total_tasks": len(agent_results),
                "successful_tasks": sum(
                    1 for r in agent_results if r.status == "success"
                ),
            }

        except Exception as exc:
            logger.error("Agent %s task execution failed: %s", agent_name, exc)
            result.summary[agent_name] = {
                "status": "error",
                "error": str(exc),
            }
