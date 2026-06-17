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
