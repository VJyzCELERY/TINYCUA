"""Run subcommand implementation for tinycua CLI."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
import threading
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from tinycua_sdk.agent import Agent

from tinycua.cli.config import load_config
from tinycua.cli.logging import write_log_entry
from tinycua.cli.transcript import (
    convert_working_messages_to_openclaw,
    write_openclaw_jsonl,
    write_transcript,
    write_usage_summary,
)
from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent

logger = logging.getLogger(__name__)


def _run_async_safely(coro: Coroutine[Any, Any, str]) -> str:
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
    def _run_in_new_loop() -> str:
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

    # Ensure workspace directory exists and pass it through the public session
    # filesystem contract instead of mutating process-global CWD.
    workspace.mkdir(parents=True, exist_ok=True)

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
            session_config=SessionConfig(
                workspace_dir=workspace,
                artifact_dir=output_dir,
            ),
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
        usage_events = loop.get_usage_events()

        # Primary transcript: OpenClaw-compatible format
        openclaw_records = convert_working_messages_to_openclaw(
            working_messages, usage_events,
        )
        write_openclaw_jsonl(openclaw_records, transcript_path)

        # Backward-compatible raw transcript
        raw_transcript_path = output_dir / "transcript.raw.jsonl"
        write_transcript(working_messages, raw_transcript_path)

        # Usage summary
        usage_path = output_dir / "usage.json"
        write_usage_summary(usage_path, usage_events, elapsed)

        _write_runtime_exports(loop, output_dir)

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
    agent: Agent,
    prompt: str,
    timeout_event: threading.Event,
) -> str:
    """Run the agent with cooperative timeout checking.

    Uses streaming mode to enable usage event capture. Events are
    consumed but not yielded — the final response string is returned.

    Args:
        agent: The TinyCUA agent instance.
        prompt: Task prompt string.
        timeout_event: Threading event set when timeout expires.

    Returns:
        The agent response string.
    """
    stream_iter = await agent.run(prompt, stream=True)
    result = ""
    try:
        async for event in stream_iter:
            if timeout_event.is_set():
                raise asyncio.CancelledError
            if event.get("type") == "response.output_text.delta":
                result += event.get("delta", "")
    except asyncio.CancelledError:
        raise
    return result


def _write_runtime_exports(loop: Any, output_dir: Path) -> None:
    """Write trace, state, task tree, and final-response event artifacts."""
    state_snapshot = _safe_loop_call(loop, "get_state_snapshot", default={})
    exports = {
        "execution_trace.json": _safe_loop_call(loop, "get_execution_trace", default=[]),
        "state_snapshot.json": state_snapshot,
        "task_tree.json": state_snapshot.get("task_tree", {})
        if isinstance(state_snapshot, dict)
        else {},
        "transcript_events.json": _safe_loop_call(
            loop,
            "get_transcript_events",
            default=[],
        ),
        "final_response_events.json": _safe_loop_call(
            loop,
            "get_final_response_events",
            default=[],
        ),
    }
    for filename, payload in exports.items():
        (output_dir / filename).write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )
    if isinstance(state_snapshot, dict):
        task_tree_text = str(state_snapshot.get("task_tree_text", "No tasks."))
        (output_dir / "task_tree.txt").write_text(task_tree_text, encoding="utf-8")
        transcript_text = str(state_snapshot.get("transcript_text", ""))
        (output_dir / "transcript.txt").write_text(transcript_text, encoding="utf-8")


def _safe_loop_call(loop: Any, method_name: str, *, default: Any) -> Any:
    """Call an optional loop export method and return default on absence/error."""
    method = getattr(loop, method_name, None)
    if not callable(method):
        return default
    try:
        return method()
    except Exception:  # noqa: BLE001 - export failure must not fail a completed run.
        logger.debug("runtime_export_failed method=%s", method_name, exc_info=True)
        return default
