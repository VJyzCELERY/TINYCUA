"""CLI entry point for tinycua with subcommand dispatch."""

from __future__ import annotations

import argparse
import os
import sys


def main() -> None:
    """Dispatch tinycua CLI subcommands.

    When invoked without a subcommand, shows help text and exits cleanly.
    Supported subcommands: run, benchmark.
    """
    parser = argparse.ArgumentParser(
        prog="tinycua",
        description="TinyCUA — Computer-Use Agent CLI.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Register 'run' subcommand
    subparsers.add_parser(
        "run",
        help="Run a TinyCUA agent task with a local model endpoint.",
    )

    # Register 'benchmark' subcommand
    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Benchmark execution commands for WildClawBench evaluation.",
    )
    benchmark_subparsers = benchmark_parser.add_subparsers(dest="benchmark_command")
    benchmark_subparsers.add_parser(
        "run",
        help="Run a TinyCUA benchmark task.",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        raise SystemExit(0)

    if args.command == "run":
        from tinycua.cli.run import parse_args, run_command

        run_args = parse_args(sys.argv[2:])

        if not run_args.prompt:
            parser.error("the following arguments are required: prompt")

        exit_code = run_command(
            prompt=run_args.prompt,
            timeout=run_args.timeout,
            output_dir=run_args.output_dir,
            workspace=run_args.workspace,
            base_url=run_args.base_url,
            api_key=run_args.api_key,
            model=run_args.model,
            verbose=run_args.verbose,
        )
        raise SystemExit(exit_code)

    elif args.command == "benchmark":
        from tinycua.cli.benchmark import benchmark_run_command, parse_args

        benchmark_args = parse_args(sys.argv[3:])

        # Read prompt from environment variable if not provided via CLI
        prompt = benchmark_args.prompt or os.environ.get("TASK_PROMPT")
        if not prompt:
            print(
                "ERROR: No task prompt provided. Use --prompt or set TASK_PROMPT env var.",
                flush=True,
            )
            raise SystemExit(1)

        # Read timeout from environment variable if not provided via CLI
        timeout = (
            benchmark_args.timeout
            if benchmark_args.timeout is not None
            else int(os.environ.get("TINYCUA_TIMEOUT", "300"))
        )

        exit_code = benchmark_run_command(
            prompt=prompt,
            workspace=benchmark_args.workspace,
            output_dir=benchmark_args.output,
            transcript_path=benchmark_args.transcript,
            timeout=timeout,
            base_url=benchmark_args.base_url,
            api_key=benchmark_args.api_key,
            model=benchmark_args.model,
            verbose=benchmark_args.verbose,
        )
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
