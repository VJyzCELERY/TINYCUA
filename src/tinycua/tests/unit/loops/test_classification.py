"""Unit tests for ClassificationLoop."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tinycua.loops import ClassificationLoop


@pytest.fixture
def mock_llm_deterministic() -> AsyncMock:
    """Mock LLM that returns a predictable classification response."""

    async def _call_llm(
        messages: list[dict], tools: list, **kwargs: object
    ) -> dict:
        return {
            "content": (
                '{\n'
                '  "mode": "primary_agent",\n'
                '  "score": 0.85,\n'
                '  "confidence": 0.78,\n'
                '  "reasons": ["High complexity detected", "Sufficient context available"],\n'
                '  "enhanced_query": "Enhanced: What is the status of project X?"\n'
                '}'
            ),
            "tool_calls": None,
        }

    return AsyncMock(side_effect=_call_llm)


@pytest.fixture
def mock_agent(mock_llm_deterministic: AsyncMock) -> MagicMock:
    """Mock agent with deterministic LLM."""
    agent = MagicMock()
    agent.name = "test_agent"
    agent.instructions = "You are a classification agent."
    agent.skills = []
    agent.is_cancelled = False
    agent.policy.max_tool_calls = 100
    agent._call_llm = mock_llm_deterministic
    return agent


class TestClassificationLoop:
    """Test ClassificationLoop construction and run()."""

    def test_default_construction(self) -> None:
        """ClassificationLoop can be constructed with default params."""
        loop = ClassificationLoop()
        assert loop.max_iterations == 5
        assert loop.rubric_dimensions == ["complexity", "context_dependency"]
        assert loop.confidence_threshold == 0.7

    def test_custom_construction(self) -> None:
        """ClassificationLoop accepts custom rubric dimensions and threshold."""
        loop = ClassificationLoop(
            max_iterations=10,
            rubric_dimensions=["custom_dim"],
            confidence_threshold=0.5,
        )
        assert loop.max_iterations == 10
        assert loop.rubric_dimensions == ["custom_dim"]
        assert loop.confidence_threshold == 0.5

    @pytest.mark.asyncio
    async def test_run_returns_tuple(
        self, mock_agent: MagicMock,
    ) -> None:
        """run() returns (ContextEnhancedQuery, ModeDecision) tuple."""
        loop = ClassificationLoop()
        result = await loop.run(
            agent=mock_agent,
            messages=[],
            tools=[],
            user_query="What is the status of project X?",
            session_context="Project X involves data analysis.",
            chat_history=[],
        )
        enhanced_query, mode_decision = result

        assert enhanced_query.enhanced_query
        assert "Enhanced" in enhanced_query.enhanced_query

        assert mode_decision.mode == "primary_agent"
        assert 0.0 <= mode_decision.score <= 1.0
        assert mode_decision.score == 0.85
        assert 0.0 <= mode_decision.confidence <= 1.0
        assert isinstance(mode_decision.reasons, list)
        assert len(mode_decision.reasons) > 0

    @pytest.mark.asyncio
    async def test_empty_context(self, mock_agent: MagicMock) -> None:
        """ClassificationLoop handles empty session context gracefully."""
        loop = ClassificationLoop()
        result = await loop.run(
            agent=mock_agent,
            messages=[],
            tools=[],
            user_query="Hello",
            session_context="",
            chat_history=[],
        )
        enhanced_query, mode_decision = result
        assert mode_decision.mode in ("primary_agent", "worker", "uncertain")
        assert enhanced_query.enhanced_query

    @pytest.mark.asyncio
    async def test_stream_mode(self, mock_agent: MagicMock) -> None:
        """ClassificationLoop supports stream=True."""
        loop = ClassificationLoop()
        stream = loop.run(
            agent=mock_agent,
            messages=[],
            tools=[],
            stream=True,
            user_query="Test query",
            session_context="Test context",
            chat_history=[],
        )
        events = [event async for event in stream]
        assert len(events) > 0
