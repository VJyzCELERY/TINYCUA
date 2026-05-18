"""Shared fixtures for unit tests."""

import pytest
from unittest.mock import AsyncMock

from tests.conftest import FakeLLMResponse


def _httpx_compatible_registry():
    """Build a ProviderRegistry with OpenAICompatibleClient (httpx-based) as default.

    Tests that mock httpx.AsyncClient.post should use this instead of the
    default SDK-backed registry, because the httpx patch does not intercept
    the openai SDK's internal HTTP client.
    """
    from tinycua_sdk.agent.llm_client import OpenAICompatibleClient
    from tinycua_sdk.core.providers import OPENAI_RESPONSES, ProviderInfo, ProviderRegistry

    registry = ProviderRegistry()
    registry.register(
        OPENAI_RESPONSES,
        lambda cfg: OpenAICompatibleClient(cfg),
        ProviderInfo(id=OPENAI_RESPONSES, factory=lambda cfg: OpenAICompatibleClient(cfg), description="test"),
    )
    return registry


def _patch_registry(monkeypatch):
    """Replace get_provider_registry in executor and providers modules with httpx-compatible registry."""
    from tinycua_sdk.agent import executor as agent_executor
    from tinycua_sdk.core import providers as core_providers

    new_registry = _httpx_compatible_registry()
    monkeypatch.setattr(core_providers, "get_provider_registry", lambda: new_registry)
    monkeypatch.setattr(agent_executor, "get_provider_registry", lambda: new_registry)


@pytest.fixture
def default_llm():
    """Return a default LanguageModel instance."""
    from tinycua_sdk import LanguageModel

    return LanguageModel(
        provider="openai-responses",
        model_name="gpt-4o-mini",
        base_url="http://localhost:1234/v1",
    )


@pytest.fixture
def default_loop():
    """Return a default BaseLoop instance."""
    from tinycua_sdk import BaseLoop

    return BaseLoop(max_iterations=3)


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for tests — uses OpenAICompatibleClient (httpx-based) with patched post."""
    with (
        pytest.MonkeyPatch.context() as mp,
    ):
        _patch_registry(mp)

        fake_response_data = {
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": "Mocked response", "annotations": []}
                    ],
                }
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            },
        }
        fake_resp = FakeLLMResponse(json_data=fake_response_data)

        import httpx

        mock_post = AsyncMock(return_value=fake_resp)
        mp.setattr(httpx.AsyncClient, "post", mock_post)
        yield mock_post


@pytest.fixture
def mock_llm_with_tool_calls():
    """Mock LLM client that returns tool calls then a final response.

    .. warning::

       This fixture hardcodes the tool name ``"search"`` and arguments
       ``{"query": "quantum"}``.  Tests that use it **must** register a
       tool named ``search`` with a ``query: str`` parameter, or the
       tool lookup will silently fail with ``{"error": "Unknown tool:
       search"}``.
    """
    with (
        pytest.MonkeyPatch.context() as mp,
    ):
        _patch_registry(mp)

        first_response = FakeLLMResponse(
            json_data={
                "output": [
                    {
                        "type": "function_call",
                        "id": "call_1",
                        "name": "search",
                        "arguments": '{"query": "quantum"}',
                    }
                ],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 15,
                    "total_tokens": 25,
                },
            }
        )
        second_response = FakeLLMResponse(
            json_data={
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Quantum computing is fascinating.",
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 30,
                    "output_tokens": 5,
                    "total_tokens": 35,
                },
            }
        )

        import httpx

        _responses = [first_response, second_response]

        async def _mock_post(*args, **kwargs):
            if _responses:
                return _responses.pop(0)
            return FakeLLMResponse(
                json_data={
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "Fallback response.",
                                    "annotations": [],
                                }
                            ],
                        }
                    ],
                    "usage": None,
                }
            )

        mock_post = AsyncMock(side_effect=_mock_post)
        mp.setattr(httpx.AsyncClient, "post", mock_post)
        yield mock_post


@pytest.fixture
def mock_llm_with_failing_tool_call():
    """Mock LLM client that returns a tool call to a tool named ``'failing_tool'``

    (no arguments).  The tool call triggers the tool, which raises
    ``RuntimeError("Tool failed")`` — allowing tests to verify that tool
    exceptions propagate correctly through the execution loop.
    """
    with (
        pytest.MonkeyPatch.context() as mp,
    ):
        _patch_registry(mp)

        first_response = FakeLLMResponse(
            json_data={
                "output": [
                    {
                        "type": "function_call",
                        "id": "call_fail_1",
                        "name": "failing_tool",
                        "arguments": "{}",
                    }
                ],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 15,
                    "total_tokens": 25,
                },
            }
        )
        second_response = FakeLLMResponse(
            json_data={
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Recovered from error.",
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "usage": None,
            }
        )

        import httpx

        mock_post = AsyncMock(side_effect=[first_response, second_response])
        mp.setattr(httpx.AsyncClient, "post", mock_post)
        yield mock_post
