"""Unit tests for tool_scopes module — per-node tool scope factory functions.

Tests verify each factory function returns a NodeToolPolicy with the correct
tool scope matching the design document.
"""

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
from tinycua.tools.digest_information import DigestInformationTool
from tinycua.tools.enhanced_context_retrieval import EnhancedContextRetrievalTool


class TestQueryAnalystToolScope:
    """Test query_analyst_tool_scope() matches design."""

    def test_returns_node_tool_policy(self) -> None:
        """Returns a NodeToolPolicy instance."""
        policy = query_analyst_tool_scope()
        assert isinstance(policy, NodeToolPolicy)

    def test_includes_task_inspect(self) -> None:
        """Includes TaskInspectTool."""
        policy = query_analyst_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "task_inspect" in tool_names

    def test_no_mutation_tools(self) -> None:
        """Does not include mutation tools."""
        policy = query_analyst_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "task_update" not in tool_names
        assert "task_init" not in tool_names
        assert "task_create" not in tool_names

    def test_no_outer_tools(self) -> None:
        """Does not include outer agent tools."""
        policy = query_analyst_tool_scope()
        assert policy.include_agent_tools == "none"


class TestInformationDigesterToolScope:
    """Test information_digester_tool_scope() matches design."""

    def test_returns_node_tool_policy(self) -> None:
        """Returns a NodeToolPolicy instance."""
        policy = information_digester_tool_scope()
        assert isinstance(policy, NodeToolPolicy)

    def test_includes_enhanced_context_retrieval(self) -> None:
        """Includes EnhancedContextRetrievalTool."""
        policy = information_digester_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "enhanced_context_retrieval" in tool_names

    def test_includes_digest_information(self) -> None:
        """Includes DigestInformationTool."""
        policy = information_digester_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "digest_information" in tool_names

    def test_exactly_two_tools(self) -> None:
        """Has exactly two tools."""
        policy = information_digester_tool_scope()
        assert len(policy.node_tools) == 2

    def test_no_outer_tools(self) -> None:
        """Does not include outer agent tools."""
        policy = information_digester_tool_scope()
        assert policy.include_agent_tools == "none"


class TestWorkerToolScope:
    """Test worker_tool_scope() matches design."""

    def test_returns_node_tool_policy(self) -> None:
        """Returns a NodeToolPolicy instance."""
        policy = worker_tool_scope()
        assert isinstance(policy, NodeToolPolicy)

    def test_has_decision_tools(self) -> None:
        """Has decision tools."""
        policy = worker_tool_scope()
        assert len(policy.node_tools) > 0

    def test_no_task_execute(self) -> None:
        """Does not include task_execute."""
        policy = worker_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "task_execute" not in tool_names

    def test_no_outer_tools(self) -> None:
        """Does not include outer agent tools."""
        policy = worker_tool_scope()
        assert policy.include_agent_tools == "none"


class TestTaskCreateToolScope:
    """Test task_create_tool_scope() matches design."""

    def test_returns_node_tool_policy(self) -> None:
        """Returns a NodeToolPolicy instance."""
        policy = task_create_tool_scope()
        assert isinstance(policy, NodeToolPolicy)

    def test_includes_task_init(self) -> None:
        """Includes TaskInitTool."""
        policy = task_create_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "task_init" in tool_names

    def test_excludes_task_create(self) -> None:
        """Excludes child TaskCreateTool from root creation scope."""
        policy = task_create_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "task_create" not in tool_names

    def test_no_inspect_or_update(self) -> None:
        """Does not include inspect or update tools."""
        policy = task_create_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "task_inspect" not in tool_names
        assert "task_update" not in tool_names

    def test_no_outer_tools(self) -> None:
        """Does not include outer agent tools."""
        policy = task_create_tool_scope()
        assert policy.include_agent_tools == "none"


