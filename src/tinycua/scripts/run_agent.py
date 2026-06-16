"""Run TinyCUA from a simple script entrypoint.

Usage:
    uv run python ./scripts/run_agent.py --stream --dir ./tmp/demo --prompt "Say hi"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from tinycua.cli.config import build_language_model
from tinycua.cli.config import load_config
from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent

logger = logging.getLogger(__name__)
PROJECT_DIR = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse script arguments."""
    parser = argparse.ArgumentParser(
        description="Run a TinyCUA agent prompt with local artifacts and trace output.",
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="Natural language prompt to run.",
    )
    parser.add_argument(
        "--dir",
        required=True,
        type=Path,
        help="Workspace directory where generated files are written.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Trace/artifact directory. Defaults to <dir>/.tinycua-artifacts.",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream runtime events, tool activity, and final response deltas.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help=(
            "Environment file to load before creating the agent. By default, "
            "loads .env from the current directory or project directory."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override TINYCUA_BASE_URL.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Override TINYCUA_API_KEY.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override TINYCUA_MODEL.",
    )
    parser.add_argument(
        "--worker-effort",
        choices=["none", "low", "medium", "high"],
        default=os.environ.get("TINYCUA_WORKER_EFFORT", "medium"),
        help="Analysis effort pass count; default: env TINYCUA_WORKER_EFFORT or medium.",
    )
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> int:
    """Run the configured TinyCUA session."""
    _load_env(args.env_file)

    workspace_dir = args.dir.expanduser().resolve()
    artifact_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir is not None
        else workspace_dir / ".tinycua-artifacts"
    )
    workspace_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    try:
        config = load_config(args.base_url, args.api_key, args.model)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr, flush=True)
        return 1

    agent = create_tinycua_agent(
        session_config=SessionConfig(
            workspace_dir=workspace_dir,
            artifact_dir=artifact_dir,
            worker_effort=args.worker_effort,
        ),
        llm_model=build_language_model(config),
    )

    if args.stream:
        result = await _run_streaming(agent, args.prompt)
    else:
        result = await agent.run(args.prompt)
        print(result, flush=True)

    _write_artifacts(agent.loop, artifact_dir)
    _print_summary(agent.loop, workspace_dir, artifact_dir, result)
    return 0


def _load_env(env_file: Path) -> None:
    """Load environment variables without overriding shell-provided values."""
    if env_file.is_absolute() or env_file != Path(".env"):
        if env_file.exists():
            load_dotenv(env_file, override=False)
        return

    candidates = [Path.cwd() / ".env", PROJECT_DIR / ".env"]
    loaded: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in loaded or not resolved.exists():
            continue
        load_dotenv(resolved, override=False)
        loaded.add(resolved)


async def _run_streaming(agent: Any, prompt: str) -> str:
    """Run an agent stream and render node text/tool activity live."""
    stream = await agent.run(prompt, stream=True)
    final_chunks: list[str] = []
    seen_transcript_events = 0
    printer = _LiveStreamPrinter()
    print("=== LIVE STREAM ===", flush=True)
    async for event in stream:
        final_delta = printer.handle_event(event)
        if final_delta:
            final_chunks.append(final_delta)
        seen_transcript_events = _print_new_transcript_events(
            agent.loop,
            seen_transcript_events,
        )
    trailing_text = printer.flush()
    if trailing_text:
        final_chunks.append(trailing_text)
    seen_transcript_events = _print_new_transcript_events(
        agent.loop,
        seen_transcript_events,
    )
    if final_chunks and not final_chunks[-1].endswith("\n"):
        print(flush=True)
    return "".join(final_chunks)


def _print_stream_event(
    event: dict[str, Any],
    printer: "_LiveStreamPrinter | None" = None,
) -> str:
    """Test helper: render one stream event with a persistent printer."""
    renderer = printer or _LiveStreamPrinter()
    return renderer.handle_event(event)


