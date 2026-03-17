"""CLI main entry point."""

import sys


def main() -> int:
    """Run the tinycua CLI."""
    import argparse

    parser = argparse.ArgumentParser(prog="tinycua", description="TINYCUA SDK CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("repl", help="Start interactive REPL")

    run_parser = subparsers.add_parser("run", help="Run a Python script")
    run_parser.add_argument("file", help="Script file to run")

    deploy_parser = subparsers.add_parser("deploy", help="Deploy tools")
    deploy_parser.add_argument("file", help="File containing tools to deploy")

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

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
