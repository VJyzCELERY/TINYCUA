"""Unit tests for TinyCUATaskAnalyzerNode."""

from __future__ import annotations

import pytest
from tinycua.config.node_config import NodeConfigBase
from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode
from tinycua.loops.node import ProcessNode


class TestTaskAnalyzerNodeInit:
    """Tests for TinyCUATaskAnalyzerNode initialization."""

    def test_inherits_from_process_node(self) -> None:
        """TinyCUATaskAnalyzerNode inherits from ProcessNode."""
        config = NodeConfigBase()
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer", config=config,
        )
        assert isinstance(task_analyzer, ProcessNode)

    def test_default_mode(self) -> None:
        """TaskAnalyzerNode defaults to 'analysis' mode."""
        config = NodeConfigBase()
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer", config=config,
        )
        assert task_analyzer.mode == "analysis"

    def test_initial_analysis_mode(self) -> None:
        """TaskAnalyzerNode can be created with 'initial_analysis' mode."""
        config = NodeConfigBase()
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=config,
            mode="initial_analysis",
        )
        assert task_analyzer.mode == "initial_analysis"

    def test_default_node_id(self) -> None:
        """TaskAnalyzerNode defaults to 'task_analyzer' node_id."""
        config = NodeConfigBase()
        task_analyzer = TinyCUATaskAnalyzerNode(config=config)
        assert task_analyzer.node_id == "task_analyzer"


class TestTaskAnalyzerToolScope:
    """Tests for TinyCUATaskAnalyzerNode tool scope filtering."""

    def test_initial_analysis_excludes_task_init(self) -> None:
        """initial_analysis mode excludes TaskInit from tool_scope."""
        config = NodeConfigBase()
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=config,
            mode="initial_analysis",
        )
        assert "TaskInit" not in task_analyzer.tool_scope

    def test_initial_analysis_excludes_task_create(self) -> None:
        """initial_analysis mode excludes TaskCreate from tool_scope."""
        config = NodeConfigBase()
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=config,
            mode="initial_analysis",
        )
        assert "TaskCreate" not in task_analyzer.tool_scope

    def test_analysis_mode_includes_standard_tools(self) -> None:
        """analysis mode includes standard analysis tools."""
        config = NodeConfigBase()
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=config,
            mode="analysis",
        )
        # Standard tools should be present
        assert len(task_analyzer.tool_scope) > 0
