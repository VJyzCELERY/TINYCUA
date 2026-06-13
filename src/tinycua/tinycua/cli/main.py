"""CLI entry point for tinycua with subcommand dispatch."""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    """Dispatch tinycua CLI subcommands.

    When invoked without a subcommand, shows help text and exits cleanly.
    Supported subcommands: run.
    """
    parser = argparse.ArgumentParser(
        prog="tinycua",
        description="TinyCUA — Computer-Use Agent CLI.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Register 'run' subcommand
    run_parser = subparsers.add_parser(
        "run",
        help="Run a TinyCUA agent task with a local model endpoint.",
    )
    run_parser.add_argument("prompt", nargs="?", help="Task prompt for the agent.")
    run_parser.add_argument("--timeout", type=int, default=600, help="Max execution seconds (default: 600).")
    run_parser.add_argument("--output-dir", type=str, default="/tmp_workspace/results", help="Output directory.")
    run_parser.add_argument("--workspace", type=str, default="/tmp_workspace", help="Working directory.")
    run_parser.add_argument("--base-url", type=str, default=None, help="Override TINYCUA_BASE_URL.")
    run_parser.add_argument("--api-key", type=str, default=None, help="Override TINYCUA_API_KEY.")
    run_parser.add_argument("--model", type=str, default=None, help="Override TINYCUA_MODEL.")
    run_parser.add_argument("--verbose", action="store_true", default=False, help="Debug logging.")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        raise SystemExit(0)

    if args.command == "run":
        from pathlib import Path

        from tinycua.cli.run import run_command

        if not args.prompt:
            run_parser.error("the following arguments are required: prompt")

        exit_code = run_command(
            prompt=args.prompt,
            timeout=args.timeout,
            output_dir=Path(args.output_dir),
            workspace=Path(args.workspace),
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            verbose=args.verbose,
        )
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
