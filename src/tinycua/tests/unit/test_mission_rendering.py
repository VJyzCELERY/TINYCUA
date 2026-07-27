"""Mission block rendering in worker-internal node continuations (FR-003)."""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.loops.task_nodes import (
    TinyCUAResultAggregationNode,
    TinyCUAResultReviewerNode,
    TinyCUATaskAnalyzerNode,
    TinyCUATaskAssessorNode,
    TinyCUATaskExecutorNode,
)
from tinycua.loops.node_contract import get_node_contract
from tinycua.models.session import Session
from tinycua.models.task import TaskResult
from tinycua.tools.task_tools import TaskDecomposeTool


def _session_with_mission(
    mission: str = "",
    constraints: list[str] | None = None,
    context: str = "",
    key_points: list[str] | None = None,
) -> Session:
    """Build a session whose root task carries a mission + constraints + context."""
    session = Session()
    root = session.task_store.create_task("Root goal")
    root.metadata["mission"] = mission
    root.metadata["inherited_constraints"] = constraints or []
    root.metadata["mission_context"] = context
    root.metadata["mission_key_points"] = key_points or []
    child = session.task_store.create_task("Child task", parent_id=root.task_id)
    child.metadata["inherited_constraints"] = constraints or []
    session.task_store.record_result(
        child.task_id, TaskResult(content="done", success=True)
    )
    return session


def test_task_analyzer_renders_mission_block() -> None:
    session = _session_with_mission(
        "Build a clock app in a single HTML file.", ["single file"]
    )
    node = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer", config=create_node_config("task_analyzer")
    )
    node.ensure_session(session)

    prompt = node.build_continuation(session)

    assert "## Current Mission — Context Only" in prompt
    assert "not your assigned task" in prompt
    assert "Build a clock app in a single HTML file." in prompt
    assert "single file" in prompt


def test_task_assessor_renders_mission_block() -> None:
    session = _session_with_mission("Research transformers.", ["use markdown"])
    node = TinyCUATaskAssessorNode(
        node_id="task_assessor", config=create_node_config("task_assessor")
    )
    node.ensure_session(session)

    prompt = node.build_continuation(session)

    assert "## Current Mission — Context Only" in prompt
    assert "Research transformers." in prompt
    assert "use markdown" in prompt


def test_planning_boundaries_share_the_granularity_rubric() -> None:
    """Analyzer, assessor, tool, and contract teach one neutral split rule."""
    analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer", config=create_node_config("task_analyzer")
    )
    assessor = TinyCUATaskAssessorNode(
        node_id="task_assessor", config=create_node_config("task_assessor")
    )
    texts = [
        analyzer._instruction,
        assessor._instruction,
        TaskDecomposeTool().description,
        get_node_contract("task_analyzer").goal,
        get_node_contract("task_assessor").goal,
    ]

    for text in texts:
        normalized = text.lower()
        assert "materially distinct concerns" in normalized
        assert "narrower context" in normalized
        assert "independent evidence" in normalized
        assert "tightly coupled" in normalized
        assert "lifecycle-only phases" in normalized


def test_task_executor_renders_mission_block() -> None:
    session = _session_with_mission("Make an analog clock.", ["single HTML file"])
    node = TinyCUATaskExecutorNode(
        node_id="task_executor", config=create_node_config("task_executor")
    )
    node.ensure_session(session)

    prompt = node.build_continuation(session)

    assert "## Current Mission — Context Only" in prompt
    assert "Make an analog clock." in prompt
    assert "single HTML file" in prompt


def test_original_request_outranks_generated_task_text() -> None:
    """Generated roadmap text cannot override the user's immutable contract."""
    session = _session_with_mission("Build a local app.", ["do not use a database"])
    nodes = (
        TinyCUATaskAnalyzerNode(
            node_id="task_analyzer", config=create_node_config("task_analyzer")
        ),
        TinyCUATaskAssessorNode(
            node_id="task_assessor", config=create_node_config("task_assessor")
        ),
        TinyCUATaskExecutorNode(
            node_id="task_executor", config=create_node_config("task_executor")
        ),
        TinyCUAResultReviewerNode(
            node_id="result_reviewer", config=create_node_config("result_reviewer")
        ),
    )

    for node in nodes:
        node.ensure_session(session)
        prompt = node.build_continuation(session)
        assert "original request and hard constraints control" in prompt.lower()
        assert "generated task text" in prompt.lower()


