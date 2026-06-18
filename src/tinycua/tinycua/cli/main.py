"""CLI entry point for tinycua with subcommand dispatch."""

from __future__ import annotations

import argparse
import os
import sys


def main() -> None:
    """Dispatch tinycua CLI subcommands.

    When invoked without a subcommand, shows help text and exits cleanly.
    Supported subcommands: run, benchmark, smoke-run.
    """
    # Load src/tinycua/.env (and cwd/.env) BEFORE parsing args so env-derived
    # argparse defaults (--worker-effort, --provider-type) see the user's
    # configured values. Shell-provided env vars always win.
    from tinycua.cli.config import _load_default_env

    _load_default_env()

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

    # Register 'smoke-run' subcommand
    from tinycua.cli.smoke_run import add_arguments as add_smoke_run_arguments

    smoke_run_parser = subparsers.add_parser(
        "smoke-run",
        help="Run WildClawBench smoke tasks across all categories.",
    )
    add_smoke_run_arguments(smoke_run_parser)

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
            dir=run_args.dir,
            provider_url=run_args.provider_url,
            api_key=run_args.api_key,
            model=run_args.model,
            provider_type=run_args.provider_type,
            worker_effort=run_args.worker_effort,
            timeout=run_args.timeout,
            verbose=run_args.verbose,
            env_file=run_args.env_file,
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

    elif args.command == "smoke-run":
        from tinycua.cli.smoke_run import parse_args, smoke_run_command

        smoke_args = parse_args(sys.argv[2:])

        exit_code = smoke_run_command(
            model=smoke_args.model,
            base_url=smoke_args.base_url,
            api_key=smoke_args.api_key,
            timeout=smoke_args.timeout,
            mode=smoke_args.mode,
            output=smoke_args.output,
            verbose=smoke_args.verbose,
            docker_image=smoke_args.docker_image,
        )
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
