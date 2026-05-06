"""Conftest for integration tests."""

import pytest
from unittest.mock import AsyncMock


def pytest_configure(config):
    """Configure integration tests."""
    config.addinivalue_line(
        "markers", "integration: marks tests as requiring local LLM server"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add skip logic for local LLM unavailable."""
    pass


def _make_fake_response(status_code=200, json_data=None):
    """Create a fake httpx.Response-like object."""
    class FakeResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json_data = json_data

        def raise_for_status(self):
            if self.status_code >= 400:
                import httpx
                raise httpx.HTTPStatusError(
                    f"HTTP {self.status_code}",
                    request=None,
                    response=self,
                )

        def json(self):
            return self._json_data

    return FakeResponse(status_code, json_data or {})


@pytest.fixture
def mock_llm_client():
    """Mock OpenAICompatibleClient for integration tests."""
    with (
        pytest.MonkeyPatch.context() as mp,
    ):
        fake_response_data = {
            "choices": [
                {
                    "message": {
                        "content": "Mocked response",
                        "role": "assistant",
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
        fake_resp = _make_fake_response(json_data=fake_response_data)

        import httpx
        mock_post = AsyncMock(return_value=fake_resp)
        mp.setattr(httpx.AsyncClient, "post", mock_post)
        yield mock_post


@pytest.fixture
def mock_llm_with_tool_calls():
    """Mock LLM client that returns tool calls then a final response.

    Note: This fixture hardcodes the tool name ``"search"`` and arguments
    ``{"query": "quantum"}``.  Tests that use it *must* register a tool
    with the same name and parameter shape for the tool call to resolve.
    """
    with (
        pytest.MonkeyPatch.context() as mp,
    ):
        first_response = _make_fake_response(json_data={
            "choices": [
                {
                    "message": {
                        "content": None,
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "search",
                                    "arguments": '{"query": "quantum"}',
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
        })
        second_response = _make_fake_response(json_data={
            "choices": [
                {
                    "message": {
                        "content": "Quantum computing is fascinating.",
                        "role": "assistant",
                    }
                }
            ],
            "usage": {"prompt_tokens": 30, "completion_tokens": 5, "total_tokens": 35},
        })

        import httpx
        mock_post = AsyncMock(side_effect=[first_response, second_response])
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
        first_response = _make_fake_response(json_data={
            "choices": [
                {
                    "message": {
                        "content": None,
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_fail_1",
                                "type": "function",
                                "function": {
                                    "name": "failing_tool",
                                    "arguments": "{}",
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
        })

        import httpx
        mock_post = AsyncMock(return_value=first_response)
        mp.setattr(httpx.AsyncClient, "post", mock_post)
        yield mock_post
