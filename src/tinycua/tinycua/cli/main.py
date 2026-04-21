"""TINYCUA CLI entry point."""

from __future__ import annotations

import argparse
import asyncio
import sys


def main() -> int:
    """Run the tinycua CLI.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    parser = argparse.ArgumentParser(
        prog="tinycua",
        description="TINYCUA - Computer-Use Agent CLI",
    )
    parser.add_argument(
        "--no-wizard",
        action="store_true",
        help="Skip setup wizard on first startup",
    )
    parser.add_argument(
        "--force-wizard",
        action="store_true",
        help="Force run setup wizard",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("repl", help="Start interactive REPL")

    run_parser = subparsers.add_parser("run", help="Run agent with input")
    run_parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Input string to send to agent",
    )
    run_parser.add_argument(
        "--file",
        default=None,
        help="Script file to read and execute",
    )

    deploy_parser = subparsers.add_parser("deploy", help="Deploy agent to backend")
    deploy_parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Agent definition file (optional)",
    )
    deploy_parser.add_argument(
        "--backend-url",
        default=None,
        help="Backend server URL",
    )
    deploy_parser.add_argument(
        "--api-key",
        default=None,
        help="Backend API key",
    )

    chat_parser = subparsers.add_parser("chat", help="Start interactive chat session")
    chat_parser.add_argument(
        "--agent",
        default=None,
        help="Agent name to chat with",
    )

    subparsers.add_parser("tui", help="Launch Textual TUI application")

    # Agent subparser
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

    if args.command is None or args.force_wizard or (not args.no_wizard and args.command in ("repl", "chat", "tui", None)):
        from tinycua.config import is_first_startup, run_wizard

        if args.force_wizard or is_first_startup():
            run_wizard()
            if args.command is None:
                return 0

    if args.command == "repl":
        from tinycua.cli.repl import run_repl

        return run_repl()

    if args.command == "run":
        from tinycua.cli.commands import cmd_run

        return asyncio.run(cmd_run(args))

    if args.command == "deploy":
        from tinycua.cli.commands import cmd_deploy

        return asyncio.run(cmd_deploy(args))

    if args.command == "chat":
        from tinycua.cli.commands import cmd_chat

        return asyncio.run(cmd_chat(args))

    if args.command == "tui":
        from tinycua.cli.commands import cmd_tui

        return asyncio.run(cmd_tui(args))

    if args.command == "agent":
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
