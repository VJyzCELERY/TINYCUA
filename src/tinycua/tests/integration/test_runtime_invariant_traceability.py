"""CLI traceability: ``tinycua run`` emits auditable runtime artifacts.

Spec: ./specs/tinycua-runtime-invariants/spec.md:224, 270
Source: src/tinycua/docs/design/loops/tinycua_loop.md:21-40, 62-65,
        src/tinycua/docs/design/loops/node_queue.md:85-101

The ``tinycua run`` CLI must run a TinyCUA agent from one prompt and emit
enough trace data to inspect node order, tool calls, final response, task
tree, workspace files, and artifact locations. These tests drive the CLI
stream printer and arg parser (no network) so the trace contract is proven
deterministically.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

_PROJECT_DIR = Path(__file__).resolve().parents[2]


def _load_cli_run_module() -> Any:
    """Import the CLI run module."""
    from tinycua.cli import run as run_module

    return run_module


def _load_stream_printer() -> Any:
    """Import the CLI live-stream printer class."""
    from tinycua.cli.live_stream import LiveStreamPrinter

    return LiveStreamPrinter


_REQUIRED_SECTIONS = (
    "=== TRACE ===",
    "=== FINAL RESPONSE ===",
    "=== TASK TREE ===",
    "=== WORKSPACE FILES ===",
    "=== ARTIFACTS ===",
)


def test_cli_run_arg_parser_supports_core_flags(tmp_path: Path) -> None:
    """The CLI ``run`` parser accepts --dir, --prompt, --worker-effort."""
    module = _load_cli_run_module()

    args = module.parse_args(
        ["--dir", str(tmp_path), "--prompt", "hello world", "--worker-effort", "high"]
    )

    assert args.prompt == "hello world"
    assert args.dir == tmp_path
    assert args.worker_effort == "high"
    # --stream is gone; streaming is the default behavior.
    assert not hasattr(args, "stream")


def test_cli_run_dir_defaults_to_cwd() -> None:
    """The default workdir is the current working directory."""
    module = _load_cli_run_module()

    args = module.parse_args(["hello"])

    assert args.dir == Path.cwd()


def test_cli_run_provider_type_defaults_to_chat_completions() -> None:
    """--provider-type defaults to openai-chat-completions."""
    module = _load_cli_run_module()

    args = module.parse_args(["hello"])

    assert args.provider_type == "openai-chat-completions"


def test_cli_run_worker_effort_from_env_takes_priority(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """TINYCUA_WORKER_EFFORT in env overrides the medium default.

    The CLI loads .env before argparse so env-derived defaults resolve.
    """

    module = _load_cli_run_module()
    monkeypatch.setenv("TINYCUA_WORKER_EFFORT", "high")

    args = module.parse_args(["--dir", str(tmp_path), "hello"])

    assert args.worker_effort == "high"


def test_cli_run_env_file_flag_specifies_env_path(tmp_path: Path) -> None:
    """--env specifies an env file path to load before resolving config."""
    module = _load_cli_run_module()

    args = module.parse_args(
        ["--dir", str(tmp_path), "--env", str(tmp_path / ".env"), "hello"]
    )

    assert args.env_file == tmp_path / ".env"


def test_cli_run_help_documents_core_flags() -> None:
    """The ``tinycua run`` parser help advertises --dir, --provider-type, etc.

    We invoke the parser directly (rather than via subprocess) because
    ``main.py`` registers the subparser before delegating to ``parse_args``;
    the real flag help lives in ``parse_args``.
    """
    import contextlib

    module = _load_cli_run_module()
    buffer = io.StringIO()
    with contextlib.suppress(SystemExit):
        with redirect_stdout(buffer):
            module.parse_args(["--help"])
    help_text = buffer.getvalue()
    for flag in ("--dir", "--provider-url", "--provider-type", "--worker-effort", "--env"):
        assert flag in help_text, f"run --help missing {flag}: {help_text!r}"


@pytest.mark.asyncio
async def test_cli_run_stream_shows_deterministic_effort_node() -> None:
    """Spec: ./spec.md:224, ./spec.md:270.

    Source: tinycua_loop.md:62-65, analysis_effort.md:30-44.
    Deterministic orchestration nodes (AnalysisEffort) emit ``node.completed``
    events whose content must be visible in the stream so the user can audit
    that effort passes actually ran. We feed the CLI printer synthetic events
    matching the real event shapes so the test is deterministic and network-free.
    """
    LiveStreamPrinter = _load_stream_printer()
    printer = LiveStreamPrinter()
    buffer = io.StringIO()

    # Real event shapes captured from a hermetic worker-effort run:
    # analysis_effort emits node.started then node.completed with the scheduled
    # pass content. query_analyst is shown first for context.
    events = [
        {"type": "node.started", "node_id": "query_analyst", "node_type": "ProcessNode"},
        {"type": "response.output_text.delta", "node_id": "query_analyst", "delta": ""},
        {"type": "node.started", "node_id": "analysis_effort", "node_type": "ProcessNode"},
        {
            "type": "node.completed",
            "node_id": "analysis_effort",
            "node_type": "ProcessNode",
            "content": "Scheduled analysis effort pass 1 of 2.",
            "finish_reason": "completed",
        },
        {"type": "node.started", "node_id": "task_assessor", "node_type": "ProcessNode"},
        {
            "type": "node.completed",
            "node_id": "analysis_effort",
            "node_type": "ProcessNode",
            "content": "Analysis effort complete after 2 pass(es).",
            "finish_reason": "completed",
        },
    ]

    with redirect_stdout(buffer):
        for event in events:
            printer.handle_event(event)
        printer.flush()

    output = buffer.getvalue()
    # The AnalysisEffort deterministic node content must surface in the stream.
    assert "analysis_effort" in output, (
        "deterministic analysis_effort node did not appear in stream output; "
        f"the printer must render node.completed events. Stream:\n{output}"
    )
    assert "Scheduled analysis effort pass 1 of 2." in output, (
        f"analysis_effort node content not rendered in stream:\n{output}"
    )
    assert "Analysis effort complete after 2 pass(es)." in output, (
        f"analysis_effort completion content not rendered in stream:\n{output}"
    )


def test_cli_run_stream_uses_node_prefix_format() -> None:
    """Spec: ./spec.md:224.

    Source: tinycua_loop.md:62-65.
    The stream renders events as ``[node_id] {content}`` lines (node prefix
    beside each event), not ``--- node_id section ---`` block headers. No raw
    JSON event payloads should appear.
    """
    LiveStreamPrinter = _load_stream_printer()
    printer = LiveStreamPrinter()
    buffer = io.StringIO()

    events = [
        {"type": "node.started", "node_id": "query_analyst", "node_type": "ProcessNode"},
        {
            "type": "response.output_text.delta",
            "node_id": "query_analyst",
            "delta": "Classify the route.",
        },
        {
            "type": "response.tool_call",
            "node_id": "query_analyst",
            "name": "select_query_route",
        },
        {
            "type": "response.usage",
            "node_id": "query_analyst",
            "usage": {"input_tokens": 598, "output_tokens": 104, "total_tokens": 702},
        },
    ]

    with redirect_stdout(buffer):
        for event in events:
            printer.handle_event(event)
        printer.flush()

    output = buffer.getvalue()
    # No block-header separators.
    assert "--- query_analyst" not in output, (
        f"stream still uses block headers; expected [node_id] prefix format:\n{output}"
    )
    # Node prefix appears beside events.
    assert "[query_analyst]" in output
    # Tool call and usage are formatted human-readably, not raw JSON.
    assert "select_query_route" in output
    assert "input_tokens=598" in output or "598" in output


def test_cli_run_summary_emits_trace_task_tree_workspace_artifacts(
    tmp_path: Path,
) -> None:
    """Spec: ./spec.md:224, ./spec.md:270.

    Source: tinycua_loop.md:21-40, tinycua_loop.md:62-65, node_queue.md:85-101.
    The end-of-run summary prints all five auditable trace sections.
    """
    from unittest.mock import MagicMock

    from tinycua.cli.live_stream import print_summary

    mock_loop = MagicMock()
    mock_loop.get_state_snapshot = MagicMock(
        return_value={
            "task_tree": {},
            "task_tree_text": "No tasks.",
        }
    )
    mock_loop.get_execution_trace = MagicMock(
        return_value=[
            {"node_id": "query_analyst", "node_type": "ProcessNode", "is_terminal": False},
            {"node_id": "response", "node_type": "ProcessNode", "is_terminal": True},
        ]
    )
    mock_loop.get_transcript_text = MagicMock(return_value="")
    mock_loop.get_transcript_events = MagicMock(return_value=[])
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "app.py").write_text("# generated\n", encoding="utf-8")
    artifact_dir = tmp_path / ".tinycua-artifacts"
    artifact_dir.mkdir()

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        print_summary(
            mock_loop, workspace, artifact_dir, "Final response to the user.",
            trace=True,
        )

    output = buffer.getvalue()
    for section in _REQUIRED_SECTIONS:
        assert section in output, f"missing trace section {section!r} in summary:\n{output}"
    assert "Final response to the user." in output
    assert "app.py" in output
