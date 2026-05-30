"""Shared fixtures for loop unit tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock, AsyncMock

import pytest

from tinycua.state import ModeDecision, DigestedInformation, ReviewerDecision, ReviewStatus, ContextEnhancedQuery


@pytest.fixture
def mock_agent() -> MagicMock:
    """Create a mock Agent with minimal attributes."""
    agent = MagicMock()
    agent.name = "test_agent"
    agent.instructions = "You are a helpful test agent."
    agent.skills = []
    agent.is_cancelled = False
    agent.policy.max_tool_calls = 100
    return agent


@pytest.fixture
def mock_llm() -> AsyncMock:
    """Create a mock LLM callable."""

    async def _call_llm(messages: list[dict], tools: list, **kwargs: Any) -> dict:
        return {"content": "Mock LLM response", "tool_calls": None}

    llm = AsyncMock(side_effect=_call_llm)
    return llm


@pytest.fixture
def sample_session_context() -> str:
    """Sample session context for testing."""
    return "User is working on Project X which involves data analysis and reporting."


@pytest.fixture
def sample_chat_history() -> list[dict]:
    """Sample chat history for testing."""
    return [
        {"role": "user", "content": "Can you help me with data analysis?"},
        {"role": "assistant", "content": "Sure, I'd be happy to help with your data analysis project."},
    ]


@pytest.fixture
def sample_context_query() -> str:
    """Sample context-enhanced query string."""
    return "Based on the session context, analyze the requirements for Project X."


@pytest.fixture
def mock_tools() -> list[MagicMock]:
    """Create a list of mock tools."""
    tool1 = MagicMock()
    tool1.name = "search_context"
    tool1.description = "Search session context"

    tool2 = MagicMock()
    tool2.name = "analyze_data"
    tool2.description = "Analyze data"

    return [tool1, tool2]


@pytest.fixture
def mock_retrieval_tool() -> MagicMock:
    """Create a mock retrieval tool for ExplorationLoop."""
    tool = MagicMock()
    tool.name = "enhanced_context_retrieval"

    async def _invoke(**kwargs: Any) -> dict:
        return {
            "results": [
                {"content": "Project X involves quarterly financial reporting.", "relevance": 0.9},
                {"content": "Key stakeholders include the finance team.", "relevance": 0.8},
            ],
        }

    tool.invoke = AsyncMock(side_effect=_invoke)
    return tool


@pytest.fixture
def mock_task() -> dict:
    """Sample task as dict."""
    return {
        "task_id": "task-001",
        "description": "Analyze quarterly financial data",
        "status": "pending",
        "assigned_to": "worker",
    }


@pytest.fixture
def mock_failed_task_result() -> dict:
    """Sample failed task result as dict."""
    return {
        "task_id": "task-001",
        "status": "failed",
        "output": "Missing required field: revenue_data",
        "error": "Schema validation failed",
    }


@pytest.fixture
def mock_passed_task_result() -> dict:
    """Sample passed task result as dict."""
    return {
        "task_id": "task-001",
        "status": "completed",
        "output": "Analysis complete. Revenue growth of 15% QoQ.",
        "error": None,
    }


@pytest.fixture
def sample_mode_decision() -> ModeDecision:
    """Sample ModeDecision for testing."""
    return ModeDecision(
        mode="primary_agent",
        score=0.85,
        confidence=0.78,
        reasons=["High complexity detected", "Sufficient context available"],
    )


@pytest.fixture
def sample_enhanced_query() -> ContextEnhancedQuery:
    """Sample ContextEnhancedQuery for testing."""
    return ContextEnhancedQuery(
        enhanced_query="Based on Project X context, analyze the quarterly financial data.",
    )


@pytest.fixture
def sample_digested_information() -> DigestedInformation:
    """Sample DigestedInformation for testing."""
    return DigestedInformation(
        context_summary="Project X focuses on quarterly financial reporting for the finance team.",
        key_points=[
            "Quarterly financial reporting is the main focus",
            "Finance team are key stakeholders",
            "Revenue data is required for analysis",
        ],
        known_gaps=["Detailed revenue breakdown not yet available"],
    )
