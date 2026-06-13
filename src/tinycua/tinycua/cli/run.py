"""Run subcommand implementation for tinycua CLI."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
import threading
from pathlib import Path

from tinycua.cli.config import load_config
from tinycua.cli.logging import write_log_entry
from tinycua.cli.transcript import write_transcript
from tinycua.factory import create_tinycua_agent

logger = logging.getLogger(__name__)


def _run_async_safely(coro: object) -> object:
    """Run an async coroutine safely, handling nested event loop cases.

    In normal CLI invocation (python -m tinycua run), there is no running
    event loop, so asyncio.run() works directly. If called from within an
    existing async context (e.g., Jupyter, another framework), we run the
    coroutine in a new thread with its own event loop to avoid nesting.

    Args:
        coro: The async coroutine to run.

    Returns:
        The result of the coroutine.
    """
    import concurrent.futures

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — safe to use asyncio.run()
        return asyncio.run(coro)

    # There's a running loop. We can't nest event loops directly.
    # Run in a new thread with its own event loop.
    def _run_in_new_loop() -> object:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run_in_new_loop)
        return future.result()


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

    # Ensure output directory exists and is writable
    output_dir.mkdir(parents=True, exist_ok=True)
    _test_file = output_dir / ".write_test"
    try:
        _test_file.touch()
        _test_file.unlink()
    except OSError:
        print(f"Output directory not writable: {output_dir}", flush=True)
        return 1

    # Ensure workspace directory exists before setting it as working dir (FR-011)
    workspace.mkdir(parents=True, exist_ok=True)
    os.chdir(workspace)

    log_path = output_dir / "agent.log"
    transcript_path = output_dir / "transcript.jsonl"

    write_log_entry(log_path, "start", "info", {"prompt": prompt, "timeout": timeout})

    try:
        config = load_config(base_url, api_key, model)
    except ValueError as e:
        write_log_entry(log_path, "config", "error", {"error": str(e)})
        print(f"Configuration error: {e}", flush=True)
        return 1

    write_log_entry(log_path, "config", "info", {
        "base_url": config["base_url"],
        "model": config["model"],
    })

    try:
        agent = create_tinycua_agent(
            base_url=config["base_url"],
            api_key=config["api_key"],
            model=config["model"],
        )
    except Exception as e:
        write_log_entry(log_path, "error", "error", {"error": str(e), "phase": "agent_creation"})
        print(f"Failed to create agent: {e}", flush=True)
        return 1

    # Timeout watchdog: set an event after timeout seconds
    timeout_event = threading.Event()

    def _timeout_handler() -> None:
        timeout_event.set()

    timer = threading.Timer(timeout, _timeout_handler)
    timer.daemon = True
    timer.start()

    start_time = time.monotonic()
    write_log_entry(log_path, "agent_run", "info", {"prompt": prompt})

    try:
        result = _run_async_safely(_run_agent_with_timeout(agent, prompt, timeout_event))
        elapsed = time.monotonic() - start_time

        if timeout_event.is_set():
            write_log_entry(log_path, "timeout", "warning", {"timeout": timeout, "elapsed": elapsed})
            print(f"Agent timed out after {timeout}s", flush=True)
            return 124

        write_log_entry(log_path, "complete", "info", {
            "elapsed": elapsed,
            "result_length": len(result) if result else 0,
        })

        # Write transcript from working messages
        loop = agent.loop
        working_messages = getattr(loop, "_working_messages", [])
        write_transcript(working_messages, transcript_path)

        print(f"Agent completed in {elapsed:.1f}s", flush=True)
        if result:
            print(result, flush=True)

        return 0
    except asyncio.CancelledError:
        elapsed = time.monotonic() - start_time
        write_log_entry(log_path, "timeout", "warning", {"timeout": timeout, "elapsed": elapsed})
        return 124
    except Exception as e:
        elapsed = time.monotonic() - start_time
        write_log_entry(log_path, "error", "error", {"error": str(e), "elapsed": elapsed})
        print(f"Agent error: {e}", flush=True)
        return 1
    finally:
        timer.cancel()


async def _run_agent_with_timeout(
    agent: object,
    prompt: str,
    timeout_event: threading.Event,
) -> str:
    """Run the agent with cooperative timeout checking.

    Args:
        agent: The TinyCUA agent instance.
        prompt: Task prompt string.
        timeout_event: Threading event set when timeout expires.

    Returns:
        The agent response string.
    """
    run_task = asyncio.create_task(agent.run(prompt))  # type: ignore[union-attr]

    while not run_task.done():
        if timeout_event.is_set():
            run_task.cancel()
            try:
                await run_task
            except asyncio.CancelledError:
                pass
            raise asyncio.CancelledError
        await asyncio.sleep(0.1)

    return run_task.result()
