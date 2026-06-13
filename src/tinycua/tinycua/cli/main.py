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
    subparsers.add_parser(
        "run",
        help="Run a TinyCUA agent task with a local model endpoint.",
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


if __name__ == "__main__":
    main()