class _LiveStreamPrinter:
    """Render stream events as node reasoning/output text plus tool markers."""

    def __init__(self) -> None:
        self._section: tuple[str, str] | None = None
        self._tool_json = _ToolProtocolBuffer()

    def handle_event(self, event: dict[str, Any]) -> str:
        """Print one event and return final output text, if the event contains any."""
        event_type = str(event.get("type", ""))
        node_id = str(event.get("node_id") or event.get("node") or "unknown")

        if event_type == "response.reasoning.delta":
            self._print_text(node_id, "reasoning", _event_delta_text(event))
            return ""

        if event_type == "response.output_text.delta":
            return self._handle_output_delta(node_id, str(event.get("delta", "")))

        if event_type in {"response.tool_call", "tool_call.ready"}:
            self._print_tool_call(node_id, _tool_name_from_event(event))
            return ""

        if event_type == "node.error":
            self._print_marker(node_id, "errors", "[node-error]")
            return ""

        if event_type == "response.usage":
            self._print_marker(
                node_id,
                "usage",
                f"[usage] {_format_usage(event.get('usage') or {})}",
            )
            return ""

        return ""

    def flush(self) -> str:
        """Flush pending output text that was not a JSON tool protocol payload."""
        text = self._tool_json.flush_text()
        if text:
            node_id = self._tool_json.last_node_id or "unknown"
            self._print_text(node_id, "output", text)
        return text

    def _handle_output_delta(self, node_id: str, delta: str) -> str:
        if not delta:
            return ""
        result = self._tool_json.push(node_id, delta)
        if result.tool_name:
            self._print_tool_call(node_id, result.tool_name)
            return ""
        if result.text:
            self._print_text(node_id, "output", result.text)
            return result.text
        return ""

    def _print_text(self, node_id: str, section: str, text: str) -> None:
        if not text:
            return
        self._print_header(node_id, section)
        print(text, end="", flush=True)

    def _print_tool_call(self, node_id: str, tool_name: str) -> None:
        self._print_marker(node_id, "tools", f"[tool-call] {tool_name}")

    def _print_marker(self, node_id: str, section: str, marker: str) -> None:
        self._print_header(node_id, section)
        print(marker, flush=True)

    def _print_header(self, node_id: str, section: str) -> None:
        key = (node_id, section)
        if self._section == key:
            return
        self._section = key
        print(f"\n\n--- {node_id} {section} ---", flush=True)


class _ToolProtocolResult:
    """Classified output-text delta content."""

    def __init__(self, text: str = "", tool_name: str = "") -> None:
        self.text = text
        self.tool_name = tool_name


class _ToolProtocolBuffer:
    """Hide streamed JSON tool protocol and release normal output text."""

    def __init__(self) -> None:
        self._pending = ""
        self.last_node_id: str | None = None

    def push(self, node_id: str, delta: str) -> _ToolProtocolResult:
        """Classify output text as visible text or JSON tool protocol."""
        if self._pending and self.last_node_id != node_id:
            text = self.flush_text()
            self.last_node_id = node_id
            self._pending = delta
            return _ToolProtocolResult(text=text)

        self.last_node_id = node_id
        candidate = self._pending + delta
        if not candidate.lstrip().startswith("{"):
            self._pending = ""
            return _ToolProtocolResult(text=candidate)

        tool_name = _tool_name_from_protocol_text_if_complete(candidate)
        if tool_name:
            self._pending = ""
            return _ToolProtocolResult(tool_name=tool_name)

        if _could_be_tool_protocol_prefix(candidate):
            self._pending = candidate
            return _ToolProtocolResult()

        self._pending = ""
        return _ToolProtocolResult(text=candidate)

    def flush_text(self) -> str:
        """Return pending visible text, suppressing complete tool protocol JSON."""
        text = self._pending
        self._pending = ""
        if _tool_name_from_protocol_text_if_complete(text):
            return ""
        return text


