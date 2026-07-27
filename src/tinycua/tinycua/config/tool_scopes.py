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
from tinycua.tools.handoff_tools import TaskAssessmentDecisionTool
from tinycua.tools.query_context_summary import QueryContextSummaryTool
from tinycua.tools.routing import QueryRouteSelectionTool, WorkerRouteSelectionTool
from tinycua.tools.task_tools import (
    FinalResponseSynthesisTool,
    TaskCreateTool,
    TaskDecomposeTool,
    TaskInitTool,
    TaskInspectTool,
    TaskResultUpdateTool,
    TaskReviewDecisionTool,
    TaskShrinkTool,
    TaskUpdateTool,
)
from tinycua.tools.todo_tools import TodoReadTool, TodoWriteTool

# Exploratory tools: inspection-oriented agent tools. ``run_shell`` is gated
# in-tool by a hardline blocklist (unrecoverable commands) + a recoverable-
# destructive warning layer, so it is safe to hand to read-oriented nodes
# (reviewer, analyzer, assessor, digester, aggregation) for verification
# without a separate neutered "readonly" tool. The gate is in shell.py.
EXPLORATORY_AGENT_TOOLS: list[str] = [
    "read_file",
    "list_files",
    "search_files",
    "run_shell",
    "web_search",
    "fetch_url",
]


def query_analyst_tool_scope() -> NodeToolPolicy:
    """Classification + read-only task/context inspection tools.

    QueryAnalystNode receives classification tools and read-only
    task/context inspection tools. No mutation tools are included.

    Returns:
        NodeToolPolicy for QueryAnalystNode.
    """
    return NodeToolPolicy(
        node_tools=[
            QueryContextSummaryTool(),
            QueryRouteSelectionTool(),
            TaskInspectTool(),
        ],
        include_agent_tools="none",
    )


def information_digester_tool_scope() -> NodeToolPolicy:
    """Enhanced context retrieval + digest information + exploratory tools.

    InformationDigesterNode receives enhanced_context_retrieval,
    digest_information, and read-only exploratory tools (web search,
    file inspection) to gather context before digestion.

    Returns:
        NodeToolPolicy for InformationDigesterNode.
    """
    return NodeToolPolicy(
        node_tools=[
            EnhancedContextRetrievalTool(),
            DigestInformationTool(),
        ],
        include_agent_tools="selected",
        allowed_agent_tool_names=EXPLORATORY_AGENT_TOOLS,
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
    roadmap root. Subtask creation is delegated to TaskAnalyzer.

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

    TaskAnalyzerNode receives mutation tools in all modes. Reanalysis can add
    missing local work but cannot recreate the root.

    Args:
        mode: One of "task_creation", "task_recreation", or "task_reanalysis".

    Returns:
        NodeToolPolicy for TaskAnalyzerNode.
    """
    base_tools = [
        TaskInspectTool(),
        TaskUpdateTool(),
        TaskDecomposeTool(),
        TaskShrinkTool(),
    ]
    if mode == "task_recreation":
        base_tools.extend([TaskInitTool(), TaskCreateTool()])
    elif mode in {"task_reanalysis", "local_replan", "cancellation_repair"}:
        base_tools.append(TaskCreateTool())
    return NodeToolPolicy(
        node_tools=base_tools,
        include_agent_tools="selected",
        allowed_agent_tool_names=EXPLORATORY_AGENT_TOOLS,
    )


def task_assessor_tool_scope() -> NodeToolPolicy:
    """Task assessment/read/update tools.

    TaskAssessorNode receives task_inspect and its validated decision tool.
    No mutation or generic handoff tools are included.

    Returns:
        NodeToolPolicy for TaskAssessorNode.
    """
    return NodeToolPolicy(
        node_tools=[TaskInspectTool(), TaskAssessmentDecisionTool()],
        include_agent_tools="selected",
        allowed_agent_tool_names=EXPLORATORY_AGENT_TOOLS,
    )


def task_executor_tool_scope() -> NodeToolPolicy:
    """Task execution + selected outer agent tools + enhanced_context_retrieval.

    TaskExecutorNode receives task execution tools, enhanced context
    retrieval, and selected outer agent tools (web_search, fetch_url,
    file ops, shell, python).

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
            "str_replace",
            "append_file",
            "list_files",
            "run_shell",
            "run_python",
        ],
    )


def result_reviewer_tool_scope() -> NodeToolPolicy:
    """Review/decision, inspection, and context-curation tools.

    ResultReviewerNode reviews executor outcomes and atomically records the
    active report, decision, and any relevant future-task context handoffs.

    Includes run_shell (gated in-tool: hardline commands blocked, recoverable
    destructive commands warn but execute) for optional inspection commands.

    Returns:
        NodeToolPolicy for ResultReviewerNode.
    """
    return NodeToolPolicy(
        node_tools=[TaskReviewDecisionTool(), TaskInspectTool()],
        include_agent_tools="selected",
        allowed_agent_tool_names=EXPLORATORY_AGENT_TOOLS,
    )


def result_aggregation_tool_scope() -> NodeToolPolicy:
    """Aggregation/consolidation + exploratory tools.

    ResultAggregationNode receives aggregation tools for consolidating
    results from multiple task executions, plus read-only exploratory
    tools to inspect artifacts during aggregation.

    Returns:
        NodeToolPolicy for ResultAggregationNode.
    """
    return NodeToolPolicy(
        node_tools=[TaskInspectTool()],
        include_agent_tools="selected",
        allowed_agent_tool_names=EXPLORATORY_AGENT_TOOLS,
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
            "str_replace",
            "append_file",
            "list_files",
            "run_shell",
            "run_python",
        ],
    )
