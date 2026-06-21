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

from dotenv import load_dotenv

from tinycua.cli.config import build_language_model
from tinycua.cli.config import load_config
from tinycua.cli.live_stream import print_summary as print_live_summary
from tinycua.cli.live_stream import run_streaming
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

    Streaming is always on (no ``--stream`` flag). The default workdir is the
    current working directory. Env-derived defaults (``--worker-effort``,
    ``--provider-type``, ``--model``, ``--provider-url``, ``--api-key``) are
    resolved after ``_load_default_env`` runs in ``main()``, so values set in
    ``src/tinycua/.env`` are honored.

    Args:
        argv: Command-line arguments. Uses sys.argv[1:] when None.

    Returns:
        Parsed argument namespace.
    """
    from tinycua.cli.main import _add_run_arguments, _normalise_run_args

    parser = argparse.ArgumentParser(
        prog="tinycua run",
        description="Run a TinyCUA agent task. Streams node/tool activity live.",
    )
    _add_run_arguments(parser)
    args = parser.parse_args(argv)
    _normalise_run_args(args)
    return args


def run_command(
    prompt: str,
    dir: Path,
    provider_url: str | None,
    api_key: str | None,
    model: str | None,
    provider_type: str | None,
    worker_effort: str,
    timeout: int,
    verbose: bool,
    env_file: Path | None,
    trace: bool = False,
    task_tree: bool = False,
    save_artifacts: bool = False,
    no_tool_audit: bool = False,
    allow_open_question: bool = False,
) -> int:
    """Execute the tinycua run command (always streaming).

    By default, only live streaming output and the final response are shown.
    Use --trace to print the execution trace, task tree, and workspace summary.
    Use --task-tree to print only the flat task tree (lighter than --trace).
    Use --save-artifacts to write trace JSON, transcript, and logs to
    ``<dir>/.tinycua-artifacts/``.

    Args:
        prompt: Task prompt for the agent.
        dir: Workspace directory where generated files are written.
        provider_url: CLI override for provider base URL.
        api_key: CLI override for API key.
        model: CLI override for model name.
        provider_type: CLI override for provider type (chat-completions/responses).
        worker_effort: Analysis effort setting passed to worker runtime.
        timeout: Maximum execution time in seconds.
        verbose: Whether to enable debug logging.
        env_file: Optional .env file to load before resolving config.
        trace: Print execution trace, task tree, and workspace summary.
        task_tree: Print only the flat task tree after the run.
        save_artifacts: Write trace JSON, transcript, and logs to disk.
        no_tool_audit: Suppress per-tool-call audit JSON files.
        allow_open_question: Allow OPEN_QUESTION reviewer decisions to bail
            to ResponseNode. Disabled by default for one-shot worker mode.

    Returns:
        Exit code: 0 success, 1 error, 124 timeout.
    """
    # Load an explicit --env file if provided (the project .env was already
    # loaded by _load_default_env in main() before argparse ran).
    if env_file is not None and env_file.exists():
        load_dotenv(env_file, override=False)

    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Resolve workspace to an absolute path. ``dir`` arrives already
    # absolute from ``_normalise_run_args`` but we ensure it here too so
    # that ``run_command`` is safe when called directly (e.g. scripts).
    workspace = Path(dir).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    artifact_dir: Path | None = None
    log_path: Path | None = None
    transcript_path: Path | None = None

    if save_artifacts:
        artifact_dir = workspace / ".tinycua-artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        # Ensure artifact directory is writable
        _test_file = artifact_dir / ".write_test"
        try:
            _test_file.touch()
            _test_file.unlink()
        except OSError:
            print(f"Artifact directory not writable: {artifact_dir}", flush=True)
            return 1

        log_path = artifact_dir / "agent.log"
        transcript_path = artifact_dir / "transcript.jsonl"

        write_log_entry(log_path, "start", "info", {"prompt": prompt, "timeout": timeout})

    try:
        config = load_config(provider_url, api_key, model, provider_type)
    except ValueError as e:
        if log_path:
            write_log_entry(log_path, "config", "error", {"error": str(e)})
        print(f"Configuration error: {e}", flush=True)
        return 1

    if log_path:
        write_log_entry(log_path, "config", "info", {
            "base_url": config["base_url"],
            "model": config["model"],
            "provider_type": config["provider_type"],
        })

    try:
        agent = create_tinycua_agent(
            session_config=SessionConfig(
                workspace_dir=workspace,
                artifact_dir=artifact_dir,
                worker_effort=worker_effort,
                disable_tool_audit=no_tool_audit,
                enable_open_question_review=allow_open_question,
            ),
            llm_model=build_language_model(config),
        )
    except Exception as e:
        if log_path:
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
    if log_path:
        write_log_entry(log_path, "agent_run", "info", {"prompt": prompt})

    try:
        # Streaming is always on: run_streaming renders node/tool activity live
        # and returns the final response text.
        result = _run_async_safely(run_streaming(agent, prompt))
        elapsed = time.monotonic() - start_time

        if timeout_event.is_set():
            if log_path:
                write_log_entry(log_path, "timeout", "warning", {"timeout": timeout, "elapsed": elapsed})
            print(f"Agent timed out after {timeout}s", flush=True)
            return 124

        if log_path:
            write_log_entry(log_path, "complete", "info", {
                "elapsed": elapsed,
                "result_length": len(result) if result else 0,
            })

        # Write transcript and runtime exports only when --save-artifacts is set
        loop = agent.loop

        if save_artifacts and artifact_dir is not None and transcript_path is not None and log_path is not None:
            working_messages = getattr(loop, "_working_messages", [])
            usage_events = loop.get_usage_events()

            # Primary transcript: OpenClaw-compatible format
            openclaw_records = convert_working_messages_to_openclaw(
                working_messages, usage_events,
            )
            write_openclaw_jsonl(openclaw_records, transcript_path)

            # Backward-compatible raw transcript
            raw_transcript_path = artifact_dir / "transcript.raw.jsonl"
            write_transcript(working_messages, raw_transcript_path)

            # Usage summary
            usage_path = artifact_dir / "usage.json"
            write_usage_summary(usage_path, usage_events, elapsed)

            _write_runtime_exports(loop, artifact_dir)

        print(f"Agent completed in {elapsed:.1f}s", flush=True)
        # In trace mode the final response is printed under the
        # === FINAL RESPONSE === header by print_summary; otherwise print it
        # bare as the default user-facing output.
        if result and not trace:
            print(result, flush=True)
        print_live_summary(loop, workspace, artifact_dir, result, trace=trace, task_tree=task_tree)

        return 0
    except asyncio.CancelledError:
        elapsed = time.monotonic() - start_time
        if log_path:
            write_log_entry(log_path, "timeout", "warning", {"timeout": timeout, "elapsed": elapsed})
        return 124
    except Exception as e:
        elapsed = time.monotonic() - start_time
        if log_path:
            write_log_entry(log_path, "error", "error", {"error": str(e), "elapsed": elapsed})
        print(f"Agent error: {e}", flush=True)
        return 1
    finally:
        timer.cancel()


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
        transcript_text = str(
            _safe_loop_call(
                loop,
                "get_transcript_text",
                default=state_snapshot.get("transcript_text", ""),
                include_node_calls=True,
            )
        )
        (output_dir / "transcript.txt").write_text(transcript_text, encoding="utf-8")


def _safe_loop_call(loop: Any, method_name: str, *, default: Any, **kwargs: Any) -> Any:
    """Call an optional loop export method and return default on absence/error."""
    method = getattr(loop, method_name, None)
    if not callable(method):
        return default
    try:
        return method(**kwargs)
    except Exception:  # noqa: BLE001 - export failure must not fail a completed run.
        logger.debug("runtime_export_failed method=%s", method_name, exc_info=True)
        return default
