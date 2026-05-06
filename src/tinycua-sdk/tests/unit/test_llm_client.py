"""Tests for LLMClient and OpenAICompatibleClient."""

import httpx
import pytest
from unittest.mock import AsyncMock

from tinycua_sdk.agent.llm_client import LLMClient, OpenAICompatibleClient
from tinycua_sdk.agent.llm_model import LanguageModel


class TestLLMClientABC:
    """Test LLMClient is abstract."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            LLMClient()


class TestOpenAICompatibleClient:
    """Test OpenAICompatibleClient with mocked httpx."""

    @pytest.mark.asyncio
    async def test_chat_returns_normalized_response(self):
        client = OpenAICompatibleClient()

        fake_response_data = {
            "choices": [
                {
                    "message": {
                        "content": "Hello!",
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

        mock_post = AsyncMock()
        mock_post.return_value.status_code = 200

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return fake_response_data

        mock_post.return_value = FakeResponse()

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(httpx.AsyncClient, "post", mock_post)
            model = LanguageModel(model_name="gpt-4o-mini")
            result = await client.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=None,
                model_config=model,
            )

        assert result["content"] == "Hello!"
        assert result["tool_calls"] is None
        assert result["usage"] == {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }

    @pytest.mark.asyncio
    async def test_chat_with_tool_calls(self):
        client = OpenAICompatibleClient()

        fake_response_data = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"city": "Tokyo"}',
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25},
        }

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return fake_response_data

        mock_post = AsyncMock(return_value=FakeResponse())

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(httpx.AsyncClient, "post", mock_post)
            model = LanguageModel(model_name="gpt-4o-mini")
            result = await client.chat(
                messages=[{"role": "user", "content": "Weather?"}],
                tools=[{"type": "function", "function": {"name": "get_weather"}}],
                model_config=model,
            )

        assert result["content"] is None
        assert result["tool_calls"] is not None
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["id"] == "call_abc123"
        assert result["tool_calls"][0]["function"]["name"] == "get_weather"
        assert result["tool_calls"][0]["function"]["arguments"] == '{"city": "Tokyo"}'

    @pytest.mark.asyncio
    async def test_chat_sends_tool_choice_auto_when_tools_present(self):
        client = OpenAICompatibleClient()

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "choices": [{"message": {"content": "ok", "role": "assistant"}}],
                    "usage": None,
                }

        mock_post = AsyncMock(return_value=FakeResponse())
        captured_payload = {}

        async def capture_post(url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return FakeResponse()

        mock_post.side_effect = capture_post

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(httpx.AsyncClient, "post", mock_post)
            model = LanguageModel(model_name="gpt-4o-mini")
            await client.chat(
                messages=[],
                tools=[{"type": "function", "function": {"name": "test"}}],
                model_config=model,
            )

        assert captured_payload.get("tool_choice") == "auto"

    @pytest.mark.asyncio
    async def test_chat_forwards_model_config_fields(self):
        client = OpenAICompatibleClient()

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "choices": [{"message": {"content": "ok", "role": "assistant"}}],
                    "usage": None,
                }

        mock_post = AsyncMock(return_value=FakeResponse())
        captured_payload = {}

        async def capture_post(url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return FakeResponse()

        mock_post.side_effect = capture_post

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(httpx.AsyncClient, "post", mock_post)
            model = LanguageModel(
                model_name="gpt-4o-mini",
                temperature=0.5,
                max_tokens=100,
                top_p=0.9,
            )
            await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                model_config=model,
            )

        assert captured_payload["model"] == "gpt-4o-mini"
        assert captured_payload["temperature"] == 0.5
        assert captured_payload["max_tokens"] == 100
        assert captured_payload["top_p"] == 0.9

    @pytest.mark.asyncio
    async def test_chat_raises_on_http_error(self):
        client = OpenAICompatibleClient()

        class FakeErrorResponse:
            status_code = 401

            def raise_for_status(self):
                raise httpx.HTTPStatusError(
                    "401 Unauthorized", request=None, response=self
                )

            def json(self):
                return {"error": "unauthorized"}

        mock_post = AsyncMock(return_value=FakeErrorResponse())

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(httpx.AsyncClient, "post", mock_post)
            model = LanguageModel(model_name="gpt-4o-mini")

            with pytest.raises(httpx.HTTPStatusError):
                await client.chat(
                    messages=[{"role": "user", "content": "hi"}],
                    tools=None,
                    model_config=model,
                )

    @pytest.mark.asyncio
    async def test_chat_no_tool_calls_when_omitted(self):
        client = OpenAICompatibleClient()

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "No tools needed.",
                                "role": "assistant",
                            }
                        }
                    ],
                    "usage": None,
                }

        mock_post = AsyncMock(return_value=FakeResponse())

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(httpx.AsyncClient, "post", mock_post)
            model = LanguageModel(model_name="gpt-4o-mini")
            result = await client.chat(
                messages=[{"role": "user", "content": "Hello"}],
                tools=None,
                model_config=model,
            )

        assert result["tool_calls"] is None
        assert result["content"] == "No tools needed."

    def test_get_client_lazy_initialization(self):
        client = OpenAICompatibleClient()
        assert client._client is None

        model = LanguageModel(
            model_name="gpt-4o-mini",
            base_url="http://test.local/v1",
            api_key="test-key",
        )

        httpx_client = client._get_client(model)
        assert httpx_client is not None
        assert client._client is httpx_client
        assert str(httpx_client.base_url) == "http://test.local/v1/"
