"""Per-node tool guidance and scope boundary contracts (FR-005, FR-006, FR-007).

Covers:
- build_tool_system_prompt returns behavioral guidance keyed on present tool
  names (not a prose tool list).
- Single-required-tool nodes have a proactive "MUST call <tool>" line in the
  initial instruction.
- Each node instruction has a one-line scope boundary.
"""

from __future__ import annotations

from tinycua.agent.tools.native import (
    append_file,
    read_file,
    run_shell,
    str_replace,
    write_file,
)
from tinycua.config.node_config import create_node_config
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.task_nodes import (
    TinyCUAResultReviewerNode,
    TinyCUATaskAnalyzerNode,
    TinyCUATaskAssessorNode,
    TinyCUATaskExecutorNode,
)
from tinycua.tools.task_tools import (
    TaskDecomposeTool,
    TaskInspectTool,
    TaskResultUpdateTool,
    TaskReviewDecisionTool,
    TaskShrinkTool,
    TaskUpdateTool,
)
from tinycua.tools.handoff_tools import TaskAssessmentDecisionTool


def test_task_executor_tool_guidance_prefers_narrowest_tool() -> None:
    """Executor guidance prefers str_replace over write_file."""
    node = TinyCUATaskExecutorNode(
        node_id="task_executor", config=create_node_config("task_executor")
    )
    tools = [
        TaskResultUpdateTool(),
        read_file,
        write_file,
        str_replace,
        append_file,
        run_shell,
    ]

    guidance = node.build_tool_system_prompt(tools)

    assert "str_replace" in guidance
    assert "append_file" in guidance
    assert "write_file" in guidance
    assert "task_result_update" in guidance


def test_result_reviewer_tool_guidance_matches_evidence_to_claims() -> None:
    """Reviewer guidance requests focused evidence rather than arbitrary checks."""
    node = TinyCUAResultReviewerNode(
        node_id="result_reviewer", config=create_node_config("result_reviewer")
    )
    tools = [
        TaskReviewDecisionTool(),
        TaskInspectTool(),
        TaskUpdateTool(),
        read_file,
        run_shell,
    ]

    guidance = node.build_tool_system_prompt(tools)

    assert "behavioral claims" in guidance.lower()
    assert "artifact claims" in guidance.lower()
    assert "explicitly requested verification" in guidance.lower()
    assert "unrelated" in guidance.lower()
    assert "task_review_decision" in guidance


def test_review_guidance_protects_exact_and_observable_requirements() -> None:
    """Reviewer checks exact deliverables and public behavior without plan drift."""
    node = TinyCUAResultReviewerNode(
        node_id="result_reviewer", config=create_node_config("result_reviewer")
    )

    instruction = f"{node.build_instruction()} {node.build_continuation()}"
    guidance = node.build_tool_system_prompt([TaskReviewDecisionTool(), run_shell])

    assert "concise review_summary" in instruction
    assert "comprehensive review_summary" not in instruction
    assert "existing finding" in instruction
    assert "exact path" in instruction
    assert "public workflow" in instruction
    assert "generated task" in instruction
    assert "primary review target" in instruction
    assert "not independent reviewer observations" in instruction.lower()
    assert "preview truncation" in instruction.lower()
    assert "explicitly requested verification" in guidance.lower()


def test_analyzer_guidance_keeps_exact_singular_deliverables_atomic() -> None:
    """Planning does not split one exact deliverable into competing owners."""
    node = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer", config=create_node_config("task_analyzer")
    )

    instruction = f"{node.build_instruction()} {node.build_continuation()}"

    assert "exactly named deliverable" in instruction
    assert "one task" in instruction


def test_task_analyzer_commit_guidance_names_only_commit_tools() -> None:
    """Analyzer commit guidance omits action-only inspection tools."""
    node = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer", config=create_node_config("task_analyzer")
    )
    tools = [TaskInspectTool(), TaskUpdateTool(), TaskDecomposeTool()]

    guidance = node.build_tool_system_prompt(tools)

    assert "task_inspect" not in guidance
    assert "task_decompose" in guidance or "task_update" in guidance


