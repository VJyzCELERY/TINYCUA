"""Live stream rendering and artifact export for TinyCUA run commands."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def print_node_traversal(loop: Any) -> None:
    """Print the linear node execution order to stderr at end of run.

    Extracts ``node_id`` from each entry in the execution trace and prints
    them as a clean list. Consecutive same-node entries collapse to
    ``node_id (×N)``; non-consecutive re-entries stay as separate lines
    (preserves traversal order). Goes to ``sys.stderr`` so it does not
    pollute the ``stdout`` response. Always-on — no flag needed.
    """
    trace_data = safe_loop_call(loop, "get_execution_trace", default=[])
    if not isinstance(trace_data, list) or not trace_data:
        print("=== NODE TRAVERSAL ===\n(no nodes executed)", file=sys.stderr, flush=True)
        return
    ids: list[str] = []
    counts: list[int] = []
    for step in trace_data:
        node_id = step.get("node_id", "unknown") if isinstance(step, dict) else "unknown"
        if ids and ids[-1] == node_id:
            counts[-1] += 1
        else:
            ids.append(node_id)
            counts.append(1)
    print("=== NODE TRAVERSAL ===", file=sys.stderr, flush=True)
    for node_id, count in zip(ids, counts):
        if count > 1:
            print(f"{node_id} (×{count})", file=sys.stderr, flush=True)
        else:
            print(node_id, file=sys.stderr, flush=True)


async def run_streaming(agent: Any, prompt: str) -> str:
    """Run an agent stream and render node text/tool activity live."""
    stream = await agent.run(prompt, stream=True)
    final_chunks: list[str] = []
    seen_transcript_events = 0
    printer = LiveStreamPrinter()
    print("=== LIVE STREAM ===", flush=True)
    async for event in stream:
        final_delta = printer.handle_event(event)
        if final_delta:
            final_chunks.append(final_delta)
        seen_transcript_events = print_new_transcript_events(
            agent.loop,
            seen_transcript_events,
        )
    trailing_text = printer.flush()
    if trailing_text:
        final_chunks.append(trailing_text)
    print_new_transcript_events(agent.loop, seen_transcript_events)
    if final_chunks and not final_chunks[-1].endswith("\n"):
        print(flush=True)
    return "".join(final_chunks)


class LiveStreamPrinter:
    """Render stream events as ``[node_id] {content}`` lines.

    Each event is printed on its own line with the node id as a prefix beside
    the content (not as a ``--- node_id section ---`` block header). Multi-line
    output carries the ``[node_id]`` prefix only on the first line so the
    stream stays readable. Deterministic orchestration nodes
    (``node.started``/``node.completed``) are rendered too so effort passes
    are visible. Tool results and usage are summarized human-readably; no raw
    JSON event payloads are emitted.
    """

    def __init__(self) -> None:
        self._tool_json = ToolProtocolBuffer()
        # Track the node id that currently owns the prefix so continuation
        # lines of a multi-line delta don't repeat the prefix.
        self._current_prefix_node: str | None = None

    def handle_event(self, event: dict[str, Any]) -> str:
        """Print one event and return final output text, if any."""
        event_type = str(event.get("type", ""))
        node_id = str(event.get("node_id") or event.get("node") or "unknown")
        if event_type == "response.reasoning.delta":
            self._print_text(node_id, event_delta_text(event), kind="reasoning")
            return ""
        if event_type == "response.output_text.delta":
            return self._handle_output_delta(node_id, str(event.get("delta", "")))
        if event_type in {"response.tool_call", "tool_call.ready"}:
            self._print_marker(node_id, f"tool_call: {tool_name_from_event(event)}")
            return ""
        if event_type == "node.started":
            self._print_marker(node_id, "start")
            return ""
        if event_type == "node.completed":
            content = str(event.get("content") or "")
            finish_reason = str(event.get("finish_reason") or "")
            if content:
                self._print_text(node_id, content, kind="output")
            elif finish_reason:
                self._print_marker(node_id, f"completed: {finish_reason}")
            return ""
        if event_type == "node.error":
            self._print_marker(node_id, "node-error")
            return ""
        if event_type == "response.usage":
            self._print_marker(node_id, f"usage: {format_usage(event.get('usage') or {})}")
            return ""
        return ""

    def flush(self) -> str:
        """Flush pending output text that was not a JSON tool protocol payload."""
        text = self._tool_json.flush_text()
        if text:
            self._print_text(self._tool_json.last_node_id or "unknown", text, kind="output")
        return text

    def _handle_output_delta(self, node_id: str, delta: str) -> str:
        if not delta:
            return ""
        result = self._tool_json.push(node_id, delta)
        if result.tool_name:
            self._print_marker(node_id, f"tool_call: {result.tool_name}")
            return ""
        if result.text:
            self._print_text(node_id, result.text, kind="output")
            return result.text
        return ""

    def _print_text(self, node_id: str, text: str, *, kind: str = "output") -> None:
        """Print text with a ``[node_id] `` prefix on the first line only.

        Continuation lines print without the prefix so multi-line reasoning or
        output stays readable. A blank line separates different nodes.
        """
        if not text:
            return
        if self._current_prefix_node != node_id:
            # New node — emit a blank separator and start with the prefix.
            if self._current_prefix_node is not None:
                print(flush=True)
            self._current_prefix_node = node_id
            first, _, rest = text.partition("\n")
            print(f"[{node_id}] {first}", flush=True)
            if rest:
                print(rest, end="", flush=True)
            return
        # Continuation of the same node's output — no prefix.
        print(text, end="", flush=True)

    def _print_marker(self, node_id: str, marker: str) -> None:
        """Print a single-line marker with the ``[node_id]`` prefix."""
        if self._current_prefix_node is not None and self._current_prefix_node != node_id:
            print(flush=True)
        self._current_prefix_node = node_id
        print(f"[{node_id}] {marker}", flush=True)


class ToolProtocolResult:
    """Classified output-text delta content."""

    def __init__(self, text: str = "", tool_name: str = "") -> None:
        self.text = text
        self.tool_name = tool_name


class ToolProtocolBuffer:
    """Hide streamed JSON tool protocol and release normal output text."""

    def __init__(self) -> None:
        self._pending = ""
        self.last_node_id: str | None = None

    def push(self, node_id: str, delta: str) -> ToolProtocolResult:
        """Classify output text as visible text or JSON tool protocol."""
        if self._pending and self.last_node_id != node_id:
            text = self.flush_text()
            self.last_node_id = node_id
            self._pending = delta
            return ToolProtocolResult(text=text)
        self.last_node_id = node_id
        candidate = self._pending + delta
        if not candidate.lstrip().startswith("{"):
            self._pending = ""
            return ToolProtocolResult(text=candidate)
        tool_name = tool_name_from_protocol_text_if_complete(candidate)
        if tool_name:
            self._pending = ""
            return ToolProtocolResult(tool_name=tool_name)
        if could_be_tool_protocol_prefix(candidate):
            self._pending = candidate
            return ToolProtocolResult()
        self._pending = ""
        return ToolProtocolResult(text=candidate)

    def flush_text(self) -> str:
        """Return pending visible text, suppressing complete tool protocol JSON."""
        text = self._pending
        self._pending = ""
        if tool_name_from_protocol_text_if_complete(text):
            return ""
        return text


def print_new_transcript_events(loop: Any, seen_count: int) -> int:
    """Print newly recorded tool/node transcript events during streaming."""
    events = safe_loop_call(loop, "get_transcript_events", default=[])
    if not isinstance(events, list):
        return seen_count
    for event in events[seen_count:]:
        if event.get("type") != "transcript.tool_result":
            continue
        label = event.get("node_label") or event.get("node_id") or "node"
        tool_name = event.get("tool_name") or "tool"
        print(
            f"\n[tool-result] node={label} tool={tool_name} "
            f"{summarize_tool_result(str(event.get('content', '')))}",
            flush=True,
        )
    return len(events)


def print_summary(loop: Any, workspace_dir: Path, artifact_dir: Path | None, result: str, *, trace: bool = False, task_tree: bool = False) -> None:
    """Print a concise session summary after a live run.

    Args:
        loop: The TinyCUALoop instance.
        workspace_dir: Workspace directory.
        artifact_dir: Artifact directory (None if --save-artifacts not set).
        result: Final response text.
        trace: If True, print execution trace, task tree, and workspace summary.
        task_tree: If True, print only the flat task tree section. Ignored when
            trace is True (trace already includes the tree).
    """
    if not trace and not task_tree:
        return
    state_snapshot = safe_loop_call(loop, "get_state_snapshot", default={})
    if trace:
        trace_data = safe_loop_call(loop, "get_execution_trace", default=[])
        print("\n=== TRACE ===", flush=True)
        for index, step in enumerate(trace_data, start=1):
            node_id = step.get("node_id") if isinstance(step, dict) else "unknown"
            node_type = step.get("node_type") if isinstance(step, dict) else "unknown"
            route = step.get("route_label") if isinstance(step, dict) else None
            terminal = step.get("is_terminal") if isinstance(step, dict) else None
            print(
                f"[{index}] {node_id} ({node_type}) route={route} terminal={terminal}",
                flush=True,
            )
            if isinstance(step, dict) and step.get("validation_errors"):
                print(f"    validation_errors={len(step['validation_errors'])}", flush=True)
            print(flush=True)
    if trace:
        print("=== FINAL RESPONSE ===", flush=True)
        print(result or "", flush=True)
    if trace or task_tree:
        print("=== TASK TREE ===", flush=True)
        if isinstance(state_snapshot, dict):
            print(state_snapshot.get("task_tree_text", "No tasks."), flush=True)
    if trace:
        print("\n=== WORKSPACE FILES ===", flush=True)
        for path in visible_workspace_files(workspace_dir):
            print(f"- {path}", flush=True)
        if artifact_dir is not None:
            print("\n=== ARTIFACTS ===", flush=True)
            print(f"Full trace/transcript JSON saved under: {artifact_dir}", flush=True)


def truncate(value: str, limit: int) -> str:
    """Truncate long event payloads for live readability."""
    if len(value) <= limit:
        return value
    return f"{value[:limit]}…[truncated]"


def format_usage(usage: Any) -> str:
    """Format token usage without dumping provider event JSON."""
    if not isinstance(usage, dict):
        return str(usage)
    parts = [f"{key}={usage[key]}" for key in ("input_tokens", "output_tokens", "total_tokens") if key in usage]
    return " ".join(parts) if parts else "received"


def summarize_tool_result(content: str) -> str:
    """Summarize a tool result without dumping its JSON body.

    Re-exported from ``node_guidance`` for backward compatibility. The
    canonical implementation lives in the loops layer so the recovery loop
    can import it without a CLI dependency.
    """
    from tinycua.loops.node_guidance import summarize_tool_result as _impl

    return _impl(content)


def event_delta_text(event: dict[str, Any]) -> str:
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


def tool_name_from_event(event: dict[str, Any]) -> str:
    """Extract a concise tool name from provider tool-call event variants."""
    name = event.get("name")
    if isinstance(name, str) and name:
        return name
    function = event.get("function")
    if isinstance(function, dict) and isinstance(function.get("name"), str):
        return function["name"]
    tool_call = event.get("tool_call")
    if isinstance(tool_call, dict) and isinstance(tool_call.get("name"), str):
        return tool_call["name"]
    return "unknown"


def tool_name_from_protocol_text_if_complete(text: str) -> str | None:
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
    return tool_name_from_protocol_payload(payload)


def tool_name_from_protocol_payload(payload: dict[str, Any]) -> str:
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


def could_be_tool_protocol_prefix(text: str) -> bool:
    """Return whether buffered text may still become a tool protocol payload."""
    stripped = text.lstrip()
    if not stripped.startswith("{") or len(stripped) > 80_000:
        return False
    compact = "".join(stripped.split())
    return any(
        target.startswith(compact[: len(target)]) or compact.startswith(target[: len(compact)])
        for target in ('{"tool_calls"', '{"tool_calls":', '{"tool_calls":[')
    ) or "tool_calls" in stripped


def visible_workspace_files(workspace_dir: Path) -> list[Path]:
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


def safe_loop_call(loop: Any, method_name: str, *, default: Any, **kwargs: Any) -> Any:
    """Call optional loop export methods without hiding run completion."""
    method = getattr(loop, method_name, None)
    if not callable(method):
        return default
    try:
        return method(**kwargs)
    except Exception:  # noqa: BLE001 - diagnostics must not fail completed runs.
        logger.debug("runtime_export_failed method=%s", method_name, exc_info=True)
        return default
