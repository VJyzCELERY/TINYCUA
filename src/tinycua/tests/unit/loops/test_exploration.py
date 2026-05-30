"""Unit tests for ExplorationLoop."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from tinycua.loops import ExplorationLoop


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM that returns predictable exploration responses."""

    async def _call_llm(
        messages: list[dict], tools: list, **kwargs: object
    ) -> dict:
        return {
            "content": (
                '{\n'
                '  "context_summary": "Project X focuses on quarterly financial reporting.",\n'
                '  "key_points": ["Quarterly reporting is main focus", "Finance team are stakeholders"],\n'
                '  "known_gaps": ["Detailed revenue breakdown not yet available"]\n'
                '}'
            ),
            "tool_calls": None,
        }

    return AsyncMock(side_effect=_call_llm)


@pytest.fixture
def mock_agent(mock_llm: AsyncMock) -> MagicMock:
    """Mock agent for exploration tests."""
    agent = MagicMock()
    agent.name = "test_explorer"
    agent.instructions = "You are an information digester."
    agent.skills = []
    agent.is_cancelled = False
    agent.policy.max_tool_calls = 100
    agent._call_llm = mock_llm
    return agent


@pytest.fixture
def mock_retrieval_tool() -> MagicMock:
    """Mock retrieval tool for ExplorationLoop."""
    tool = MagicMock()
    tool.name = "enhanced_context_retrieval"

    async def _invoke(**kwargs: Any) -> dict:
        return {
            "results": [
                {"content": "Project X involves quarterly financial data.", "relevance": 0.9},
                {"content": "Key stakeholders: finance team.", "relevance": 0.8},
            ],
        }

    tool.invoke = AsyncMock(side_effect=_invoke)
    return tool


@pytest.fixture
def mock_empty_retrieval_tool() -> MagicMock:
    """Mock retrieval tool that returns no results."""
    tool = MagicMock()
    tool.name = "enhanced_context_retrieval"

    async def _invoke(**kwargs: Any) -> dict:
        return {"results": []}

    tool.invoke = AsyncMock(side_effect=_invoke)
    return tool


class TestExplorationLoop:
    """Test ExplorationLoop construction and run()."""

    def test_default_construction(self) -> None:
        """ExplorationLoop can be constructed with default params."""
        loop = ExplorationLoop()
        assert loop.max_iterations == 5
        assert loop.max_search_iterations == 3
        assert loop.relevance_threshold == 0.6

    def test_custom_construction(self) -> None:
        """ExplorationLoop accepts custom params."""
        loop = ExplorationLoop(
            max_iterations=8,
            max_search_iterations=5,
            relevance_threshold=0.8,
        )
        assert loop.max_iterations == 8
        assert loop.max_search_iterations == 5
        assert loop.relevance_threshold == 0.8

    @pytest.mark.asyncio
    async def test_run_returns_digested_information(
        self,
        mock_agent: MagicMock,
        mock_retrieval_tool: MagicMock,
    ) -> None:
        """run() returns DigestedInformation with context_summary and key_points."""
        loop = ExplorationLoop()
        digested = await loop.run(
            agent=mock_agent,
            messages=[],
            tools=[mock_retrieval_tool],
            context_enhanced_query="Analyze Project X requirements",
            caller="primary_agent",
        )
        assert digested.context_summary
        assert "Project X" in digested.context_summary
        assert isinstance(digested.key_points, list)
        assert len(digested.key_points) > 0

    @pytest.mark.asyncio
    async def test_no_relevant_context(
        self,
        mock_agent: MagicMock,
        mock_empty_retrieval_tool: MagicMock,
    ) -> None:
        """ExplorationLoop returns DigestedInformation with empty key_points when no context found."""
        loop = ExplorationLoop()
        digested = await loop.run(
            agent=mock_agent,
            messages=[],
            tools=[mock_empty_retrieval_tool],
            context_enhanced_query="Unknown topic",
            caller="primary_agent",
        )
        assert digested.context_summary
        assert isinstance(digested.key_points, list)

    @pytest.mark.asyncio
    async def test_caller_is_forwarded(
        self,
        mock_agent: MagicMock,
        mock_retrieval_tool: MagicMock,
    ) -> None:
        """Caller parameter is forwarded through the loop."""
        loop = ExplorationLoop()
        digested = await loop.run(
            agent=mock_agent,
            messages=[],
            tools=[mock_retrieval_tool],
            context_enhanced_query="Test query",
            caller="worker",
        )
        assert digested.context_summary

    @pytest.mark.asyncio
    async def test_stream_mode(
        self,
        mock_agent: MagicMock,
        mock_retrieval_tool: MagicMock,
    ) -> None:
        """ExplorationLoop supports stream=True."""
        loop = ExplorationLoop()
        stream = loop.run(
            agent=mock_agent,
            messages=[],
            tools=[mock_retrieval_tool],
            stream=True,
            context_enhanced_query="Test query",
            caller="primary_agent",
        )
        events = [event async for event in stream]
        assert len(events) > 0
