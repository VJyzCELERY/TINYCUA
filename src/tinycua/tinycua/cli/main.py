"""CLI entry point for tinycua with subcommand dispatch."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _load_default_env() -> None:
    """Load the project ``.env`` before argparse evaluates env-derived defaults."""
    from tinycua.cli.config import _PROJECT_DIR

    candidates = [Path.cwd() / ".env", _PROJECT_DIR / ".env"]
    loaded: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in loaded or not resolved.exists():
            continue
        load_dotenv(resolved, override=False)
        loaded.add(resolved)


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    """Register all ``tinycua run`` arguments on a parser.

    Shared between ``main.py`` (top-level subparser) and ``run.py``
    (standalone invocation) so the argument set stays in sync without
    duplication.  Env-derived defaults are resolved at call time so
    ``_load_default_env`` values are honoured.
    """
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Task prompt for the TinyCUA agent.",
    )
    parser.add_argument(
        "--prompt",
        dest="prompt_option",
        default=None,
        help="Task prompt for one-shot invocation. Overrides positional prompt.",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Workspace directory where generated files are written (default: cwd).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override TINYCUA_MODEL env var.",
    )
    parser.add_argument(
        "--provider-url",
        dest="provider_url",
        type=str,
        default=None,
        help="Override TINYCUA_BASE_URL env var (provider base URL).",
    )
    parser.add_argument(
        "--base-url",
        dest="provider_url",
        type=str,
        default=None,
        help=argparse.SUPPRESS,  # hidden alias for --provider-url
    )
    parser.add_argument(
        "--provider-type",
        dest="provider_type",
        type=str,
        default=os.environ.get("TINYCUA_PROVIDER_TYPE", "openai-chat-completions"),
        help="Provider API type: openai-chat-completions or openai-responses "
        "(default: env TINYCUA_PROVIDER_TYPE or openai-chat-completions).",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Override TINYCUA_API_KEY env var.",
    )
    parser.add_argument(
        "--worker-effort",
        choices=["none", "low", "medium", "high"],
        default=os.environ.get("TINYCUA_WORKER_EFFORT", "medium"),
        help="Analysis effort pass count (default: env TINYCUA_WORKER_EFFORT or medium).",
    )
    parser.add_argument(
        "--env",
        dest="env_file",
        type=Path,
        default=None,
        help="Path to an .env file to load before resolving config (default: src/tinycua/.env).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Maximum execution time in seconds (default: 600).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable debug logging output.",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        default=False,
        help="Print execution trace, task tree, and workspace summary after the run.",
    )
    parser.add_argument(
        "--save-artifacts",
        action="store_true",
        default=False,
        help="Save trace JSON, transcript, and logs to <dir>/.tinycua-artifacts/.",
    )


def _normalise_run_args(args: argparse.Namespace) -> None:
    """Post-process run args: merge --prompt into prompt, resolve --dir."""
    if args.prompt_option:
        args.prompt = args.prompt_option
    delattr(args, "prompt_option")
    # ponytail: resolve --dir to absolute path; default to cwd
    if args.dir is None:
        args.dir = Path.cwd()
    args.dir = args.dir.expanduser().resolve()
    # `--base-url` and `--provider-url` share dest=provider_url; the first wins.
    # Expose base_url as a compatibility alias for callers/tests.
    args.base_url = args.provider_url


def main() -> None:
    """Dispatch tinycua CLI subcommands.

    When invoked without a subcommand, shows help text and exits cleanly.
    Supported subcommands: run, benchmark, smoke-run.
    """
    # Load src/tinycua/.env (and cwd/.env) BEFORE parsing args so env-derived
    # argparse defaults (--worker-effort, --provider-type) see the user's
    # configured values. Shell-provided env vars always win.
    _load_default_env()

    parser = argparse.ArgumentParser(
        prog="tinycua",
        description="TinyCUA — Computer-Use Agent CLI.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Register 'run' subcommand with full argument set so argparse validates
    # everything in a single pass. No re-parsing via sys.argv needed.
    run_parser = subparsers.add_parser(
        "run",
        help="Run a TinyCUA agent task with a local model endpoint.",
    )
    _add_run_arguments(run_parser)

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
        _normalise_run_args(args)

        if not args.prompt:
            parser.error("the following arguments are required: prompt")

        from tinycua.cli.run import run_command

        exit_code = run_command(
            prompt=args.prompt,
            dir=args.dir,
            provider_url=args.provider_url,
            api_key=args.api_key,
            model=args.model,
            provider_type=args.provider_type,
            worker_effort=args.worker_effort,
            timeout=args.timeout,
            verbose=args.verbose,
            env_file=args.env_file,
            trace=args.trace,
            save_artifacts=args.save_artifacts,
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