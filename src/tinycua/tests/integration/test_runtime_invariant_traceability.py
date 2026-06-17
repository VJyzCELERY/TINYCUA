"""One-shot script traceability: run_agent.py emits auditable runtime artifacts.

Spec: ./specs/tinycua-runtime-invariants/spec.md:224, 270
Source: src/tinycua/docs/design/loops/tinycua_loop.md:21-40, 62-65,
        src/tinycua/docs/design/loops/node_queue.md:85-101

The one-shot script must run a TinyCUA agent from one prompt and emit enough
trace data to inspect node order, tool calls, final response, task tree,
workspace files, and artifact locations. This test drives the script with a
scripted LLM (no network) so the trace contract is proven deterministically.
"""

from __future__ import annotations

import io
import re
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent

# Reuse the proven scripted-LLM pattern from the route matrix tests.
from tests.integration.test_runtime_invariant_route_matrix import _RouteMatrixScript

_PROJECT_DIR = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _PROJECT_DIR / "scripts" / "run_agent.py"


def _load_script_module() -> Any:
    """Load run_agent.py without executing its main guard."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("run_agent_traceability", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_REQUIRED_SECTIONS = (
    "=== TRACE ===",
    "=== FINAL RESPONSE ===",
    "=== TASK TREE ===",
    "=== WORKSPACE FILES ===",
    "=== ARTIFACTS ===",
)


@pytest.mark.asyncio
async def test_run_agent_emits_trace_response_task_tree_workspace_artifacts(
    tmp_path: Path,
) -> None:
    """Spec: ./spec.md:224, ./spec.md:270.

    Source: tinycua_loop.md:21-40, tinycua_loop.md:62-65, node_queue.md:85-101.
    The one-shot script prints all five auditable trace sections.
    """
    module = _load_script_module()
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    args = module.parse_args(
        ["--dir", str(workspace), "--prompt", "hello", "--stream"]
    )

    # Build the agent the same way run() does, then inject a scripted LLM so
    # the trace contract is proven without a network dependency.
    from tinycua.cli.config import build_language_model, load_config

    config = load_config("http://localhost:1234/v1", "test-key", "test-model")
    agent = create_tinycua_agent(
        session_config=SessionConfig(workspace_dir=workspace),
        llm_model=build_language_model(config),
        enable_native_tools=True,
    )
    agent._call_llm = _RouteMatrixScript(route="passthrough")  # type: ignore[method-assign]

    # Drive the script's own rendering path by monkeypatching create_tinycua_agent
    # to return our scripted agent. This keeps the test hermetic while exercising
    # the real _print_summary / _write_artifacts code in the script.
    import tinycua.factory as factory_mod

    original_factory = factory_mod.create_tinycua_agent

    def _patched(**kwargs: Any) -> Any:  # noqa: ANN202
        # Reuse the agent we already built with the scripted LLM.
        return agent

    factory_mod.create_tinycua_agent = _patched  # type: ignore[assignment]
    try:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            return_code = await module.run(args)
    finally:
        factory_mod.create_tinycua_agent = original_factory  # type: ignore[assignment]

    assert return_code == 0
    output = buffer.getvalue()
    for section in _REQUIRED_SECTIONS:
        assert section in output, f"missing trace section {section!r} in script output"


@pytest.mark.asyncio
async def test_run_agent_stream_exposes_node_order_for_audit(tmp_path: Path) -> None:
    """Spec: ./spec.md:224, ./spec.md:270.

    Source: tinycua_loop.md:21-40, tinycua_loop.md:62-65.
    Stream mode must expose node/tool lifecycle events enough to audit route
    order. We assert the trace section lists at least the entry and terminal
    nodes in order.
    """
    module = _load_script_module()
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    args = module.parse_args(
        ["--dir", str(workspace), "--prompt", "hello", "--stream"]
    )

    from tinycua.cli.config import build_language_model, load_config
    import tinycua.factory as factory_mod

    config = load_config("http://localhost:1234/v1", "test-key", "test-model")
    agent = create_tinycua_agent(
        session_config=SessionConfig(workspace_dir=workspace),
        llm_model=build_language_model(config),
        enable_native_tools=True,
    )
    agent._call_llm = _RouteMatrixScript(route="passthrough")  # type: ignore[method-assign]

    original_factory = factory_mod.create_tinycua_agent

    def _patched(**kwargs: Any) -> Any:  # noqa: ANN202
        return agent

    factory_mod.create_tinycua_agent = _patched  # type: ignore[assignment]
    try:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            await module.run(args)
    finally:
        factory_mod.create_tinycua_agent = original_factory  # type: ignore[assignment]

    output = buffer.getvalue()
    # The === TRACE === section lists [index] node_id (node_type) ... lines.
    trace_match = re.search(
        r"=== TRACE ===\n(?P<body>.*?)\n=== TASK TREE ===",
        output,
        re.DOTALL,
    )
    assert trace_match is not None, "could not isolate TRACE section in output"
    trace_lines = [
        line
        for line in trace_match.group("body").splitlines()
        if re.match(r"\[\d+\]\s", line)
    ]
    assert trace_lines, "trace section listed no node entries"
    # First node is query_analyst; last listed node is response.
    first = trace_lines[0]
    last = trace_lines[-1]
    assert "query_analyst" in first, f"trace does not start at query_analyst: {first}"
    assert "response" in last, f"trace does not end at response: {last}"


def test_run_agent_script_help_documents_required_flags() -> None:
    """Spec: ./spec.md:224.

    Source: tinycua_loop.md:62-65.
    The script's --help output must advertise --prompt, --dir, and --stream so
    a human can audit a one-shot run from the command line.
    """
    import subprocess

    result = subprocess.run(
        ["uv", "run", "python", str(_SCRIPT_PATH), "--help"],
        cwd=_PROJECT_DIR,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0
    help_text = result.stdout
    for flag in ("--prompt", "--dir", "--stream"):
        assert flag in help_text, f"--help missing {flag}: {help_text!r}"


def test_run_agent_loads_worker_effort_from_env_before_parsing_args(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The script loads .env before argparse so env-derived defaults resolve.

    Spec: ./spec.md:224. Regression guard: ``TINYCUA_WORKER_EFFORT`` set in the
    project ``.env`` must reach ``SessionConfig.worker_effort``. Previously
    ``parse_args`` froze the default to ``"none"`` before ``.env`` was loaded,
    silently ignoring the user's configured effort.
    """
    import os

    module = _load_script_module()
    env_file = tmp_path / ".env"
    env_file.write_text("TINYCUA_WORKER_EFFORT=high\n", encoding="utf-8")

    # Simulate the script's startup: shell env has no value, .env provides it.
    monkeypatch.delenv("TINYCUA_WORKER_EFFORT", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "PROJECT_DIR", tmp_path, raising=False)

    module._load_default_env()
    args = module.parse_args(
        ["--dir", str(tmp_path / "ws"), "--prompt", "hello"]
    )

    assert os.environ.get("TINYCUA_WORKER_EFFORT") == "high"
    assert args.worker_effort == "high", (
        "parse_args did not pick up TINYCUA_WORKER_EFFORT from .env; the env "
        "was loaded after argparse froze the default."
    )


