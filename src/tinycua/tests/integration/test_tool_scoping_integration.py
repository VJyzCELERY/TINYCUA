"""Integration tests for tool scoping — Milestone 4.2."""

from __future__ import annotations


from tinycua.config.node_config import NodeToolPolicy
from tinycua.config.tool_scopes import (
    information_digester_tool_scope,
    query_analyst_tool_scope,
    response_tool_scope,
    result_aggregation_tool_scope,
    result_reviewer_tool_scope,
    task_analyzer_tool_scope,
    task_assessor_tool_scope,
    task_create_tool_scope,
    task_executor_tool_scope,
    worker_tool_scope,
)
from tinycua.config.types import Tool


class MockTool(Tool):
    """Minimal mock tool for testing."""

    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self.name = name


class TestTaskExecutorReceivesCorrectTools:
    """TaskExecutor node receives task tools + selected outer tools + enhanced_context_retrieval."""

    def test_task_executor_receives_correct_tools(self) -> None:
        """TaskExecutor receives task tools, selected outer tools, and enhanced_context_retrieval."""
        # Arrange
        outer_tools = [
            MockTool("web_search"),
            MockTool("calculator"),
            MockTool("read_file"),
        ]
        policy = task_executor_tool_scope()

        # Act
        resolved = policy.resolve_tools(outer_tools)

        # Assert
        tool_names = [t.name for t in resolved]
        assert "task_execute" not in tool_names
        assert "task_result_update" in tool_names
        assert "enhanced_context_retrieval" in tool_names
        assert "web_search" in tool_names
        assert "calculator" in tool_names
        assert "read_file" in tool_names


class TestTaskAnalyzerExcludesTaskInitInCreationMode:
    """TaskAnalyzerNode in task_creation mode does NOT receive TaskInit/TaskCreate."""

    def test_task_analyzer_excludes_task_init_in_creation_mode(self) -> None:
        """TaskAnalyzer in creation mode excludes task_init and task_create."""
        # Arrange
        policy = task_analyzer_tool_scope(mode="task_creation")

        # Act
        resolved = policy.resolve_tools([])

        # Assert
        tool_names = [t.name for t in resolved]
        assert "task_init" not in tool_names
        assert "task_create" not in tool_names
        assert "task_inspect" in tool_names
        assert "task_update" in tool_names
        assert "task_decompose" in tool_names


class TestTaskAnalyzerIncludesTaskInitInRecreationMode:
    """TaskAnalyzerNode in task_recreation mode DOES receive TaskInit/TaskCreate."""

    def test_task_analyzer_includes_task_init_in_recreation_mode(self) -> None:
        """TaskAnalyzer in recreation mode includes task_init and task_create."""
        # Arrange
        policy = task_analyzer_tool_scope(mode="task_recreation")

        # Act
        resolved = policy.resolve_tools([])

        # Assert
        tool_names = [t.name for t in resolved]
        assert "task_init" in tool_names
        assert "task_create" in tool_names
        assert "task_inspect" in tool_names


class TestResponseNodeIncludesEnhancedContextRetrieval:
    """ResponseNode receives final response tools + enhanced_context_retrieval."""

    def test_response_node_includes_enhanced_context_retrieval(self) -> None:
        """ResponseNode includes final_response_synthesis and enhanced_context_retrieval."""
        # Arrange
        policy = response_tool_scope(allow_digest=True)

        # Act
        resolved = policy.resolve_tools([])

        # Assert
        tool_names = [t.name for t in resolved]
        assert "final_response_synthesis" in tool_names
        assert "enhanced_context_retrieval" in tool_names


class TestInformationDigesterScope:
    """InformationDigesterNode receives only enhanced_context_retrieval + digest_information."""

    def test_information_digester_scope(self) -> None:
        """InformationDigester receives exactly enhanced_context_retrieval and digest_information."""
        # Arrange
        policy = information_digester_tool_scope()

        # Act
        resolved = policy.resolve_tools([])

        # Assert
        tool_names = [t.name for t in resolved]
        assert "enhanced_context_retrieval" in tool_names
        assert "digest_information" in tool_names
        assert len(tool_names) == 2


class TestDenyWinsOverAllowForOuterTools:
    """denied_agent_tool_names takes precedence over include_agent_tools='selected'."""

    def test_deny_wins_over_allow_for_outer_tools(self) -> None:
        """Deny list overrides allow list for outer tools."""
        # Arrange
        policy = NodeToolPolicy(
            node_tools=[],
            include_agent_tools="selected",
            allowed_agent_tool_names=["web_search", "calculator"],
            denied_agent_tool_names=["calculator"],
        )
        outer_tools = [
            MockTool("web_search"),
            MockTool("calculator"),
            MockTool("file_read"),
        ]

        # Act
        resolved = policy.resolve_tools(outer_tools)

        # Assert
        tool_names = [t.name for t in resolved]
        assert "web_search" in tool_names
        assert "calculator" not in tool_names
        assert "file_read" not in tool_names


