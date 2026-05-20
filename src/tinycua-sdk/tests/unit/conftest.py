"""Shared fixtures for unit tests.

.. note::
   ``OpenAICompatibleClient`` has been removed. All fixtures now mock
   ``OpenAIResponsesClient`` by patching ``_get_client`` to return a
   mock SDK client whose ``responses.create`` is an ``AsyncMock``.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


def _make_fake_sdk_response(json_data: dict):
    """Create a fake SDK response object with ``model_dump()``."""
    fake = MagicMock()
    fake.model_dump.return_value = json_data
    return fake


def _patch_sdk_client(monkeypatch):
    """Patch ``OpenAIResponsesClient._get_client`` to return a mock SDK client.

    Tests that use the registry (via ``AgentExecutor`` or ``BaseLoop``) will
    automatically create ``OpenAIResponsesClient`` instances whose
    ``_get_client()`` returns the shared mock, without making real HTTP calls.
    """
    from tinycua_sdk.providers.open_ai import OpenAIResponsesClient

    mock_sdk = MagicMock()
    mock_sdk.responses = MagicMock()

    def mock_get_client(self):
        return mock_sdk

    monkeypatch.setattr(OpenAIResponsesClient, "_get_client", mock_get_client)
    return mock_sdk


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
    """Mock LLM client using ``OpenAIResponsesClient`` with patched SDK.

    The returned ``AsyncMock`` is the ``responses.create`` mock — tests can
    inspect ``call_args``, ``call_count``, etc. to verify what was sent to
    the LLM.
    """
    from tinycua_sdk.providers.open_ai import OpenAIResponsesClient

    mock_sdk = MagicMock()
    mock_sdk.responses = MagicMock()

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
    fake_resp = _make_fake_sdk_response(fake_response_data)
    mock_create = AsyncMock(return_value=fake_resp)
    mock_sdk.responses.create = mock_create

    def mock_get_client(self):
        return mock_sdk

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(OpenAIResponsesClient, "_get_client", mock_get_client)
        yield mock_create


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
    from tinycua_sdk.providers.open_ai import OpenAIResponsesClient

    mock_sdk = MagicMock()
    mock_sdk.responses = MagicMock()

    first_response_data = {
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
    second_response_data = {
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

    _responses = [
        _make_fake_sdk_response(first_response_data),
        _make_fake_sdk_response(second_response_data),
    ]

    async def _mock_create(**kwargs):
        if _responses:
            return _responses.pop(0)
        return _make_fake_sdk_response({
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
        })

    mock_create = AsyncMock(side_effect=_mock_create)
    mock_sdk.responses.create = mock_create

    def mock_get_client(self):
        return mock_sdk

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(OpenAIResponsesClient, "_get_client", mock_get_client)
        yield mock_create


@pytest.fixture
def mock_llm_with_failing_tool_call():
    """Mock LLM client that returns a tool call to a tool named ``'failing_tool'``

    (no arguments).  The tool call triggers the tool, which raises
    ``RuntimeError("Tool failed")`` — allowing tests to verify that tool
    exceptions propagate correctly through the execution loop.
    """
    from tinycua_sdk.providers.open_ai import OpenAIResponsesClient

    mock_sdk = MagicMock()
    mock_sdk.responses = MagicMock()

    first_response_data = {
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
    second_response_data = {
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

    mock_create = AsyncMock(side_effect=[
        _make_fake_sdk_response(first_response_data),
        _make_fake_sdk_response(second_response_data),
    ])
    mock_sdk.responses.create = mock_create

    def mock_get_client(self):
        return mock_sdk

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(OpenAIResponsesClient, "_get_client", mock_get_client)
        yield mock_create
