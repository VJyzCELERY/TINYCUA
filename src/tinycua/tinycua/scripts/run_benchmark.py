"""Main benchmark orchestrator for WildClawBench runs.

Loops through tasks, runs TinyCUAAgent, collects usage, aggregates results,
and writes summary_all.json. Supports both full 60-task runs and subsets.
"""

from __future__ import annotations

import json
import logging
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tinycua.scripts.benchmark_config import BenchmarkConfig, parse_args
from tinycua.scripts.collect_metadata import collect_run_metadata, preflight_check
from tinycua.wildclawbench.agent import TinyCUAAgent

logger = logging.getLogger(__name__)

# Default 60-task WildClawBench task list
DEFAULT_TASKS = [f"task_{i:03d}" for i in range(1, 61)]


@dataclass
class TaskResult:
    """Result of a single benchmark task execution.

    Attributes:
        task_id: Unique task identifier.
        task_category: Category of the task (e.g. 'Productivity Flow').
        score: Graded score (0.0-1.0) or None if not scored.
        status: Execution status: 'success', 'failed', 'timeout', 'error'.
        elapsed_time: Wall-clock time in seconds.
        error: Error message if status is not 'success'.
        transcript_path: Path to transcript JSONL file.
        usage_path: Path to usage JSON file.
        log_path: Path to agent log file.
        output_path: Path to task output directory.
        requests: Number of LLM API requests made.
        total_tokens: Total tokens consumed (None if unavailable).
        cost: Monetary cost of the task (0.0 for local models).
    """

    task_id: str
    task_category: str
    score: float | None
    status: str
    elapsed_time: float
    error: str | None
    transcript_path: str
    usage_path: str
    log_path: str
    output_path: str | None
    requests: int
    total_tokens: int | None
    cost: float


@dataclass
class SummaryAggregate:
    """Aggregated statistics across all task results.

    Attributes:
        total_tasks: Total number of tasks attempted.
        completed_tasks: Number of tasks that completed (success or failed).
        successful_tasks: Number of tasks with status 'success'.
        failed_tasks: Number of tasks with status 'failed'.
        skipped_tasks: Number of tasks that were skipped.
        average_score: Mean score across scored tasks (None if none scored).
        min_score: Minimum score across scored tasks (None if none scored).
        max_score: Maximum score across scored tasks (None if none scored).
        median_score: Median score across scored tasks (None if none scored).
        total_elapsed_seconds: Total wall-clock time across all tasks.
        average_task_time: Average time per task in seconds.
        category_scores: Per-category score breakdown.
    """

    total_tasks: int = 0
    completed_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    skipped_tasks: int = 0
    average_score: float | None = None
    min_score: float | None = None
    max_score: float | None = None
    median_score: float | None = None
    total_elapsed_seconds: float = 0.0
    average_task_time: float = 0.0
    category_scores: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_task_results(cls, results: list[TaskResult]) -> SummaryAggregate:
        """Compute aggregate statistics from a list of task results.

        Args:
            results: List of TaskResult instances.

        Returns:
            Populated SummaryAggregate.
        """
        if not results:
            return cls(
                total_tasks=0,
                completed_tasks=0,
                successful_tasks=0,
                failed_tasks=0,
                skipped_tasks=0,
            )

        successful = [r for r in results if r.status == "success"]
        failed = [r for r in results if r.status in ("failed", "error", "timeout")]
        scored = [r for r in results if r.score is not None]

        scores = [r.score for r in scored] if scored else []
        avg_score = statistics.mean(scores) if scores else None
        min_score = min(scores) if scores else None
        max_score = max(scores) if scores else None
        median_score = statistics.median(scores) if scores else None

        total_elapsed = sum(r.elapsed_time for r in results)
        avg_time = total_elapsed / len(results) if results else 0.0

        # Per-category breakdown
        category_scores: dict[str, dict[str, Any]] = {}
        for result in results:
            cat = result.task_category
            if cat not in category_scores:
                category_scores[cat] = {"scores": [], "count": 0}
            category_scores[cat]["count"] += 1
            if result.score is not None:
                category_scores[cat]["scores"].append(result.score)

        # Compute per-category averages
        for cat in category_scores:
            cat_scores = category_scores[cat]["scores"]
            category_scores[cat] = {
                "count": category_scores[cat]["count"],
                "average_score": statistics.mean(cat_scores) if cat_scores else None,
                "min_score": min(cat_scores) if cat_scores else None,
                "max_score": max(cat_scores) if cat_scores else None,
            }

        return cls(
            total_tasks=len(results),
            completed_tasks=len(successful) + len(failed),
            successful_tasks=len(successful),
            failed_tasks=len(failed),
            skipped_tasks=0,
            average_score=avg_score,
            min_score=min_score,
            max_score=max_score,
            median_score=median_score,
            total_elapsed_seconds=total_elapsed,
            average_task_time=avg_time,
            category_scores=category_scores,
        )