@pytest.mark.asyncio
async def test_run_agent_stream_shows_deterministic_effort_node(
    tmp_path: Path,
) -> None:
    """Spec: ./spec.md:224, ./spec.md:270.

    Source: tinycua_loop.md:62-65, analysis_effort.md:30-44.
    Deterministic orchestration nodes (AnalysisEffort) emit ``node.completed``
    events whose content must be visible in ``--stream`` so the user can audit
    that effort passes actually ran. We feed the printer synthetic events
    matching the real event shapes (captured from a hermetic run) so the test is
    deterministic and network-free.
    """
    import io
    from contextlib import redirect_stdout

    module = _load_script_module()
    printer = module._LiveStreamPrinter()
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
    # The AnalysisEffort deterministic node content must surface in the stream
    # so the user can see effort passes were scheduled.
    assert "analysis_effort" in output, (
        "deterministic analysis_effort node did not appear in stream output; "
        f"the printer must render node.completed events for deterministic nodes. "
        f"Stream output:\n{output}"
    )
    assert "Scheduled analysis effort pass 1 of 2." in output, (
        f"analysis_effort node content not rendered in stream:\n{output}"
    )
    assert "Analysis effort complete after 2 pass(es)." in output, (
        f"analysis_effort completion content not rendered in stream:\n{output}"
    )
