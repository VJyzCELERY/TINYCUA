"""Unit tests for LinearAgentLoop."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from tinycua.loops import LinearAgentLoop


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Mock LLM that returns predictable responses."""

    async def _call_llm(
        messages: list[dict], tools: list, **kwargs: object
    ) -> dict:
        # Return a simple text response (no tool calls)
        return {
            "content": "Analysis complete. The requirements are clear.",
            "tool_calls": None,
        }

    return AsyncMock(side_effect=_call_llm)


@pytest.fixture
def mock_agent(mock_llm: AsyncMock) -> MagicMock:
    """Mock agent for linear agent tests."""
    agent = MagicMock()
    agent.name = "test_linear_agent"
    agent.instructions = "You are a linear agent."
    agent.skills = []
    agent.is_cancelled = False
    agent.policy.max_tool_calls = 100
    agent._call_llm = mock_llm
    return agent


class TestLinearAgentLoop:
    """Test LinearAgentLoop construction and run()."""

    def test_default_construction(self) -> None:
        """LinearAgentLoop can be constructed with default params."""
        loop = LinearAgentLoop()
        assert loop.max_iterations == 5
        assert loop.system_prompt_template == ""

    def test_custom_construction(self) -> None:
        """LinearAgentLoop accepts custom params."""
        loop = LinearAgentLoop(
            max_iterations=10,
            system_prompt_template="You are a task analyzer.",
            shallow_task_list=[{"id": "1", "name": "Task 1"}],
        )
        assert loop.max_iterations == 10
        assert loop.system_prompt_template == "You are a task analyzer."
        assert loop.shallow_task_list == [{"id": "1", "name": "Task 1"}]

    @pytest.mark.asyncio
    async def test_run_returns_string(
        self,
        mock_agent: MagicMock,
    ) -> None:
        """run() returns a string output."""
        loop = LinearAgentLoop()
        output = await loop.run(
            agent=mock_agent,
            messages=[],
            tools=[],
            input_data={"query": "Analyze requirements"},
        )
        assert isinstance(output, str)
        assert len(output) > 0

    @pytest.mark.asyncio
    async def test_run_with_tools(
        self,
        mock_agent: MagicMock,
    ) -> None:
        """run() works with tools list."""
        tool = MagicMock()
        tool.name = "test_tool"
        loop = LinearAgentLoop()
        output = await loop.run(
            agent=mock_agent,
            messages=[],
            tools=[tool],
            input_data="Test input",
        )
        assert isinstance(output, str)

    @pytest.mark.asyncio
    async def test_run_with_string_input(
        self,
        mock_agent: MagicMock,
    ) -> None:
        """run() accepts string input_data."""
        loop = LinearAgentLoop()
        output = await loop.run(
            agent=mock_agent,
            messages=[],
            tools=[],
            input_data="Direct string input",
        )
        assert isinstance(output, str)

    @pytest.mark.asyncio
    async def test_stream_mode(
        self,
        mock_agent: MagicMock,
    ) -> None:
        """LinearAgentLoop supports stream=True."""
        loop = LinearAgentLoop()
        stream = loop.run(
            agent=mock_agent,
            messages=[],
            tools=[],
            stream=True,
            input_data="Test",
        )
        events = [event async for event in stream]
        assert len(events) > 0
