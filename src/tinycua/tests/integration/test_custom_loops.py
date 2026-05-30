"""Integration tests for custom loop types (M2)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from tinycua.loops import (
    LoopType,
    ClassificationLoop,
    ExplorationLoop,
    LinearAgentLoop,
    HybridReviewLoop,
    CheckResult,
    create_loop,
)


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM that returns predictable responses."""

    async def _call_llm(
        messages: list[dict], tools: list, **kwargs: Any
    ) -> dict:
        return {"content": "Mock response for integration test", "tool_calls": None}

    return AsyncMock(side_effect=_call_llm)


@pytest.fixture
def mock_agent(mock_llm: AsyncMock) -> MagicMock:
    """Mock agent for integration tests."""
    agent = MagicMock()
    agent.name = "test_agent"
    agent.instructions = "You are a test agent."
    agent.skills = []
    agent.is_cancelled = False
    agent.policy.max_tool_calls = 100
    agent._call_llm = mock_llm
    return agent


@pytest.fixture
def sample_session_context() -> str:
    return "Project X involves quarterly financial reporting and data analysis."


@pytest.fixture
def sample_context_query() -> str:
    return "Based on the session context, analyze the requirements for Project X."


@pytest.fixture
def sample_chat_history() -> list[dict]:
    return [
        {"role": "user", "content": "Help me with Project X analysis."},
        {"role": "assistant", "content": "I can help with that."},
    ]


@pytest.fixture
def mock_task() -> dict:
    return {
        "task_id": "task-001",
        "description": "Analyze quarterly financial data",
        "status": "completed",
        "assigned_to": "worker",
    }


@pytest.fixture
def mock_failed_task_result() -> dict:
    return {
        "task_id": "task-001",
        "status": "failed",
        "output": "Missing required field: revenue_data",
        "error": "Schema validation failed",
    }


@pytest.fixture
def mock_tools() -> list[MagicMock]:
    tool = MagicMock()
    tool.name = "test_tool"
    tool.description = "A test tool"

    async def _invoke(**kwargs: Any) -> dict:
        return {"result": "Tool executed successfully"}

    tool.invoke = AsyncMock(side_effect=_invoke)
    return [tool]


@pytest.mark.integration
async def test_classification_loop_full_flow(
    mock_agent: MagicMock,
    mock_llm: AsyncMock,
    sample_session_context: str,
    sample_chat_history: list[dict],
) -> None:
    """ClassificationLoop produces valid ModeDecision + ContextEnhancedQuery."""
    loop = ClassificationLoop(rubric_dimensions=["complexity", "context_dependency"])
    result = await loop.run(
        agent=mock_agent,
        messages=[],
        tools=[],
        user_query="What is the status of project X?",
        session_context=sample_session_context,
        chat_history=sample_chat_history,
    )
    enhanced_query, mode_decision = result
    assert enhanced_query.enhanced_query
    assert mode_decision.mode in ("primary_agent", "worker", "uncertain")
    assert 0.0 <= mode_decision.score <= 1.0
    assert isinstance(mode_decision.reasons, list)
    assert len(mode_decision.reasons) > 0


@pytest.mark.integration
async def test_exploration_loop_full_flow(
    mock_agent: MagicMock,
    mock_llm: AsyncMock,
    sample_context_query: str,
) -> None:
    """ExplorationLoop produces DigestedInformation."""
    from unittest.mock import AsyncMock, MagicMock

    retrieval_tool = MagicMock()
    retrieval_tool.name = "enhanced_context_retrieval"

    async def _retrieve(**kwargs: Any) -> dict:
        return {
            "results": [
                {"content": "Relevant context data", "relevance": 0.9},
            ],
        }

    retrieval_tool.invoke = AsyncMock(side_effect=_retrieve)

    loop = ExplorationLoop()
    digested = await loop.run(
        agent=mock_agent,
        messages=[],
        tools=[retrieval_tool],
        context_enhanced_query=sample_context_query,
        caller="primary_agent",
    )
    assert digested.context_summary
    assert isinstance(digested.key_points, list)


@pytest.mark.integration
async def test_linear_agent_loop_react_flow(
    mock_agent: MagicMock,
    mock_llm: AsyncMock,
    mock_tools: list[MagicMock],
) -> None:
    """LinearAgentLoop executes ReAct iterations and returns output."""
    loop = LinearAgentLoop(max_iterations=5)
    output = await loop.run(
        agent=mock_agent,
        messages=[],
        tools=mock_tools,
        input_data={"query": "Analyze the requirements"},
    )
    assert isinstance(output, str)
    assert len(output) > 0


@pytest.mark.integration
async def test_hybrid_review_deterministic_short_circuit(
    mock_agent: MagicMock,
    mock_llm: AsyncMock,
    mock_task: dict,
    mock_failed_task_result: dict,
) -> None:
    """HybridReviewLoop short-circuits on deterministic failure without LLM call."""
    import copy

    def failing_check(task: dict, task_result: dict) -> CheckResult | None:
        return CheckResult(
            check_name="schema_validdity",
            passed=False,
            reason="Missing required field",
            decision_override="retry",
        )

    loop = HybridReviewLoop(deterministic_checks=[failing_check])
    decision = await loop.run(
        agent=mock_agent,
        messages=[],
        tools=[],
        task=mock_task,
        task_result=mock_failed_task_result,
    )
    assert decision.status in ("retry", "escalate_user")
    assert decision.reason

    # LLM should NOT have been called since deterministic check failed
    mock_llm.assert_not_called()


@pytest.mark.integration
async def test_create_loop_factory() -> None:
    """create_loop() instantiates the correct subclass for each LoopType."""
    loop = create_loop(LoopType.CLASSIFICATION)
    assert isinstance(loop, ClassificationLoop)

    loop = create_loop(LoopType.EXPLORATION)
    assert isinstance(loop, ExplorationLoop)

    loop = create_loop(LoopType.LINEAR_AGENT)
    assert isinstance(loop, LinearAgentLoop)

    loop = create_loop(LoopType.HYBRID_REVIEW)
    assert isinstance(loop, HybridReviewLoop)

    with pytest.raises(ValueError, match="Unknown loop type"):
        create_loop("invalid_type")  # type: ignore[arg-type]


@pytest.mark.integration
async def test_all_loops_support_streaming(
    mock_agent: MagicMock,
    mock_llm: AsyncMock,
) -> None:
    """All loop types support stream=True, yielding SSE events."""

    # Each loop has different required kwargs for run()
    test_cases: list[tuple[type, dict[str, Any]]] = [
        (ClassificationLoop, {
            "user_query": "hello",
            "session_context": "",
            "chat_history": [],
        }),
        (ExplorationLoop, {
            "context_enhanced_query": "test",
            "caller": "primary_agent",
        }),
        (LinearAgentLoop, {
            "input_data": "test",
        }),
        (HybridReviewLoop, {
            "task": {},
            "task_result": {},
            "execution_log": None,
        }),
    ]

    for loop_cls, kwargs in test_cases:
        loop = loop_cls()
        stream = loop.run(
            agent=mock_agent,
            messages=[],
            tools=[],
            stream=True,
            **kwargs,
        )
        events = [event async for event in stream]
        assert len(events) > 0, f"{loop_cls.__name__} produced no stream events"