def _print_new_transcript_events(loop: Any, seen_count: int) -> int:
    """Print newly recorded tool/node transcript events during streaming."""
    events = _safe_loop_call(loop, "get_transcript_events", default=[])
    if not isinstance(events, list):
        return seen_count
    for event in events[seen_count:]:
        event_type = event.get("type")
        if event_type == "transcript.tool_result":
            label = event.get("node_label") or event.get("node_id") or "node"
            tool_name = event.get("tool_name") or "tool"
            print(
                f"\n[tool-result] node={label} tool={tool_name} "
                f"{_summarize_tool_result(str(event.get('content', '')))}",
                flush=True,
            )
    return len(events)


def _truncate(value: str, limit: int) -> str:
    """Truncate long event payloads for live readability."""
    if len(value) <= limit:
        return value
    return f"{value[:limit]}…[truncated]"


def _format_usage(usage: Any) -> str:
    """Format token usage without dumping provider event JSON."""
    if not isinstance(usage, dict):
        return str(usage)
    parts = []
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        if key in usage:
            parts.append(f"{key}={usage[key]}")
    return " ".join(parts) if parts else "received"


def _summarize_tool_result(content: str) -> str:
    """Summarize a tool result without dumping its JSON body."""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return _truncate(content, 500)
    if not isinstance(payload, dict):
        return _truncate(content, 500)
    output = payload.get("output")
    status = ""
    if isinstance(output, dict):
        success = output.get("success")
        if success is not None:
            status = f"success={success}"
        if output.get("path"):
            return f"{status} path={output['path']}".strip()
        if output.get("task_id"):
            task_bits = [status, f"task_id={output['task_id']}"]
            if output.get("status"):
                task_bits.append(f"status={output['status']}")
            if output.get("decision"):
                task_bits.append(f"decision={output['decision']}")
            return " ".join(bit for bit in task_bits if bit)
        if output.get("exit_code") is not None:
            return (
                f"exit_code={output.get('exit_code')} "
                f"timed_out={output.get('timed_out')}"
            )
    if isinstance(output, list):
        return f"items={len(output)}"
    if payload.get("error"):
        return f"error={payload['error']}"
    return "completed"


def _event_delta_text(event: dict[str, Any]) -> str:
    """Extract visible text from provider delta event variants."""
    for key in ("delta", "text", "content"):
        value = event.get(key)
        if isinstance(value, str):
            return value
    delta = event.get("delta")
    if isinstance(delta, dict):
        for key in ("text", "content", "value"):
            value = delta.get(key)
            if isinstance(value, str):
                return value
    return ""


def _tool_name_from_event(event: dict[str, Any]) -> str:
    """Extract a concise tool name from provider tool-call event variants."""
    name = event.get("name")
    if isinstance(name, str) and name:
        return name
    function = event.get("function")
    if isinstance(function, dict):
        function_name = function.get("name")
        if isinstance(function_name, str) and function_name:
            return function_name
    tool_call = event.get("tool_call")
    if isinstance(tool_call, dict):
        tool_name = tool_call.get("name")
        if isinstance(tool_name, str) and tool_name:
            return tool_name
    return "unknown"


def _tool_name_from_protocol_text_if_complete(text: str) -> str | None:
    """Return tool name when text is a complete JSON tool protocol payload."""
    stripped = text.strip()
    if not stripped.startswith("{") or "tool_calls" not in stripped:
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("tool_calls"), list):
        return None
    return _tool_name_from_protocol_payload(payload)


def _tool_name_from_protocol_payload(payload: dict[str, Any]) -> str:
    """Extract the first tool name from parsed protocol payload."""
    calls = payload.get("tool_calls")
    if not isinstance(calls, list) or not calls:
        return "json_protocol"
    first = calls[0]
    if not isinstance(first, dict):
        return "json_protocol"
    name = first.get("name")
    if isinstance(name, str) and name:
        return name
    function = first.get("function")
    if isinstance(function, dict) and isinstance(function.get("name"), str):
        return function["name"]
    return "json_protocol"


