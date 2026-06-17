"""CLI entry point for agents-benchmark."""

from __future__ import annotations

import argparse
import sys


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
        print(f"Running benchmark with model={args.model}, agents={args.agents}")
    elif args.command == "compare":
        print(f"Comparing results from {args.results_dir}")


if __name__ == "__main__":
    main()
