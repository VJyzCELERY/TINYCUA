"""Unit tests for the always-on node traversal summary to stderr."""

from __future__ import annotations

import sys
from typing import Any

import pytest

from tinycua.cli.live_stream import print_node_traversal


class _MockLoop:
    """Minimal loop stub with get_execution_trace."""

    def __init__(self, trace: list[dict[str, Any]]) -> None:
        self._trace = trace

    def get_execution_trace(self) -> list[dict[str, Any]]:
        return list(self._trace)


class TestPrintNodeTraversalGoesToStderr:
    """The traversal summary goes to stderr, not stdout."""

    def test_output_goes_to_stderr_not_stdout(self, capsys: pytest.CaptureFixture[str]):
        loop = _MockLoop([
            {"node_id": "query_analyst"},
            {"node_id": "digester"},
        ])
        print_node_traversal(loop)
        captured = capsys.readouterr()
        assert "=== NODE TRAVERSAL ===" in captured.err
        assert "query_analyst" in captured.err
        assert "digester" in captured.err
        # stdout should NOT contain the traversal section.
        assert "=== NODE TRAVERSAL ===" not in captured.out


class TestPrintNodeTraversalConsecutiveDedup:
    """Consecutive same-node entries collapse to node_id (×N)."""

    def test_consecutive_duplicates_collapse(self, capsys: pytest.CaptureFixture[str]):
        loop = _MockLoop([
            {"node_id": "task_executor"},
            {"node_id": "task_executor"},
            {"node_id": "task_executor"},
        ])
        print_node_traversal(loop)
        captured = capsys.readouterr()
        assert "task_executor (×3)" in captured.err
        # Should NOT have 3 separate task_executor lines (excluding the ×3 line).
        lines = [l for l in captured.err.strip().split("\n") if l and l != "=== NODE TRAVERSAL ==="]
        assert len(lines) == 1

    def test_two_consecutive_collapse(self, capsys: pytest.CaptureFixture[str]):
        loop = _MockLoop([
            {"node_id": "analysis_effort"},
            {"node_id": "analysis_effort"},
        ])
        print_node_traversal(loop)
        captured = capsys.readouterr()
        assert "analysis_effort (×2)" in captured.err


class TestPrintNodeTraversalNonConsecutiveReentry:
    """Non-consecutive re-entries appear as separate lines (preserves order)."""

    def test_non_consecutive_reentries_are_separate(self, capsys: pytest.CaptureFixture[str]):
        loop = _MockLoop([
            {"node_id": "task_executor"},
            {"node_id": "result_reviewer"},
            {"node_id": "task_executor"},
        ])
        print_node_traversal(loop)
        captured = capsys.readouterr()
        lines = [l for l in captured.err.strip().split("\n") if l and l != "=== NODE TRAVERSAL ==="]
        # 3 separate lines — no dedup because they're not consecutive.
        assert len(lines) == 3
        assert lines[0] == "task_executor"
        assert lines[1] == "result_reviewer"
        assert lines[2] == "task_executor"
        # No (×N) suffix.
        assert "×" not in captured.err


class TestPrintNodeTraversalEmptyTrace:
    """Empty trace prints the header + (no nodes executed)."""

    def test_empty_trace(self, capsys: pytest.CaptureFixture[str]):
        loop = _MockLoop([])
        print_node_traversal(loop)
        captured = capsys.readouterr()
        assert "=== NODE TRAVERSAL ===" in captured.err
        assert "(no nodes executed)" in captured.err


class TestPrintNodeTraversalOrderPreserved:
    """The traversal order matches the execution trace order."""

    def test_order_preserved(self, capsys: pytest.CaptureFixture[str]):
        loop = _MockLoop([
            {"node_id": "query_analyst"},
            {"node_id": "digester"},
            {"node_id": "worker"},
            {"node_id": "task_create"},
            {"node_id": "task_analyzer"},
            {"node_id": "task_executor"},
            {"node_id": "result_reviewer"},
            {"node_id": "result_aggregation"},
            {"node_id": "response"},
        ])
        print_node_traversal(loop)
        captured = capsys.readouterr()
        lines = [l for l in captured.err.strip().split("\n") if l and l != "=== NODE TRAVERSAL ==="]
        assert lines == [
            "query_analyst",
            "digester",
            "worker",
            "task_create",
            "task_analyzer",
            "task_executor",
            "result_reviewer",
            "result_aggregation",
            "response",
        ]