def test_task_assessor_commit_guidance_names_only_decision_tool() -> None:
    """Assessor commit guidance omits action-only inspection tools."""
    node = TinyCUATaskAssessorNode(
        node_id="task_assessor", config=create_node_config("task_assessor")
    )
    tools = [TaskInspectTool(), TaskAssessmentDecisionTool()]

    guidance = node.build_tool_system_prompt(tools)

    assert "task_assessment_decision" in guidance
    assert "task_inspect" not in guidance
    assert "findings" in guidance
    assert "advisories" in guidance
    assert "rationale" in guidance


def test_final_assessor_guidance_explains_advisory_proceed_behavior() -> None:
    """Final findings are preserved without implying another analyzer pass."""
    node = TinyCUATaskAssessorNode(
        node_id="task_assessor",
        config=create_node_config("task_assessor", mode="final_assessment"),
    )

    guidance = node.build_tool_system_prompt([TaskAssessmentDecisionTool()])

    assert "both decisions proceed" in guidance.lower()
    assert "exhausted advisories" in guidance.lower()
    assert "without another analyzer" in guidance.lower()


def test_task_analyzer_treats_assessor_recommendations_as_advisory() -> None:
    """Analyzer chooses how to address Assessor recommendations."""
    node = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer", config=create_node_config("task_analyzer")
    )

    guidance = node.build_tool_system_prompt([TaskShrinkTool(), TaskUpdateTool()])

    assert "TaskAssessor recommendation" in guidance
    assert "decide" in guidance
    assert "Do not change tasks merely" in guidance


def test_tool_guidance_empty_when_no_tools_present() -> None:
    """Guidance is empty when no relevant tools are present (graceful no-op)."""
    node = TinyCUATaskExecutorNode(
        node_id="task_executor", config=create_node_config("task_executor")
    )

    guidance = node.build_tool_system_prompt([])

    # Without tools, the guidance may be empty or a minimal fallback, but must
    # not reference tool names that aren't present.
    assert "write_file" not in guidance


def test_query_analyst_instruction_has_proactive_required_tool_line() -> None:
    """QueryAnalyst initial instruction says the final action MUST call the route tool."""
    node = TinyCUAQueryAnalystNode(
        node_id="query_analyst", config=create_node_config("query_analyst")
    )

    instruction = node.build_instruction()

    assert "select_query_route" in instruction
    assert "MUST" in instruction


def test_task_executor_instruction_defers_commit_tool_to_commit_phase() -> None:
    """TaskExecutor action instruction does not require an unavailable commit tool."""
    node = TinyCUATaskExecutorNode(
        node_id="task_executor", config=create_node_config("task_executor")
    )

    instruction = node.build_instruction()

    assert "task_result_update" not in instruction
    assert "MUST" in instruction


def test_result_reviewer_instruction_defers_commit_tool_to_commit_phase() -> None:
    """Reviewer action instruction does not require an unavailable commit tool."""
    node = TinyCUAResultReviewerNode(
        node_id="result_reviewer", config=create_node_config("result_reviewer")
    )

    instruction = node.build_instruction()

    assert "task_review_decision" not in instruction


def test_task_executor_instruction_has_scope_boundary() -> None:
    """Executor instruction has a scope-boundary line."""
    node = TinyCUATaskExecutorNode(
        node_id="task_executor", config=create_node_config("task_executor")
    )

    instruction = node.build_instruction()

    # Scope boundary: "You only ...; you do not ..." pattern.
    assert "you do not" in instruction.lower() or "do not" in instruction.lower()


def test_task_analyzer_instruction_has_scope_boundary() -> None:
    """Analyzer instruction has a scope-boundary line (no execution)."""
    node = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer", config=create_node_config("task_analyzer")
    )

    instruction = node.build_instruction()

    assert "do not" in instruction.lower()


def test_task_assessor_instruction_has_scope_boundary() -> None:
    """Assessor instruction has a scope-boundary line (no mutation)."""
    node = TinyCUATaskAssessorNode(
        node_id="task_assessor", config=create_node_config("task_assessor")
    )

    instruction = node.build_instruction()

    assert "do not" in instruction.lower()


def test_result_reviewer_instruction_has_scope_boundary() -> None:
    """Reviewer instruction has a scope-boundary line (read-only)."""
    node = TinyCUAResultReviewerNode(
        node_id="result_reviewer", config=create_node_config("result_reviewer")
    )

    instruction = node.build_instruction()

    assert "do not" in instruction.lower()
