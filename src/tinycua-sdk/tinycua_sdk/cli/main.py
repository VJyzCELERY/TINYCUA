"""CLI main entry point.

.. deprecated::
    This module has been moved to ``tinycua.cli.main``.
    Import from ``tinycua_sdk.cli.main`` will continue to work
    but will emit a deprecation warning.
"""

import sys
import warnings

warnings.warn(
    "tinycua_sdk.cli.main is deprecated. Use tinycua.cli.main instead.",
    DeprecationWarning,
    stacklevel=2,
)


def main() -> int:
    """Run the tinycua CLI.

    Returns:
        Exit code (0 for success, 1 for help/no command).

    """
    import argparse

    parser = argparse.ArgumentParser(prog="tinycua", description="TINYCUA SDK CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("repl", help="Start interactive REPL")

    run_parser = subparsers.add_parser("run", help="Run a Python script")
    run_parser.add_argument("file", help="Script file to run")

    deploy_parser = subparsers.add_parser("deploy", help="Deploy tools")
    deploy_parser.add_argument("file", help="File containing tools to deploy")

    # Agent subparser (deprecated path)
    agent_parser = subparsers.add_parser("agent", help="Manage agents")
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command")

    # create command
    create_parser = agent_subparsers.add_parser("create", help="Create an agent")
    create_parser.add_argument(
        "path",
        nargs="?",
        help="Path to AGENT.md file or directory containing AGENT.md",
    )
    create_parser.add_argument(
        "--template",
        help="Template name (coder, researcher, assistant)",
    )
    create_parser.add_argument(
        "--model",
        help="Override model (e.g., gpt-4o, gpt-5-nano)",
    )
    create_parser.add_argument(
        "--provider",
        help="Override provider (e.g., openai, ollama)",
    )
    create_parser.add_argument(
        "--tools",
        help="Override tools (comma-separated list)",
    )
    create_parser.add_argument(
        "--skills",
        help="Override skills (comma-separated list)",
    )
    create_parser.add_argument(
        "--loop",
        help="Override loop type (default, react, plan)",
    )
    create_parser.add_argument(
        "--temperature",
        type=float,
        help="Override temperature (0.0-2.0)",
    )
    create_parser.add_argument(
        "--override-file",
        help="Path to JSON or YAML file with override values (CLI args take precedence)",
    )

    # templates command
    templates_parser = agent_subparsers.add_parser(
        "templates", help="List available agent templates"
    )
    templates_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed template information",
    )

    # info command
    info_parser = agent_subparsers.add_parser(
        "info", help="Show agent configuration details"
    )
    info_parser.add_argument(
        "--file",
        help="Path to AGENT.md file",
    )
    info_parser.add_argument(
        "--template",
        help="Template name",
    )

    args = parser.parse_args()

    if args.command == "repl":
        from tinycua_sdk.cli.repl import run_repl

        return run_repl()
    if args.command == "run":
        print("Running script...")
        return 0
    if args.command == "deploy":
        print("Deploying tools...")
        return 0

    if args.command == "agent":
        import asyncio

        from tinycua_sdk.cli.agent_commands import (
            cmd_agent_create,
            cmd_agent_info,
            cmd_agent_templates,
        )

        if args.agent_command == "create":
            return asyncio.run(cmd_agent_create(args))
        if args.agent_command == "templates":
            return asyncio.run(cmd_agent_templates(args))
        if args.agent_command == "info":
            return asyncio.run(cmd_agent_info(args))

        agent_parser.print_help()
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
