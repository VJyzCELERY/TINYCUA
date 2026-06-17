"""CLI entry point for agents-benchmark."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from agents_benchmark.agent_registry import AgentRegistry
from agents_benchmark.compare import compare_agents
from agents_benchmark.runner import BenchmarkRunner

logger = logging.getLogger(__name__)

DEFAULT_AGENTS = ["hermes", "claudecode", "codex", "openclaw"]


def _build_registry() -> AgentRegistry:
    """Build and populate the agent registry with all adapters.

    Returns:
        Registry with all known agent adapters registered.
    """
    registry = AgentRegistry()

    from agents_benchmark.agents.claudecode import ClaudeCodeAdapter
    from agents_benchmark.agents.codex import CodexAdapter
    from agents_benchmark.agents.hermes import HermesAgentAdapter
    from agents_benchmark.agents.openclaw import OpenClawAdapter

    registry.register("hermes", HermesAgentAdapter)
    registry.register("claudecode", ClaudeCodeAdapter)
    registry.register("codex", CodexAdapter)
    registry.register("openclaw", OpenClawAdapter)

    return registry


def _handle_run(args: argparse.Namespace) -> None:
    """Handle the 'run' subcommand.

    Args:
        args: Parsed CLI arguments.
    """
    registry = _build_registry()
    runner = BenchmarkRunner(registry=registry, results_dir=args.results_dir)

    if args.agents == "all":
        agent_list = list(DEFAULT_AGENTS)
    else:
        agent_list = [a.strip() for a in args.agents.split(",")]

    if args.parallel > 1:
        logger.warning("--parallel > 1 is not yet implemented; running sequentially")

    result = runner.run_pipeline(agents=agent_list, model=args.model)

    output_dir = Path(args.results_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / "summary_all.json"
    serializable = {
        "agent_results": {
            name: [
                {
                    "agent_name": r.agent_name,
                    "task_id": r.task_id,
                    "score": r.score,
                    "status": r.status,
                    "elapsed_time": r.elapsed_time,
                    "token_usage": r.token_usage,
                    "output_dir": str(r.output_dir),
                }
                for r in results
            ]
            for name, results in result.agent_results.items()
        },
        "summary": result.summary,
    }
    with summary_path.open("w") as f:
        json.dump(serializable, f, indent=2)

    print(f"Results written to {summary_path}")


def _handle_compare(args: argparse.Namespace) -> None:
    """Handle the 'compare' subcommand.

    Args:
        args: Parsed CLI arguments.
    """
    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        logger.error("Results directory not found: %s", results_dir)
        sys.exit(1)

    agent_results: dict[str, list[dict]] = {}
    for result_file in sorted(results_dir.glob("*_results.json")):
        agent_name = result_file.name.replace("_results.json", "")
        try:
            with result_file.open() as f:
                data = json.load(f)
            agent_results[agent_name] = data.get("tasks", [])
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Skipping %s: %s", agent_name, exc)

    if not agent_results:
        logger.warning("No agent result files found in %s", results_dir)

    comparison = compare_agents(agent_results)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(comparison, f, indent=2)

    print(f"Comparison written to {output_path}")


def main(argv: list[str] | None = None) -> None:
    """Run the agents-benchmark CLI."""
    parser = argparse.ArgumentParser(
        prog="agents-benchmark",
        description="Unified WildClawBench benchmark harness",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Default (run) subcommand
    run_parser = subparsers.add_parser("run", help="Run the benchmark pipeline")
    run_parser.add_argument("--model", required=True, help="Model name/path")
    run_parser.add_argument(
        "--agents", default="all", help="Comma-separated agent names or 'all'"
    )
    run_parser.add_argument("--category", default="all", help="Task category filter")
    run_parser.add_argument(
        "--parallel", type=int, default=1, help="Parallel task count"
    )
    run_parser.add_argument(
        "--results-dir", default="output", help="Results output directory"
    )
    run_parser.add_argument("--config", default=None, help="Config file path")

    # Compare subcommand
    compare_parser = subparsers.add_parser("compare", help="Compare results")
    compare_parser.add_argument(
        "--results-dir", default="output", help="Results directory"
    )
    compare_parser.add_argument(
        "--output", default="comparison.json", help="Output comparison file"
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "run":
        _handle_run(args)
    elif args.command == "compare":
        _handle_compare(args)


if __name__ == "__main__":
    main()
