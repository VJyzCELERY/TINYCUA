"""Shared fixtures for unit tests."""

import pytest


@pytest.fixture
def default_llm():
    """Return a default LLMModel instance."""
    from tinycua_sdk import LLMModel

    return LLMModel(
        provider="openai-compatible",
        model_name="gpt-4o-mini",
        base_url="http://localhost:1234/v1",
    )


@pytest.fixture
def default_loop():
    """Return a default BaseLoop instance."""
    from tinycua_sdk import BaseLoop

    return BaseLoop(max_iterations=3)


@pytest.fixture
def mock_llm_response():
    """Return a mock LLM response string."""
    return "Mocked LLM response"
