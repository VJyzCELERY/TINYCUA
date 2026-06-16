"""Guardrails preventing semantic runtime node stubs."""

from __future__ import annotations

from pathlib import Path

from tinycua.config.node_config import create_node_config
from tinycua.loops import task_nodes


def test_semantic_task_nodes_define_runtime_behavior() -> None:
    """Task nodes must provide concrete prompts or runtime hooks."""
    node_classes = [
        task_nodes.TinyCUATaskAnalyzerNode,
        task_nodes.TinyCUAAnalysisEffortNode,
        task_nodes.TinyCUATaskAssessorNode,
        task_nodes.TinyCUATaskExecutorNode,
        task_nodes.TinyCUAResultReviewerNode,
        task_nodes.TinyCUAResultAggregationNode,
    ]

    for cls in node_classes:
        node = cls(node_id=cls.__name__, config=create_node_config("task_executor"))
        assert node.build_instruction().strip(), cls.__name__
        assert node.build_continuation().strip() or hasattr(
            node,
            "run_deterministic",
        ), cls.__name__
        source = Path(task_nodes.__file__).read_text(encoding="utf-8").lower()
        assert "stub" not in source


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


def test_runtime_modules_do_not_contain_hardcoded_action_fallbacks() -> None:
    """Runtime must not ship scaffold, synthetic-success, or route fallbacks."""
    root = Path(__file__).resolve().parents[2]
    checked_paths = [
        root / "tinycua" / "loops" / "tinycua_loop.py",
        root / "tinycua" / "loops" / "task_nodes.py",
        root / "tinycua" / "loops" / "route_classifier.py",
        root / "tinycua" / "config" / "session_config.py",
    ]
    forbidden = [
        "created workspace scaffold",
        "note_scheduler_app",
        "backend.py",
        "scheduler.py",
        "content_or_fallback",
        "allow_synthetic_terminal_fallback",
        "fallback_label",
        "plan {root.title}",
        "execute {root.title}",
    ]

    for path in checked_paths:
        source = path.read_text(encoding="utf-8").lower()
        for marker in forbidden:
            assert marker not in source, f"{marker!r} found in {path}"
