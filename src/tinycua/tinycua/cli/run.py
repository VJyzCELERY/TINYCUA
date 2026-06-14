"""Run subcommand implementation for tinycua CLI."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from tinycua.cli._common import create_agent, run_agent, setup_output_dir
from tinycua.cli.logging import write_log_entry

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the ``tinycua run`` subcommand.

    Args:
        argv: Command-line arguments. Uses sys.argv[1:] when None.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        prog="tinycua run",
        description="Run a TinyCUA agent task with a local model endpoint.",
    )
    parser.add_argument(
        "prompt",
        help="Task prompt for the TinyCUA agent.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Maximum execution time in seconds (default: 600).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp_workspace/results"),
        help="Output directory for transcript and log files (default: /tmp_workspace/results).",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("/tmp_workspace"),
        help="Working directory for the agent session (default: /tmp_workspace).",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Override TINYCUA_BASE_URL env var.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Override TINYCUA_API_KEY env var.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="llama3",
        help="Override TINYCUA_MODEL env var (default: llama3).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable debug logging output.",
    )
    return parser.parse_args(argv)


def run_command(
    prompt: str,
    timeout: int,
    output_dir: Path,
    workspace: Path,
    base_url: str | None,
    api_key: str | None,
    model: str | None,
    verbose: bool,
) -> int:
    """Execute the tinycua run command.

    Orchestrates config loading, agent creation, execution with timeout
    watchdog, and transcript/log writing.

    Args:
        prompt: Task prompt for the agent.
        timeout: Maximum execution time in seconds.
        output_dir: Directory for transcript and log output.
        workspace: Working directory for the agent session.
        base_url: CLI override for base URL.
        api_key: CLI override for API key.
        model: CLI override for model name.
        verbose: Whether to enable debug logging.

    Returns:
        Exit code: 0 success, 1 error, 124 timeout.
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if not setup_output_dir(output_dir):
        print(f"Output directory not writable: {output_dir}", flush=True)
        return 1

    workspace.mkdir(parents=True, exist_ok=True)
    os.chdir(workspace)

    log_path = output_dir / "agent.log"
    transcript_path = output_dir / "transcript.jsonl"

    write_log_entry(log_path, "start", "info", {"prompt": prompt, "timeout": timeout})

    agent, _config = create_agent(log_path, base_url, api_key, model)
    if agent is None:
        return 1

    return run_agent(agent, prompt, timeout, output_dir, transcript_path, log_path)
