"""Shared fixtures for unit tests."""

import pytest


@pytest.fixture
def default_llm():
    """Return a default LanguageModel instance."""
    from tinycua_sdk import LanguageModel

    return LanguageModel(
        provider="openai-compatible",
        model_name="gpt-4o-mini",
        base_url="http://localhost:1234/v1",
    )


@pytest.fixture
def default_loop():
    """Return a default BaseLoop instance."""
    from tinycua_sdk import BaseLoop

    return BaseLoop(max_iterations=3)