def run_full_benchmark(
    config: BenchmarkConfig,
    output_dir: Path,
    tasks: list[str] | None = None,
) -> None:
    """Execute the full benchmark suite.

    Loops through tasks, runs TinyCUAAgent for each, collects usage data,
    and writes summary_all.json to the output directory.

    Args:
        config: Benchmark configuration.
        output_dir: Directory to write results and summary.
        tasks: Optional list of task IDs (defaults to all 60 tasks).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    preflight_check(output_dir)

    if tasks is None:
        tasks = DEFAULT_TASKS

    agent = TinyCUAAgent(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model_name,
    )

    start_time = datetime.now(timezone.utc)
    results: list[TaskResult] = []

    for task_id in tasks:
        logger.info("Running task %s", task_id)

        task_dir = output_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        from tinycua.wildclawbench.base_agent import AgentTaskSpec

        spec = AgentTaskSpec(
            task_id=task_id,
            task={},
            workspace_path=str(task_dir / "workspace"),
            prompt=f"Complete benchmark task {task_id}",
            timeout_seconds=config.timeout_seconds,
            output_dir=task_dir,
            model=config.model_name,
        )

        try:
            execution = agent.run_task(spec)
            usage = agent.collect_usage(
                task_id, task_dir, execution.elapsed_time
            )

            status = "success" if execution.error is None else "failed"
            error_msg = execution.error
            total_tokens = usage.get("total_tokens")
            requests_count = usage.get("requests", 0)
            cost = usage.get("cost", 0.0)

            result = TaskResult(
                task_id=task_id,
                task_category="Uncategorized",
                score=1.0 if status == "success" else 0.0,
                status=status,
                elapsed_time=execution.elapsed_time,
                error=error_msg,
                transcript_path=str(task_dir / "transcript.jsonl"),
                usage_path=str(task_dir / "usage.json"),
                log_path=str(task_dir / "agent.log"),
                output_path=str(task_dir),
                requests=requests_count,
                total_tokens=total_tokens,
                cost=cost,
            )
        except Exception as exc:
            logger.error("Task %s raised exception: %s", task_id, exc)
            result = TaskResult(
                task_id=task_id,
                task_category="Uncategorized",
                score=None,
                status="error",
                elapsed_time=0.0,
                error=str(exc),
                transcript_path="",
                usage_path="",
                log_path="",
                output_path=None,
                requests=0,
                total_tokens=None,
                cost=0.0,
            )

        results.append(result)

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    metadata = collect_run_metadata(config, start_time, end_time, duration)
    summary = SummaryAggregate.from_task_results(results)

    summary_data = {
        "metadata": asdict(metadata),
        "summary": asdict(summary),
        "tasks": [asdict(r) for r in results],
    }

    summary_path = output_dir / "summary_all.json"
    with open(summary_path, "w") as f:
        json.dump(summary_data, f, indent=2)

    logger.info("Benchmark complete. Summary written to %s", summary_path)


def main() -> None:
    """CLI entry point for the benchmark runner."""
    args = parse_args()
    config = BenchmarkConfig.from_args(args)

    output_dir = Path(args.output_dir or "benchmark_results")
    tasks = args.tasks.split(",") if args.tasks else None

    if config.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    run_full_benchmark(config, output_dir, tasks)


if __name__ == "__main__":
    main()