class TestTaskAnalyzerToolScope:
    """Test task_analyzer_tool_scope() in all three modes."""

    def test_creation_mode_excludes_task_init(self) -> None:
        """task_creation mode excludes task_init."""
        policy = task_analyzer_tool_scope(mode="task_creation")
        tool_names = [t.name for t in policy.node_tools]
        assert "task_init" not in tool_names
        assert "task_create" not in tool_names

    def test_creation_mode_includes_structural_tools(self) -> None:
        """task_creation mode includes structural tools."""
        policy = task_analyzer_tool_scope(mode="task_creation")
        tool_names = [t.name for t in policy.node_tools]
        assert "task_inspect" in tool_names
        assert "task_update" in tool_names
        assert "task_decompose" in tool_names

    def test_recreation_mode_includes_task_init(self) -> None:
        """task_recreation mode includes task_init."""
        policy = task_analyzer_tool_scope(mode="task_recreation")
        tool_names = [t.name for t in policy.node_tools]
        assert "task_init" in tool_names

    def test_recreation_mode_includes_task_create(self) -> None:
        """task_recreation mode includes task_create."""
        policy = task_analyzer_tool_scope(mode="task_recreation")
        tool_names = [t.name for t in policy.node_tools]
        assert "task_create" in tool_names

    def test_recreation_mode_includes_structural_tools(self) -> None:
        """task_recreation mode includes structural tools."""
        policy = task_analyzer_tool_scope(mode="task_recreation")
        tool_names = [t.name for t in policy.node_tools]
        assert "task_inspect" in tool_names
        assert "task_update" in tool_names
        assert "task_decompose" in tool_names

    def test_reanalysis_mode_excludes_task_init(self) -> None:
        """task_reanalysis mode excludes task_init."""
        policy = task_analyzer_tool_scope(mode="task_reanalysis")
        tool_names = [t.name for t in policy.node_tools]
        assert "task_init" not in tool_names
        assert "task_create" not in tool_names

    def test_reanalysis_mode_includes_structural_tools(self) -> None:
        """task_reanalysis mode includes structural tools."""
        policy = task_analyzer_tool_scope(mode="task_reanalysis")
        tool_names = [t.name for t in policy.node_tools]
        assert "task_inspect" in tool_names
        assert "task_update" in tool_names
        assert "task_decompose" in tool_names

    def test_no_outer_tools(self) -> None:
        """Does not include outer agent tools in any mode."""
        for mode in ("task_creation", "task_recreation", "task_reanalysis"):
            policy = task_analyzer_tool_scope(mode=mode)
            assert policy.include_agent_tools == "none"


class TestTaskAssessorToolScope:
    """Test task_assessor_tool_scope() matches design."""

    def test_returns_node_tool_policy(self) -> None:
        """Returns a NodeToolPolicy instance."""
        policy = task_assessor_tool_scope()
        assert isinstance(policy, NodeToolPolicy)

    def test_includes_task_inspect(self) -> None:
        """Includes TaskInspectTool."""
        policy = task_assessor_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "task_inspect" in tool_names

    def test_includes_task_update(self) -> None:
        """Includes TaskUpdateTool."""
        policy = task_assessor_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "task_update" in tool_names

    def test_no_task_init(self) -> None:
        """Does not include TaskInitTool."""
        policy = task_assessor_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "task_init" not in tool_names

    def test_no_outer_tools(self) -> None:
        """Does not include outer agent tools."""
        policy = task_assessor_tool_scope()
        assert policy.include_agent_tools == "none"


class TestTaskExecutorToolScope:
    """Test task_executor_tool_scope() matches design."""

    def test_returns_node_tool_policy(self) -> None:
        """Returns a NodeToolPolicy instance."""
        policy = task_executor_tool_scope()
        assert isinstance(policy, NodeToolPolicy)

    def test_includes_task_execute(self) -> None:
        """Includes TaskExecuteTool."""
        policy = task_executor_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "task_execute" in tool_names

    def test_includes_task_result_update(self) -> None:
        """Includes TaskResultUpdateTool."""
        policy = task_executor_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "task_result_update" in tool_names

    def test_includes_enhanced_context_retrieval(self) -> None:
        """Includes EnhancedContextRetrievalTool."""
        policy = task_executor_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "enhanced_context_retrieval" in tool_names

    def test_includes_todo_tools(self) -> None:
        """Includes TodoReadTool and TodoWriteTool."""
        policy = task_executor_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "todo_read" in tool_names
        assert "todo_write" in tool_names

    def test_selected_outer_tools(self) -> None:
        """Uses selected mode for outer agent tools."""
        policy = task_executor_tool_scope()
        assert policy.include_agent_tools == "selected"
        assert "web_search" in policy.allowed_agent_tool_names
        assert "read_file" in policy.allowed_agent_tool_names
        assert "calculator" in policy.allowed_agent_tool_names


class TestResultReviewerToolScope:
    """Test result_reviewer_tool_scope() matches design."""

    def test_returns_node_tool_policy(self) -> None:
        """Returns a NodeToolPolicy instance."""
        policy = result_reviewer_tool_scope()
        assert isinstance(policy, NodeToolPolicy)

    def test_includes_task_review_decision(self) -> None:
        """Includes TaskReviewDecisionTool."""
        policy = result_reviewer_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "task_review_decision" in tool_names
        assert "task_result_update" not in tool_names

    def test_no_task_init(self) -> None:
        """Does not include TaskInitTool."""
        policy = result_reviewer_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "task_init" not in tool_names

    def test_read_only_outer_tools(self) -> None:
        """Reviewer may inspect artifacts but cannot mutate workspace files."""
        policy = result_reviewer_tool_scope()
        assert policy.include_agent_tools == "selected"
        assert "list_files" in policy.allowed_agent_tool_names
        assert "read_file" in policy.allowed_agent_tool_names
        assert "write_file" not in policy.allowed_agent_tool_names
        assert "edit_file" not in policy.allowed_agent_tool_names
        assert "run_shell" not in policy.allowed_agent_tool_names


