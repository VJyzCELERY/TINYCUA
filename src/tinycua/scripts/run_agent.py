"""Run TinyCUA from a simple script entrypoint.

This is a thin shim over the ``tinycua run`` CLI command. It preserves the
``--dir``/``--prompt``/``--stream`` invocation shape for backward compatibility
while delegating to :func:`tinycua.cli.run.run_command`.

Usage:
    uv run python ./scripts/run_agent.py --dir ./tmp/demo --prompt "Say hi"

Streaming is always on. The ``tinycua run`` CLI is the primary entry point;
this script exists so existing invocations keep working.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from tinycua.cli.config import _load_default_env
from tinycua.cli.run import run_command

PROJECT_DIR = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the script's backward-compatible argument shape.

    Maps the script flags onto the ``tinycua run`` command's arg names so
    :func:`run_command` receives what it expects. ``--stream`` is accepted
    but ignored (streaming is always on).
    """
    parser = argparse.ArgumentParser(
        description="Run a TinyCUA agent prompt with local artifacts and trace output.",
    )
    parser.add_argument(
        "--prompt", required=True, help="Natural language prompt to run."
    )
    parser.add_argument("--dir", required=True, type=Path, help="Workspace directory.")
    parser.add_argument("--output-dir", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument(
        "--stream", action="store_true", default=False, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--env-file", type=Path, default=Path(".env"), help="Env file to load."
    )
    parser.add_argument("--base-url", default=None, help="Override TINYCUA_BASE_URL.")
    parser.add_argument("--api-key", default=None, help="Override TINYCUA_API_KEY.")
    parser.add_argument("--model", default=None, help="Override TINYCUA_MODEL.")
    parser.add_argument(
        "--worker-effort",
        choices=["none", "low", "medium", "high"],
        default=os.environ.get("TINYCUA_WORKER_EFFORT", "medium"),
        help="Analysis effort pass count; default: env TINYCUA_WORKER_EFFORT or medium.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Script entrypoint — delegates to the ``tinycua run`` command."""
    # Load src/tinycua/.env before parsing args so env-derived defaults resolve.
    _load_default_env()
    args = parse_args(argv)

    # An explicit --env-file (non-default) is loaded in addition to the
    # project .env already loaded by _load_default_env.
    if args.env_file and args.env_file != Path(".env") and args.env_file.exists():
        load_dotenv(args.env_file, override=False)

    return run_command(
        prompt=args.prompt,
        dir=args.dir,
        provider_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
        provider_type=os.environ.get(
            "TINYCUA_PROVIDER_TYPE", "openai-chat-completions"
        ),
        worker_effort=args.worker_effort,
        timeout=600,
        verbose=False,
        env_file=args.env_file,
    )


if __name__ == "__main__":
    raise SystemExit(main())