def _could_be_tool_protocol_prefix(text: str) -> bool:
    """Return whether buffered text may still become a tool protocol payload."""
    stripped = text.lstrip()
    if not stripped.startswith("{"):
        return False
    if len(stripped) > 80_000:
        return False
    compact = "".join(stripped.split())
    return any(
        target.startswith(compact[: len(target)]) or compact.startswith(target[: len(compact)])
        for target in ('{"tool_calls"', '{"tool_calls":', '{"tool_calls":[')
    ) or "tool_calls" in stripped


def _write_artifacts(loop: Any, artifact_dir: Path) -> None:
    """Write JSON/text runtime artifacts for debugging."""
    state_snapshot = _safe_loop_call(loop, "get_state_snapshot", default={})
    artifacts = {
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
    for filename, payload in artifacts.items():
        (artifact_dir / filename).write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )
    if isinstance(state_snapshot, dict):
        (artifact_dir / "task_tree.txt").write_text(
            str(state_snapshot.get("task_tree_text", "No tasks.")),
            encoding="utf-8",
        )
    transcript_text = _safe_loop_call(
        loop,
        "get_transcript_text",
        default="",
        include_node_calls=True,
    )
    (artifact_dir / "transcript.txt").write_text(str(transcript_text), encoding="utf-8")


def _print_summary(loop: Any, workspace_dir: Path, artifact_dir: Path, result: str) -> None:
    """Print a concise notebook replacement summary without raw event JSON."""
    state_snapshot = _safe_loop_call(loop, "get_state_snapshot", default={})
    trace = _safe_loop_call(loop, "get_execution_trace", default=[])
    print("\n=== SESSION DIRECTORIES ===", flush=True)
    print(f"workspace_dir={workspace_dir}", flush=True)
    print(f"artifact_dir={artifact_dir}", flush=True)
    print("\n=== FINAL RESPONSE ===", flush=True)
    print(result or "<empty>", flush=True)
    print("\n=== TRACE ===", flush=True)
    for index, step in enumerate(trace, start=1):
        node_id = step.get("node_id") if isinstance(step, dict) else "unknown"
        node_type = step.get("node_type") if isinstance(step, dict) else "unknown"
        route = step.get("route_label") if isinstance(step, dict) else None
        terminal = step.get("is_terminal") if isinstance(step, dict) else None
        print(
            f"[{index}] {node_id} ({node_type}) route={route} terminal={terminal}",
            flush=True,
        )
        if isinstance(step, dict) and step.get("validation_errors"):
            print(
                f"    validation_errors={len(step['validation_errors'])}",
                flush=True,
            )
        print(flush=True)
    print("=== TASK TREE ===", flush=True)
    if isinstance(state_snapshot, dict):
        print(state_snapshot.get("task_tree_text", "No tasks."), flush=True)
    print("\n=== WORKSPACE FILES ===", flush=True)
    for path in _visible_workspace_files(workspace_dir):
        print(f"- {path}", flush=True)
    print("\n=== ARTIFACTS ===", flush=True)
    print(f"Full trace/transcript JSON saved under: {artifact_dir}", flush=True)


def _visible_workspace_files(workspace_dir: Path) -> list[Path]:
    """Return generated files excluding virtualenv/cache noise."""
    ignored_parts = {".tinycua-artifacts", ".venv", "venv", "__pycache__"}
    files = []
    for path in workspace_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(workspace_dir)
        if ignored_parts.intersection(relative.parts):
            continue
        files.append(relative)
    return sorted(files)


def _safe_loop_call(loop: Any, method_name: str, *, default: Any, **kwargs: Any) -> Any:
    """Call optional loop export methods without hiding run completion."""
    method = getattr(loop, method_name, None)
    if not callable(method):
        return default
    try:
        return method(**kwargs)
    except Exception:  # noqa: BLE001 - diagnostics must not fail completed runs.
        logger.debug("runtime_export_failed method=%s", method_name, exc_info=True)
        return default


def main(argv: list[str] | None = None) -> int:
    """Script entrypoint."""
    return asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
