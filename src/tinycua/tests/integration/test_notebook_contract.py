"""Notebook acceptance-demo contract tests."""

from __future__ import annotations

import json
from pathlib import Path


def test_notebook_displays_runtime_state_contract() -> None:
    """Notebook source exposes task tree, tool results, and state snapshot."""
    notebook_path = Path("notebooks/tinycua_agent_trace_demo.ipynb")
    notebook = json.loads(notebook_path.read_text())
    source = "\n".join(
        "".join(cell.get("source", [])) for cell in notebook.get("cells", [])
    )

    assert "get_state_snapshot" in source
    assert "task_tree" in source
    assert "tool_results" in source
    assert "workspace_dir" in source
    assert "artifact_dir" in source
