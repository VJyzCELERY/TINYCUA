"""Live notebook execution contract."""

from __future__ import annotations

import os
from pathlib import Path

import dotenv
import pytest


pytestmark = pytest.mark.live_llm


def _require_live_llm() -> None:
    dotenv.load_dotenv(Path(".env.test"), override=False)
    if os.environ.get("TINYCUA_LIVE_LLM") != "1":
        pytest.skip("Set TINYCUA_LIVE_LLM=1 to run live notebook contract")


def test_notebook_contract_live_executes_against_local_llm() -> None:
    """Execute the demo notebook end to end against the configured local LLM."""
    _require_live_llm()
    import nbformat
    from nbclient import NotebookClient

    notebook_path = Path("notebooks/tinycua_agent_trace_demo.ipynb")
    notebook = nbformat.read(notebook_path, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=240,
        kernel_name="python3",
        resources={"metadata": {"path": str(Path.cwd())}},
    )

    client.execute()

    outputs = []
    for cell in notebook.cells:
        for output in cell.get("outputs", []):
            outputs.append(output.get("text", ""))
    rendered = "\n".join(outputs)
    assert "STATE SNAPSHOT" in rendered
    assert "task_tree" in rendered
    assert "TRACE" in rendered