def test_executor_requires_scope_mismatch_reporting() -> None:
    """Executor guidance distinguishes incidental effects from sibling execution."""
    node = TinyCUATaskExecutorNode(
        node_id="task_executor", config=create_node_config("task_executor")
    )
    guidance = f"{node._instruction} {node._continuation}".lower()

    assert "do not intentionally implement pending sibling" in guidance
    assert "why it was required" in guidance
    assert "evidence" in guidance
    assert "partially or fully satisfied" in guidance
    assert "scope mismatch" in guidance


def test_executor_renders_targeted_planning_advisories() -> None:
    """Budget-exhausted planning concerns remain visible during execution."""
    session = _session_with_mission("Build an app.")
    active = session.task_store.get_active_task()
    assert active is not None
    active.metadata["planning_advisories"] = [
        {"advisory": "Verify the integration seam.", "analysis_budget_exhausted": True}
    ]
    node = TinyCUATaskExecutorNode(
        node_id="task_executor", config=create_node_config("task_executor")
    )
    node.ensure_session(session)

    prompt = node.build_continuation(session)

    assert "Planning advisories" in prompt
    assert "Verify the integration seam." in prompt


def test_result_reviewer_renders_mission_block() -> None:
    session = _session_with_mission("Build a Notion clone.", ["python backend"])
    node = TinyCUAResultReviewerNode(
        node_id="result_reviewer", config=create_node_config("result_reviewer")
    )
    node.ensure_session(session)

    prompt = node.build_continuation(session)

    assert "## Current Mission — Context Only" in prompt
    assert "Build a Notion clone." in prompt
    assert "python backend" in prompt


def test_result_aggregation_renders_mission_block() -> None:
    session = _session_with_mission("Write a report.", ["markdown"])
    node = TinyCUAResultAggregationNode(
        node_id="result_aggregation", config=create_node_config("result_aggregation")
    )
    node.ensure_session(session)

    prompt = node.build_continuation(session)

    assert "## Current Mission — Context Only" in prompt
    assert "Write a report." in prompt


def test_mission_block_empty_when_no_mission() -> None:
    """When no mission is set, no ## Mission block is rendered (no-op)."""
    session = Session()
    session.task_store.create_task("Root")
    node = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer", config=create_node_config("task_analyzer")
    )
    node.ensure_session(session)

    prompt = node.build_continuation(session)

    assert "## Current Mission — Context Only" not in prompt


def test_mission_block_includes_digester_context_and_key_points() -> None:
    """Mission block renders {context}\\n{query} — digester research first, then original request."""
    session = _session_with_mission(
        mission="Research frontier LLMs.",
        context="Frontier LLMs as of 2026 include Claude Opus 4.8, GPT-5.5, Gemini 3.1.",
        key_points=["Claude Opus 4.8 leads on coding", "GPT-5.5 leads on reasoning"],
    )
    node = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer", config=create_node_config("task_analyzer")
    )
    node.ensure_session(session)

    prompt = node.build_continuation(session)

    assert "## Current Mission — Context Only" in prompt
    # Context (digester research) appears before the original request.
    assert "Frontier LLMs as of 2026" in prompt
    assert "Key findings:" in prompt
    assert "Claude Opus 4.8 leads on coding" in prompt
    assert "Original request: Research frontier LLMs." in prompt
    # Context should appear before the original request (the {context}\n{query} structure).
    assert prompt.index("Frontier LLMs as of 2026") < prompt.index("Original request:")


def test_mission_block_omits_empty_sections() -> None:
    """No key points → no 'Key findings:' header. No context → no context line."""
    session = _session_with_mission(
        mission="Build a clock.", constraints=["single file"]
    )
    node = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer", config=create_node_config("task_analyzer")
    )
    node.ensure_session(session)

    prompt = node.build_continuation(session)

    assert "## Current Mission — Context Only" in prompt
    assert "Original request: Build a clock." in prompt
    assert "single file" in prompt
    # No context / no key points → those sections are omitted entirely.
    assert "Key findings:" not in prompt


if __name__ == "__main__":
    # ponytail: self-check
    test_task_analyzer_renders_mission_block()
    test_task_assessor_renders_mission_block()
    test_task_executor_renders_mission_block()
    test_result_reviewer_renders_mission_block()
    test_result_aggregation_renders_mission_block()
    test_mission_block_empty_when_no_mission()
    print("ok")
