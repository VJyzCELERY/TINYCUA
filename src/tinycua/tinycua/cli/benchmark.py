"""Benchmark subcommand implementation for tinycua CLI.

.. deprecated::
    ``tinycua benchmark`` is deprecated. Use ``tinycua run`` instead.
"""

from __future__ import annotations

import argparse
import logging
import warnings
from pathlib import Path

from tinycua.cli._common import create_agent, run_agent, setup_output_dir
from tinycua.cli.logging import write_log_entry

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the ``tinycua benchmark run`` subcommand.

    Args:
        argv: Command-line arguments. Uses sys.argv[2:] when None.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        prog="tinycua benchmark run",
        description="Run a TinyCUA agent benchmark task for WildClawBench evaluation.",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Task prompt for the agent (reads from TASK_PROMPT env var if not provided).",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("/tmp_workspace"),
        help="Working directory for the agent session (default: /tmp_workspace).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp_workspace/results"),
        help="Output directory for benchmark artifacts (default: /tmp_workspace/results).",
    )
    parser.add_argument(
        "--transcript",
        type=Path,
        default=Path("/tmp_workspace/transcript.jsonl"),
        help="Path for transcript output (default: /tmp_workspace/transcript.jsonl).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Maximum execution time in seconds (reads from TINYCUA_TIMEOUT env var if not provided, default: 300).",
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
        default=None,
        help="Override TINYCUA_MODEL env var (default: llama3).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable debug logging output.",
    )
    return parser.parse_args(argv)


def benchmark_run_command(
    prompt: str | None,
    workspace: Path,
    output_dir: Path,
    transcript_path: Path,
    timeout: int,
    base_url: str | None,
    api_key: str | None,
    model: str | None,
    verbose: bool,
) -> int:
    """Execute the tinycua benchmark run command.

    .. deprecated:: Use ``tinycua run`` instead.

    Orchestrates config loading, agent creation, execution with timeout
    watchdog, and artifact writing for WildClawBench benchmark evaluation.

    Args:
        prompt: Task prompt for the agent. Falls back to TASK_PROMPT env var.
        workspace: Working directory for the agent session.
        output_dir: Directory for benchmark artifact output.
        transcript_path: Path for transcript JSONL output.
        timeout: Maximum execution time in seconds.
        base_url: CLI override for base URL.
        api_key: CLI override for API key.
        model: CLI override for model name.
        verbose: Whether to enable debug logging.

    Returns:
        Exit code: 0 success, 1 error, 124 timeout.
    """
    warnings.warn(
        "tinycua benchmark is deprecated. Use tinycua run instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    import os

    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if not prompt:
        prompt = os.environ.get("TASK_PROMPT", "")
    if not prompt:
        print(
            "Error: No task prompt provided. Set --prompt or TASK_PROMPT env var.",
            flush=True,
        )
        return 1

    if not setup_output_dir(output_dir):
        print(f"Output directory not writable: {output_dir}", flush=True)
        return 1

    # Resolve workspace to absolute path — never mutate process CWD.
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    log_path = output_dir / "agent.log"

    write_log_entry(
        log_path,
        "start",
        "info",
        {
            "prompt": prompt,
            "timeout": timeout,
            "workspace": str(workspace),
            "output": str(output_dir),
        },
    )

    agent, _config = create_agent(log_path, base_url, api_key, model)
    if agent is None:
        return 1

    return run_agent(agent, prompt, timeout, output_dir, transcript_path, log_path)