class TestNodeToolsAlwaysIncludedEvenIfDenied:
    """Node tools are always included even if their names appear in denied_agent_tool_names."""

    def test_node_tools_always_included_even_if_denied(self) -> None:
        """Node tools bypass deny list and are always included."""
        # Arrange
        node_tool = MockTool("web_search")
        policy = NodeToolPolicy(
            node_tools=[node_tool],
            include_agent_tools="none",
            denied_agent_tool_names=["web_search"],
        )
        outer_tools = [MockTool("web_search"), MockTool("calculator")]

        # Act
        resolved = policy.resolve_tools(outer_tools)

        # Assert
        tool_names = [t.name for t in resolved]
        assert "web_search" in tool_names  # Node tool is always included
        assert "calculator" not in tool_names


class TestEmptyAllowedListIncludesNoOuterTools:
    """include_agent_tools='selected' with empty allowed list includes no outer tools."""

    def test_empty_allowed_list_includes_no_outer_tools(self) -> None:
        """Empty allowed list with selected mode includes no outer tools."""
        # Arrange
        policy = NodeToolPolicy(
            node_tools=[MockTool("task_execute")],
            include_agent_tools="selected",
            allowed_agent_tool_names=[],
        )
        outer_tools = [MockTool("web_search"), MockTool("calculator")]

        # Act
        resolved = policy.resolve_tools(outer_tools)

        # Assert
        tool_names = [t.name for t in resolved]
        assert "task_execute" in tool_names
        assert "web_search" not in tool_names
        assert "calculator" not in tool_names


class TestQueryAnalystReceivesClassificationAndReadOnlyTools:
    """QueryAnalystNode receives classification + read-only task/context inspection tools."""

    def test_query_analyst_receives_classification_and_read_only_tools(self) -> None:
        """QueryAnalyst receives classification and read-only task inspection tools."""
        # Arrange
        policy = query_analyst_tool_scope()

        # Act
        resolved = policy.resolve_tools([])

        # Assert
        tool_names = [t.name for t in resolved]
        assert "task_inspect" in tool_names
        assert "task_update" not in tool_names
        assert "task_init" not in tool_names


class TestTaskCreateReceivesRootCreationToolsOnly:
    """TaskCreateNode receives deterministic root task creation tools only."""

    def test_task_create_receives_root_creation_tools_only(self) -> None:
        """TaskCreate receives only task_init."""
        # Arrange
        policy = task_create_tool_scope()

        # Act
        resolved = policy.resolve_tools([])

        # Assert
        tool_names = [t.name for t in resolved]
        assert "task_init" in tool_names
        assert "task_create" not in tool_names
        assert "task_inspect" not in tool_names
        assert "task_update" not in tool_names


class TestTaskAssessorReceivesAssessmentTools:
    """TaskAssessorNode receives read-only inspect and handoff tools."""

    def test_task_assessor_receives_assessment_tools(self) -> None:
        """TaskAssessor receives task_inspect and node_handoff but not task_init."""
        # Arrange
        policy = task_assessor_tool_scope()

        # Act
        resolved = policy.resolve_tools([])

        # Assert
        tool_names = [t.name for t in resolved]
        assert "task_inspect" in tool_names
        assert "node_handoff" in tool_names
        assert "task_update" not in tool_names
        assert "task_init" not in tool_names


class TestWorkerReceivesDecisionToolsOnly:
    """WorkerNode receives worker decision tools only."""

    def test_worker_receives_decision_tools_only(self) -> None:
        """Worker receives decision tools but not task_execute."""
        # Arrange
        policy = worker_tool_scope()

        # Act
        resolved = policy.resolve_tools([])

        # Assert
        tool_names = [t.name for t in resolved]
        assert len(tool_names) > 0  # Has decision tools
        assert "task_execute" not in tool_names


class TestResultReviewerReceivesReviewAndUpdateTools:
    """ResultReviewerNode receives explicit review decision tools."""

    def test_result_reviewer_receives_review_and_update_tools(self) -> None:
        """ResultReviewer receives task_review_decision but not task_init."""
        # Arrange
        policy = result_reviewer_tool_scope()

        # Act
        resolved = policy.resolve_tools([])

        # Assert
        tool_names = [t.name for t in resolved]
        assert "task_review_decision" in tool_names
        assert "task_inspect" in tool_names
        assert "task_result_update" not in tool_names
        assert "task_init" not in tool_names


class TestResultAggregationReceivesAggregationTools:
    """ResultAggregationNode receives aggregation/consolidation tools."""

    def test_result_aggregation_receives_aggregation_tools(self) -> None:
        """ResultAggregation receives aggregation tools but not task_execute."""
        # Arrange
        policy = result_aggregation_tool_scope()

        # Act
        resolved = policy.resolve_tools([])

        # Assert
        tool_names = [t.name for t in resolved]
        assert len(tool_names) > 0
        assert "task_execute" not in tool_names


class TestTaskAnalyzerExcludesTaskInitInReanalysisMode:
    """TaskAnalyzerNode in task_reanalysis mode does NOT receive TaskInit/TaskCreate."""

    def test_task_analyzer_excludes_task_init_in_reanalysis_mode(self) -> None:
        """TaskAnalyzer in reanalysis mode excludes task_init and task_create."""
        # Arrange
        policy = task_analyzer_tool_scope(mode="task_reanalysis")

        # Act
        resolved = policy.resolve_tools([])

        # Assert
        tool_names = [t.name for t in resolved]
        assert "task_init" not in tool_names
        assert "task_create" not in tool_names
        assert "task_inspect" in tool_names
        assert "task_update" in tool_names
        assert "task_decompose" in tool_names
