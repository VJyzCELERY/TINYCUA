"""Shared utilities for tinycua CLI subcommands."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import time
import threading
from pathlib import Path

from tinycua.cli.config import load_config
from tinycua.cli.logging import write_log_entry
from tinycua.cli.transcript import write_transcript
from tinycua.factory import create_tinycua_agent

logger = logging.getLogger(__name__)


def run_async_safely(coro: object) -> object:
    """Run an async coroutine safely, handling nested event loop cases.

    In normal CLI invocation, there is no running event loop, so
    asyncio.run() works directly. If called from within an existing
    async context, we run the coroutine in a new thread with its own
    event loop to avoid nesting.

    Args:
        coro: The async coroutine to run.

    Returns:
        The result of the coroutine.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    def _run_in_new_loop() -> object:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run_in_new_loop)
        return future.result()


async def run_agent_with_timeout(
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


def setup_output_dir(output_dir: Path) -> bool:
    """Ensure output directory exists and is writable.

    Args:
        output_dir: Directory to create and test.

    Returns:
        True if writable, False otherwise.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    _test_file = output_dir / ".write_test"
    try:
        _test_file.touch()
        _test_file.unlink()
    except OSError:
        return False
    return True


def create_agent(
    log_path: Path,
    base_url: str | None,
    api_key: str | None,
    model: str | None,
) -> tuple[object | None, dict[str, str]]:
    """Load config and create a TinyCUA agent.

    Args:
        log_path: Path for logging.
        base_url: CLI override for base URL.
        api_key: CLI override for API key.
        model: CLI override for model name.

    Returns:
        Tuple of (agent, config) or (None, config) on error.
    """
    try:
        config = load_config(base_url, api_key, model)
    except ValueError as e:
        write_log_entry(log_path, "config", "error", {"error": str(e)})
        print(f"Configuration error: {e}", flush=True)
        return None, {}

    write_log_entry(
        log_path,
        "config",
        "info",
        {"base_url": config["base_url"], "model": config["model"]},
    )

    try:
        agent = create_tinycua_agent(
            base_url=config["base_url"],
            api_key=config["api_key"],
            model=config["model"],
        )
    except Exception as e:
        write_log_entry(
            log_path, "error", "error", {"error": str(e), "phase": "agent_creation"}
        )
        print(f"Failed to create agent: {e}", flush=True)
        return None, config

    return agent, config


def run_agent(
    agent: object,
    prompt: str,
    timeout: int,
    output_dir: Path,
    transcript_path: Path,
    log_path: Path,
) -> int:
    """Run the agent with timeout watchdog and write artifacts.

    Args:
        agent: The TinyCUA agent instance.
        prompt: Task prompt string.
        timeout: Maximum execution time in seconds.
        output_dir: Directory for artifact output.
        transcript_path: Path for transcript JSONL output.
        log_path: Path for log output.

    Returns:
        Exit code: 0 success, 1 error, 124 timeout.
    """
    timeout_event = threading.Event()

    def _timeout_handler() -> None:
        timeout_event.set()

    timer = threading.Timer(timeout, _timeout_handler)
    timer.daemon = True
    timer.start()

    start_time = time.monotonic()
    write_log_entry(log_path, "agent_run", "info", {"prompt": prompt})

    try:
        result = run_async_safely(run_agent_with_timeout(agent, prompt, timeout_event))
        elapsed = time.monotonic() - start_time

        if timeout_event.is_set():
            write_log_entry(
                log_path, "timeout", "warning", {"timeout": timeout, "elapsed": elapsed}
            )
            print(f"Agent timed out after {timeout}s", flush=True)
            return 124

        write_log_entry(
            log_path,
            "complete",
            "info",
            {"elapsed": elapsed, "result_length": len(result) if result else 0},
        )

        loop = agent.loop
        working_messages = getattr(loop, "_working_messages", [])
        if not working_messages:
            logger.warning(
                "No working messages found for transcript — check agent implementation"
            )
        write_transcript(working_messages, transcript_path)

        print(f"Agent completed in {elapsed:.1f}s", flush=True)
        if result:
            print(result, flush=True)

        return 0
    except asyncio.CancelledError:
        elapsed = time.monotonic() - start_time
        write_log_entry(
            log_path, "timeout", "warning", {"timeout": timeout, "elapsed": elapsed}
        )
        return 124
    except Exception as e:
        elapsed = time.monotonic() - start_time
        write_log_entry(
            log_path, "error", "error", {"error": str(e), "elapsed": elapsed}
        )
        print(f"Agent error: {e}", flush=True)
        return 1
    finally:
        timer.cancel()