class TestResultAggregationToolScope:
    """Test result_aggregation_tool_scope() matches design."""

    def test_returns_node_tool_policy(self) -> None:
        """Returns a NodeToolPolicy instance."""
        policy = result_aggregation_tool_scope()
        assert isinstance(policy, NodeToolPolicy)

    def test_has_aggregation_tools(self) -> None:
        """Has aggregation tools."""
        policy = result_aggregation_tool_scope()
        assert len(policy.node_tools) > 0

    def test_no_task_execute(self) -> None:
        """Does not include task_execute."""
        policy = result_aggregation_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "task_execute" not in tool_names

    def test_no_outer_tools(self) -> None:
        """Does not include outer agent tools."""
        policy = result_aggregation_tool_scope()
        assert policy.include_agent_tools == "none"


class TestResponseToolScope:
    """Test response_tool_scope() with allow_digest=True and False."""

    def test_returns_node_tool_policy(self) -> None:
        """Returns a NodeToolPolicy instance."""
        policy = response_tool_scope()
        assert isinstance(policy, NodeToolPolicy)

    def test_includes_final_response_synthesis(self) -> None:
        """Includes FinalResponseSynthesisTool."""
        policy = response_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "final_response_synthesis" in tool_names

    def test_includes_enhanced_context_retrieval(self) -> None:
        """Includes EnhancedContextRetrievalTool."""
        policy = response_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "enhanced_context_retrieval" in tool_names

    def test_includes_todo_tools(self) -> None:
        """Includes TodoReadTool and TodoWriteTool."""
        policy = response_tool_scope()
        tool_names = [t.name for t in policy.node_tools]
        assert "todo_read" in tool_names
        assert "todo_write" in tool_names

    def test_allow_digest_true_includes_digest(self) -> None:
        """allow_digest=True includes DigestInformationTool."""
        policy = response_tool_scope(allow_digest=True)
        tool_names = [t.name for t in policy.node_tools]
        assert "digest_information" in tool_names

    def test_allow_digest_false_excludes_digest(self) -> None:
        """allow_digest=False excludes DigestInformationTool."""
        policy = response_tool_scope(allow_digest=False)
        tool_names = [t.name for t in policy.node_tools]
        assert "digest_information" not in tool_names

    def test_selected_outer_tools(self) -> None:
        """Uses selected mode for outer agent tools."""
        policy = response_tool_scope()
        assert policy.include_agent_tools == "selected"
        assert "web_search" in policy.allowed_agent_tool_names


class TestEnhancedContextRetrievalCache:
    """Test enhanced_context_retrieval cache creation and isolation."""

    def test_cache_created_on_first_call(self) -> None:
        """Cache is created on first call."""
        tool = EnhancedContextRetrievalTool()
        context = [{"role": "user", "content": "Test"}]
        result = tool(session_context=context, query="test")
        assert result is not None
        assert "source" in result

    def test_cache_reused_on_subsequent_calls(self) -> None:
        """Cache is reused on subsequent calls with same context."""
        tool = EnhancedContextRetrievalTool()
        context = [{"role": "user", "content": "Test"}]
        result1 = tool(session_context=context, query="test")
        result2 = tool(session_context=context, query="test")
        assert result1["source"] == "fresh"
        assert result2["source"] == "cache"

    def test_different_contexts_get_separate_caches(self) -> None:
        """Different invocation scopes get independent caches."""
        tool1 = EnhancedContextRetrievalTool()
        tool2 = EnhancedContextRetrievalTool()
        context1 = [{"role": "user", "content": "Context A"}]
        context2 = [{"role": "user", "content": "Context B"}]
        result1 = tool1(session_context=context1, query="test")
        result2 = tool2(session_context=context2, query="test")
        assert result1 is not None
        assert result2 is not None


class TestDigestInformationOutput:
    """Test digest_information output format."""

    def test_returns_structured_digest(self) -> None:
        """Returns a structured digest dict."""
        tool = DigestInformationTool()
        result = tool(information="test info")
        assert "summary" in result
        assert result["summary"] == "test info"
        assert "key_points" in result
