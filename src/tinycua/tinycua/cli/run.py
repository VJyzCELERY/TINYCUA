"""Run subcommand implementation for tinycua CLI."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
import threading
from collections.abc import Coroutine
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent

from tinycua.cli.config import build_language_model
from tinycua.cli.config import load_config
from tinycua.cli.live_stream import print_node_traversal
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


def _prepare_run_workspace(
    dir: Path,
    save_artifacts: bool,
    prompt: str,
    timeout: int,
) -> tuple[Path, Path | None, Path | None, Path | None] | int:
    """Resolve workspace + artifact dirs. Returns (workspace, artifact_dir, log_path, transcript_path) or 1 on error."""
    workspace = Path(dir).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    artifact_dir: Path | None = None
    log_path: Path | None = None
    transcript_path: Path | None = None

    if save_artifacts:
        artifact_dir = workspace / ".tinycua-artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        _test_file = artifact_dir / ".write_test"
        try:
            _test_file.touch()
            _test_file.unlink()
        except OSError:
            print(
                f"Artifact directory not writable: {artifact_dir}",
                file=sys.stderr,
                flush=True,
            )
            return 1
        log_path = artifact_dir / "agent.log"
        transcript_path = artifact_dir / "transcript.jsonl"
        write_log_entry(
            log_path, "start", "info", {"prompt": prompt, "timeout": timeout}
        )

    return workspace, artifact_dir, log_path, transcript_path


def _load_run_config(
    provider_url: str | None,
    api_key: str | None,
    model: str | None,
    provider_type: str | None,
    log_path: Path | None,
) -> dict | int:
    """Load run config. Returns config dict or 1 on error."""
    try:
        config = load_config(provider_url, api_key, model, provider_type)
    except ValueError as e:
        if log_path:
            write_log_entry(log_path, "config", "error", {"error": str(e)})
        print(f"Configuration error: {e}", file=sys.stderr, flush=True)
        return 1
    if log_path:
        write_log_entry(
            log_path,
            "config",
            "info",
            {
                "base_url": config["base_url"],
                "model": config["model"],
                "provider_type": config["provider_type"],
            },
        )
    return config


def _resolve_max_context(
    config: dict, cli_override: int | None, log_path: Path | None
) -> int | None:
    """Resolve the real max_context for compaction (FR-084).

    Priority: explicit ``--max-context`` CLI flag > server probe > None
    (let the SDK default of 128000 apply).

    Args:
        config: The run config dict (must have base_url, api_key, model).
        cli_override: The ``--max-context`` CLI flag value, or None.
        log_path: Optional artifact log path for recording the resolution.

    Returns:
        The resolved max_context (int), or None when the SDK default should
        apply (no override and probe skipped/failed).
    """
    if cli_override is not None and cli_override > 0:
        if log_path:
            write_log_entry(
                log_path,
                "max_context",
                "info",
                {"source": "cli", "value": cli_override},
            )
        return cli_override

    # Probe the server best-effort. Runs synchronously here since this is
    # before the async agent loop starts. Uses a fresh event loop.
    import asyncio

    from tinycua.cli.model_probe import resolve_max_context

    try:
        resolved = asyncio.get_event_loop().run_until_complete(
            resolve_max_context(
                config["base_url"],
                config["api_key"],
                config["model"],
                fallback=128000,
            )
        )
    except RuntimeError:
        # No running loop — use asyncio.run for a one-shot call.
        resolved = asyncio.run(
            resolve_max_context(
                config["base_url"],
                config["api_key"],
                config["model"],
                fallback=128000,
            )
        )
    if log_path:
        write_log_entry(
            log_path, "max_context", "info", {"source": "probe", "value": resolved}
        )
    # Only return when different from the SDK default so we don't redundantly
    # pass 128000 (let the SDK default apply naturally via None).
    if resolved == 128000:
        return None
    return resolved


def _build_run_agent(
    config: dict,
    workspace: Path,
    artifact_dir: Path | None,
    worker_effort: str,
    no_tool_audit: bool,
    allow_open_question: bool,
    replan_threshold: int | None,
    log_path: Path | None,
    recovery_strategy: str = "standard",
) -> Agent | int:
    """Build the tinycua agent. Returns the agent or 1 on error."""
    try:
        from tinycua.compaction.simple import SimpleCompaction

        agent = create_tinycua_agent(
            session_config=SessionConfig(
                workspace_dir=workspace,
                artifact_dir=artifact_dir,
                worker_effort=worker_effort,
                disable_tool_audit=no_tool_audit,
                enable_open_question_review=allow_open_question,
                replan_threshold=replan_threshold
                if replan_threshold is not None
                else 5,
                compaction_strategy=SimpleCompaction(),  # FR-082
                recovery_strategy=recovery_strategy,  # FR-087
            ),
            llm_model=build_language_model(
                config, max_context=config.get("max_context")
            ),
        )
    except Exception as e:
        if log_path:
            write_log_entry(
                log_path, "error", "error", {"error": str(e), "phase": "agent_creation"}
            )
        print(f"Failed to create agent: {e}", file=sys.stderr, flush=True)
        return 1
    return agent


def _write_run_transcripts(
    loop: Any,
    artifact_dir: Path,
    transcript_path: Path,
    elapsed: float,
) -> None:
    """Write transcript + usage + runtime exports when --save-artifacts is set."""
    working_messages = getattr(loop, "_working_messages", [])
    usage_events = loop.get_usage_events()
    openclaw_records = convert_working_messages_to_openclaw(
        working_messages, usage_events
    )
    write_openclaw_jsonl(openclaw_records, transcript_path)
    raw_transcript_path = artifact_dir / "transcript.raw.jsonl"
    write_transcript(working_messages, raw_transcript_path)
    usage_path = artifact_dir / "usage.json"
    write_usage_summary(usage_path, usage_events, elapsed)
    _write_runtime_exports(loop, artifact_dir)


def _finalize_run_success(
    agent: Agent,
    result: str,
    elapsed: float,
    timeout: int,
    timeout_event: threading.Event,
    save_artifacts: bool,
    artifact_dir: Path | None,
    transcript_path: Path | None,
    log_path: Path | None,
    workspace: Path,
    trace: bool,
    task_tree: bool,
) -> int:
    """Handle a completed run: timeout check, artifacts, summary. Returns exit code."""
    if timeout_event.is_set():
        if log_path:
            write_log_entry(
                log_path, "timeout", "warning", {"timeout": timeout, "elapsed": elapsed}
            )
        print(f"Agent timed out after {timeout}s", file=sys.stderr, flush=True)
        return 124

    if log_path:
        write_log_entry(
            log_path,
            "complete",
            "info",
            {
                "elapsed": elapsed,
                "result_length": len(result) if result else 0,
            },
        )

    loop = agent.loop
    if (
        save_artifacts
        and artifact_dir is not None
        and transcript_path is not None
        and log_path is not None
    ):
        _write_run_transcripts(loop, artifact_dir, transcript_path, elapsed)

    print(f"Agent completed in {elapsed:.1f}s", file=sys.stderr, flush=True)
    print_node_traversal(loop)
    if trace:
        from tinycua.cli.live_stream import print_final_task_tree

        print_final_task_tree(loop)
    if result and not trace:
        print(result, flush=True)
    print_live_summary(
        loop, workspace, artifact_dir, result, trace=trace, task_tree=task_tree
    )
    return 0


def _handle_run_exception(
    exc: BaseException,
    elapsed: float,
    timeout: int,
    log_path: Path | None,
) -> int:
    """Handle a run exception (CancelledError→124, other→1). Returns exit code."""
    if isinstance(exc, asyncio.CancelledError):
        if log_path:
            write_log_entry(
                log_path, "timeout", "warning", {"timeout": timeout, "elapsed": elapsed}
            )
        return 124
    if log_path:
        write_log_entry(
            log_path, "error", "error", {"error": str(exc), "elapsed": elapsed}
        )
    print(f"Agent error: {exc}", file=sys.stderr, flush=True)
    return 1


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
    replan_threshold: int | None = None,
    max_context: int | None = None,
    recovery_strategy: str = "standard",
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
        replan_threshold: Consecutive reviewer rejections before auto-replan.
            Defaults to 5 if not specified.
        max_context: Override for the model's max context window (tokens) used
            for compaction threshold calculation (FR-084). When None, the
            runtime probes the server via GET /v1/models; falls back to the
            SDK default (128000) when the probe fails or the field is absent.
        recovery_strategy: Retry strategy for missing state-tool validation
            failures (FR-087..FR-093). "standard" (default) uses the existing
            tool-exposed retry + 15/10/3 recovery. "markdown_synthesis" adds
            one no-tools markdown continuation before standard recovery.

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

    ws_result = _prepare_run_workspace(dir, save_artifacts, prompt, timeout)
    if isinstance(ws_result, int):
        return ws_result
    workspace, artifact_dir, log_path, transcript_path = ws_result

    config = _load_run_config(provider_url, api_key, model, provider_type, log_path)
    if isinstance(config, int):
        return config

    # FR-084: resolve the real max_context. Priority: explicit --max-context
    # flag > server probe (GET /v1/models) > SDK default (128000).
    resolved_max_context = _resolve_max_context(config, max_context, log_path)
    if resolved_max_context is not None:
        config["max_context"] = resolved_max_context

    agent = _build_run_agent(
        config,
        workspace,
        artifact_dir,
        worker_effort,
        no_tool_audit,
        allow_open_question,
        replan_threshold,
        log_path,
        recovery_strategy=recovery_strategy,
    )
    if isinstance(agent, int):
        return agent

    # FR-075: enable task tree snapshot logging when --trace is set.
    if trace:
        loop = agent.loop
        if hasattr(loop, "root_session") and loop.root_session is not None:
            loop.root_session.task_store._enable_trace = True

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
        return _finalize_run_success(
            agent,
            result,
            elapsed,
            timeout,
            timeout_event,
            save_artifacts,
            artifact_dir,
            transcript_path,
            log_path,
            workspace,
            trace,
            task_tree,
        )
    except Exception as e:
        elapsed = time.monotonic() - start_time
        return _handle_run_exception(e, elapsed, timeout, log_path)
    except asyncio.CancelledError as e:
        elapsed = time.monotonic() - start_time
        return _handle_run_exception(e, elapsed, timeout, log_path)
    finally:
        timer.cancel()


def _write_runtime_exports(loop: Any, output_dir: Path) -> None:
    """Write trace, state, task tree, and final-response event artifacts."""
    state_snapshot = _safe_loop_call(loop, "get_state_snapshot", default={})
    exports = {
        "execution_trace.json": _safe_loop_call(
            loop, "get_execution_trace", default=[]
        ),
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
