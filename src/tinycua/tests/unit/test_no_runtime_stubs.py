"""Guardrails preventing semantic runtime node stubs."""

from __future__ import annotations

import inspect
from pathlib import Path

from tinycua.loops import task_nodes


def test_semantic_task_nodes_define_runtime_behavior() -> None:
    """Task nodes must implement concrete runtime hooks, not empty subclasses."""
    node_classes = [
        task_nodes.TinyCUATaskAnalyzerNode,
        task_nodes.TinyCUAAnalysisEffortNode,
        task_nodes.TinyCUATaskAssessorNode,
        task_nodes.TinyCUATaskExecutorNode,
        task_nodes.TinyCUAResultReviewerNode,
        task_nodes.TinyCUAResultAggregationNode,
    ]

    for cls in node_classes:
        assert any(name in cls.__dict__ for name in {"parse_loop_result", "on_complete"}), cls.__name__
        source = inspect.getsource(cls).lower()
        assert "stub" not in source
        assert "pass" not in source


def test_runtime_modules_do_not_expose_remaining_stub_markers() -> None:
    """Final prototype runtime modules must not advertise placeholder behavior."""
    root = Path(__file__).resolve().parents[2]
    checked_paths = [
        root / "tinycua" / "tools" / "enhanced_context_retrieval.py",
        root / "tinycua" / "tools" / "digest_information.py",
        root / "tinycua" / "tools" / "__init__.py",
        root / "tinycua" / "config" / "types.py",
        root / "tinycua" / "config" / "tool_scopes.py",
        root / "tinycua" / "config" / "node_config.py",
        root / "tinycua" / "compaction" / "simple.py",
    ]

    for path in checked_paths:
        source = path.read_text(encoding="utf-8").lower()
        assert "stub" not in source, path
        assert "placeholder" not in source, path
