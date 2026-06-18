"""Per-node tool scope definitions and factory functions for TinyCUA nodes.

Each factory function returns a NodeToolPolicy configured with the correct
tool scope for its corresponding node type. These are used by
TinyCUALoop._prepare_node() to resolve tools before LLM calls.

Reference:
    src/tinycua/docs/design/constants/tools.md — authoritative tool-to-node mapping.
    design.md — design decisions and rationale.
"""

from __future__ import annotations

from tinycua.config.node_config import NodeToolPolicy
from tinycua.tools.digest_information import DigestInformationTool
from tinycua.tools.enhanced_context_retrieval import EnhancedContextRetrievalTool
from tinycua.tools.handoff_tools import NodeHandoffTool
from tinycua.tools.routing import QueryRouteSelectionTool, WorkerRouteSelectionTool
from tinycua.tools.task_tools import (
    FinalResponseSynthesisTool,
    TaskCreateTool,
    TaskDecomposeTool,
    TaskInitTool,
    TaskInspectTool,
    TaskResultUpdateTool,
    TaskReviewDecisionTool,
    TaskUpdateTool,
)
from tinycua.tools.todo_tools import TodoReadTool, TodoWriteTool

# Agent tool names grouped by access level.  Nodes that only need
# read-only verification (e.g. ResultReviewer) use READONLY_AGENT_TOOLS
# so they can inspect the workspace and run tests without mutating files.
READONLY_AGENT_TOOLS: list[str] = ["read_file", "list_files", "run_shell_readonly"]


def query_analyst_tool_scope() -> NodeToolPolicy:
    """Classification + read-only task/context inspection tools.

    QueryAnalystNode receives classification tools and read-only
    task/context inspection tools. No mutation tools are included.

    Returns:
        NodeToolPolicy for QueryAnalystNode.
    """
    return NodeToolPolicy(
        node_tools=[QueryRouteSelectionTool(), TaskInspectTool()],
        include_agent_tools="none",
    )


def information_digester_tool_scope() -> NodeToolPolicy:
    """Enhanced context retrieval + digest information tools.

    InformationDigesterNode receives exactly two tools:
    enhanced_context_retrieval and digest_information.

    Returns:
        NodeToolPolicy for InformationDigesterNode.
    """
    return NodeToolPolicy(
        node_tools=[
            EnhancedContextRetrievalTool(),
            DigestInformationTool(),
        ],
        include_agent_tools="none",
    )


def worker_tool_scope() -> NodeToolPolicy:
    """Worker decision tools only.

    WorkerNode receives worker decision tools for routing decisions.
    No task mutation tools are included.

    Returns:
        NodeToolPolicy for WorkerNode.
    """
    return NodeToolPolicy(
        node_tools=[WorkerRouteSelectionTool(), TaskInspectTool()],
        include_agent_tools="none",
    )


def task_create_tool_scope() -> NodeToolPolicy:
    """Deterministic root task creation tools.

    TaskCreateNode receives only TaskInit for initializing exactly one new
    task tree root. Subtask creation is delegated to TaskAnalyzer.

    Returns:
        NodeToolPolicy for TaskCreateNode.
    """
    return NodeToolPolicy(
        node_tools=[TaskInitTool()],
        include_agent_tools="none",
    )


def task_analyzer_tool_scope(
    mode: str = "task_creation",
) -> NodeToolPolicy:
    """Structural task tools with mode-dependent TaskInit/TaskCreate.

    TaskAnalyzerNode receives task_inspect, task_update, and task_decompose
    in all modes. TaskInit and TaskCreate are only included in
    task_recreation mode.

    Args:
        mode: One of "task_creation", "task_recreation", or "task_reanalysis".

    Returns:
        NodeToolPolicy for TaskAnalyzerNode.
    """
    base_tools = [TaskInspectTool(), TaskUpdateTool(), TaskDecomposeTool()]
    if mode == "task_recreation":
        base_tools.extend([TaskInitTool(), TaskCreateTool()])
    return NodeToolPolicy(
        node_tools=base_tools,
        include_agent_tools="none",
    )


def task_assessor_tool_scope() -> NodeToolPolicy:
    """Task assessment/read/update tools.

    TaskAssessorNode receives task_inspect and task_update for
    assessing task state. No creation tools are included.

    Returns:
        NodeToolPolicy for TaskAssessorNode.
    """
    return NodeToolPolicy(
        node_tools=[TaskInspectTool(), NodeHandoffTool()],
        include_agent_tools="none",
    )


def task_executor_tool_scope() -> NodeToolPolicy:
    """Task execution + selected outer agent tools + enhanced_context_retrieval.

    TaskExecutorNode receives task execution tools, enhanced context
    retrieval, and selected outer agent tools (web_search, file_read, calculator).

    Returns:
        NodeToolPolicy for TaskExecutorNode.
    """
    return NodeToolPolicy(
        node_tools=[
            TaskResultUpdateTool(),
            EnhancedContextRetrievalTool(),
            TodoReadTool(),
            TodoWriteTool(),
        ],
        include_agent_tools="selected",
        allowed_agent_tool_names=[
            "web_search",
            "fetch_url",
            "read_file",
            "write_file",
            "edit_file",
            "list_files",
            "run_shell",
            "run_python",
            "calculator",
        ],
    )


def result_reviewer_tool_scope() -> NodeToolPolicy:
    """Review/decision, inspection, and context curation tools.

    ResultReviewerNode verifies executor outcome reports, calls task_inspect
    to review task state, and can update unfinished task descriptions with
    relevant discoveries before proceeding.

    Includes run_shell_readonly for running tests and verification commands
    without risk of accidental filesystem mutation.

    Returns:
        NodeToolPolicy for ResultReviewerNode.
    """
    return NodeToolPolicy(
        node_tools=[TaskReviewDecisionTool(), TaskInspectTool(), TaskUpdateTool()],
        include_agent_tools="selected",
        allowed_agent_tool_names=READONLY_AGENT_TOOLS,
    )


def result_aggregation_tool_scope() -> NodeToolPolicy:
    """Aggregation/consolidation tools.

    ResultAggregationNode receives aggregation tools for consolidating
    results from multiple task executions.

    Returns:
        NodeToolPolicy for ResultAggregationNode.
    """
    return NodeToolPolicy(
        node_tools=[TaskInspectTool()],
        include_agent_tools="none",
    )


def deterministic_controller_tool_scope() -> NodeToolPolicy:
    """No-tool policy for deterministic orchestration controller nodes."""
    return NodeToolPolicy(node_tools=[], include_agent_tools="none")


def response_tool_scope(allow_digest: bool = True) -> NodeToolPolicy:
    """Same base as TaskExecutor + final response synthesis + optional digest.

    ResponseNode has the same base toolset as TaskExecutor, plus
    enhanced_context_retrieval and optional information-digestion
    request capability.

    Args:
        allow_digest: When True, includes digest_information tool.

    Returns:
        NodeToolPolicy for ResponseNode.
    """
    node_tools = [
        FinalResponseSynthesisTool(),
        EnhancedContextRetrievalTool(),
        TodoReadTool(),
        TodoWriteTool(),
    ]
    if allow_digest:
        node_tools.append(DigestInformationTool())

    return NodeToolPolicy(
        node_tools=node_tools,
        include_agent_tools="selected",
        allowed_agent_tool_names=[
            "web_search",
            "fetch_url",
            "read_file",
            "write_file",
            "edit_file",
            "list_files",
            "run_shell",
            "run_python",
            "calculator",
        ],
    )
