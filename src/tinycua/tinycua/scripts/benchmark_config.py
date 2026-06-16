"""Benchmark configuration dataclass for WildClawBench runs.

Defines BenchmarkConfig with fields for model, endpoint, and output
configuration. Supports CLI argument parsing via argparse.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run.

    Attributes:
        model_name: Name of the local LLM model.
        base_url: Base URL of the LLM API endpoint.
        api_key: Optional API key for authentication.
        timeout_seconds: Per-task timeout in seconds.
        preserve_artifacts: Whether to keep task artifacts after grading.
        verbose: Enable verbose logging output.
        concurrent_tasks: Number of tasks to run concurrently.
            Currently informational only — concurrent execution not yet implemented.
    """

    model_name: str = "llama3"
    base_url: str = "http://localhost:8000/v1"
    api_key: str | None = None
    timeout_seconds: int = 600
    preserve_artifacts: bool = True
    verbose: bool = False
    concurrent_tasks: int = 1

    @classmethod
    def from_args(cls, args: argparse.Namespace | None = None) -> BenchmarkConfig:
        """Construct config from parsed CLI arguments.

        Args:
            args: Parsed argparse.Namespace, or None to use defaults.

        Returns:
            BenchmarkConfig populated from args.
        """
        if args is None:
            return cls()

        return cls(
            model_name=getattr(args, "model_name", cls.model_name),
            base_url=getattr(args, "base_url", cls.base_url),
            api_key=getattr(args, "api_key", None) or cls.api_key,
            timeout_seconds=getattr(args, "timeout_seconds", cls.timeout_seconds),
            preserve_artifacts=getattr(
                args, "preserve_artifacts", cls.preserve_artifacts
            ),
            verbose=getattr(args, "verbose", cls.verbose),
            concurrent_tasks=getattr(args, "concurrent_tasks", cls.concurrent_tasks),
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the benchmark runner.

    Args:
        argv: Optional argument list (defaults to sys.argv).

    Returns:
        Parsed argparse.Namespace.
    """
    parser = argparse.ArgumentParser(
        description="Run WildClawBench benchmark tasks with TinyCUA."
    )
    parser.add_argument(
        "--model-name",
        default="llama3",
        help="Name of the local LLM model (default: llama3).",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000/v1",
        help="LLM API base URL (default: http://localhost:8000/v1).",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        type=str,
        help="Optional API key for authentication.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=600,
        help="Per-task timeout in seconds (default: 600).",
    )
    parser.add_argument(
        "--preserve-artifacts",
        action="store_false",
        default=True,
        dest="preserve_artifacts",
        help="Remove task artifacts after grading (default: preserve).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging output.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for benchmark results (default: benchmark_results/).",
    )
    parser.add_argument(
        "--tasks",
        type=str,
        default=None,
        help="Comma-separated list of task IDs to run (default: all 60 tasks).",
    )
    parser.add_argument(
        "--concurrent-tasks",
        type=int,
        default=1,
        help="Number of tasks to run concurrently (default: 1).",
    )
    return parser.parse_args(argv)
