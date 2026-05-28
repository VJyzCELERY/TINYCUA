"""Tests for LLMClient and OpenAICompatibleClient."""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import FakeLLMResponse
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
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": "Hello!", "annotations": []}
                    ],
                }
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            },
        }

        mock_post = AsyncMock()
        mock_post.return_value = FakeLLMResponse(json_data=fake_response_data)

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
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        }
        assert mock_post.call_args[0][0] == "/responses"

    @pytest.mark.asyncio
    async def test_chat_with_tool_calls(self):
        client = OpenAICompatibleClient()

        fake_response_data = {
            "output": [
                {
                    "type": "function_call",
                    "id": "call_abc123",
                    "name": "get_weather",
                    "arguments": '{"city": "Tokyo"}',
                }
            ],
            "usage": {"input_tokens": 15, "output_tokens": 10, "total_tokens": 25},
        }

        mock_post = AsyncMock(
            return_value=FakeLLMResponse(json_data=fake_response_data)
        )

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(httpx.AsyncClient, "post", mock_post)
            model = LanguageModel(model_name="gpt-4o-mini")
            result = await client.chat(
                messages=[{"role": "user", "content": "Weather?"}],
                tools=[{"type": "function", "name": "get_weather"}],
                model_config=model,
            )

        assert result["content"] is None
        assert result["tool_calls"] is not None
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["id"] == "call_abc123"
        assert result["tool_calls"][0]["name"] == "get_weather"
        assert result["tool_calls"][0]["arguments"] == '{"city": "Tokyo"}'
        assert mock_post.call_args[0][0] == "/responses"

    @pytest.mark.asyncio
    async def test_chat_sends_tool_choice_auto_when_tools_present(self):
        client = OpenAICompatibleClient()

        fake_response = FakeLLMResponse(
            json_data={
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "ok", "annotations": []}],
                    }
                ],
                "usage": None,
            }
        )
        mock_post = AsyncMock(return_value=fake_response)
        captured_payload = {}
        captured_url = None

        async def capture_post(url, **kwargs):
            nonlocal captured_url
            captured_url = url
            captured_payload.update(kwargs.get("json", {}))
            return FakeLLMResponse(
                json_data={
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "ok", "annotations": []}],
                        }
                    ],
                    "usage": None,
                }
            )

        mock_post.side_effect = capture_post

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(httpx.AsyncClient, "post", mock_post)
            model = LanguageModel(model_name="gpt-4o-mini")
            await client.chat(
                messages=[],
                tools=[{"type": "function", "name": "test"}],
                model_config=model,
            )

        assert captured_url == "/responses"
        assert captured_payload.get("tool_choice") == "auto"

    @pytest.mark.asyncio
    async def test_chat_forwards_model_config_fields(self):
        client = OpenAICompatibleClient()

        fake_ok = FakeLLMResponse(
            json_data={
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "ok", "annotations": []}],
                    }
                ],
                "usage": None,
            }
        )
        mock_post = AsyncMock(return_value=fake_ok)
        captured_payload = {}
        captured_url = None

        async def capture_post(url, **kwargs):
            nonlocal captured_url
            captured_url = url
            captured_payload.update(kwargs.get("json", {}))
            return fake_ok

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
                user="test-user",
            )
            await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                model_config=model,
            )

        assert captured_url == "/responses"
        assert captured_payload["model"] == "gpt-4o-mini"
        assert captured_payload["temperature"] == 0.5
        assert captured_payload["max_output_tokens"] == 100
        assert captured_payload["top_p"] == 0.9
        assert captured_payload["user"] == "test-user"

    @pytest.mark.asyncio
    async def test_chat_raises_on_http_error(self):
        client = OpenAICompatibleClient()

        mock_post = AsyncMock(
            return_value=FakeLLMResponse(
                json_data={"error": "unauthorized"},
                status_code=401,
            )
        )

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

        assert mock_post.call_args[0][0] == "/responses"

    @pytest.mark.asyncio
    async def test_chat_no_tool_calls_when_omitted(self):
        client = OpenAICompatibleClient()

        mock_post = AsyncMock(
            return_value=FakeLLMResponse(
                json_data={
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "No tools needed.",
                                    "annotations": [],
                                }
                            ],
                        }
                    ],
                    "usage": None,
                }
            )
        )

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
        assert mock_post.call_args[0][0] == "/responses"

    @pytest.mark.asyncio
    async def test_chat_dispatches_to_chat_sync_when_stream_false(self):
        """chat(stream=False) calls _chat_sync and returns a dict."""
        client = OpenAICompatibleClient()
        fake_data = {
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": "sync", "annotations": []}
                    ],
                }
            ],
            "usage": None,
        }
        mock_post = AsyncMock(return_value=FakeLLMResponse(json_data=fake_data))

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(httpx.AsyncClient, "post", mock_post)
            model = LanguageModel(model_name="gpt-4o-mini")
            result = await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                model_config=model,
                stream=False,
            )

        assert isinstance(result, dict)
        assert result["content"] == "sync"
        assert mock_post.call_args[0][0] == "/responses"

    def _make_fake_stream_response(self, sse_lines):
        """Create a FakeStreamResponse that yields the given SSE lines."""

        async def fake_aiter_lines():
            for line in sse_lines:
                yield line

        class FakeStreamResponse:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def raise_for_status(self):
                pass

            def aiter_lines(self):
                return fake_aiter_lines()

        return FakeStreamResponse()

    @pytest.mark.asyncio
    async def test_chat_stream_returns_async_iterator_when_stream_true(self):
        """chat(stream=True) returns an async iterator."""
        client = OpenAICompatibleClient()

        fake_sse_lines = [
            'data: {"type":"response.output_text.delta","delta":"Hello","item_id":"1"}\n',
            'data: {"type":"response.output_text.delta","delta":" world","item_id":"2"}\n',
            'data: {"type":"response.completed","finish_reason":"completed"}\n',
            "data: [DONE]\n",
        ]

        fake_response = self._make_fake_stream_response(fake_sse_lines)

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mock_stream = MagicMock(return_value=fake_response)
            mp.setattr(httpx.AsyncClient, "stream", mock_stream)
            model = LanguageModel(
                base_url="http://test.local/v1", model_name="gpt-4o-mini"
            )
            result = await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                model_config=model,
                stream=True,
            )

            chunks = [c async for c in result]

        mock_stream.assert_called_once()
        args, kwargs = mock_stream.call_args
        assert args[0] == "POST"
        assert args[1] == "/responses"
        assert kwargs["json"]["stream"] is True
        assert kwargs["json"]["model"] == "gpt-4o-mini"
        assert "input" in kwargs["json"]
        assert "stream_options" not in kwargs["json"]

        assert len(chunks) == 3
        assert chunks[0] == {
            "type": "response.output_text.delta",
            "delta": "Hello",
            "item_id": "1",
        }
        assert chunks[1] == {
            "type": "response.output_text.delta",
            "delta": " world",
            "item_id": "2",
        }
        assert chunks[2] == {
            "type": "response.completed",
            "finish_reason": "completed",
        }

    @pytest.mark.asyncio
    async def test_chat_stream_parses_function_call_arguments(self):
        """SSE parsing yields function_call_arguments.delta/.done events."""
        client = OpenAICompatibleClient()

        fake_sse_lines = [
            'data: {"type":"response.function_call_arguments.delta","item_id":"call_1","delta":"{\\"city\\": \\"Tokyo\\"}"}\n',
            'data: {"type":"response.function_call_arguments.done","item_id":"call_1","name":"get_weather","arguments":"{\\"city\\": \\"Tokyo\\"}"}\n',
            "data: [DONE]\n",
        ]

        fake_response = self._make_fake_stream_response(fake_sse_lines)

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(httpx.AsyncClient, "stream", MagicMock(return_value=fake_response))
            model = LanguageModel(
                base_url="http://test.local/v1", model_name="gpt-4o-mini"
            )
            result = await client.chat(
                messages=[{"role": "user", "content": "weather?"}],
                tools=[{"type": "function", "name": "get_weather"}],
                model_config=model,
                stream=True,
            )

            chunks = [c async for c in result]

        assert len(chunks) == 2
        assert chunks[0] == {
            "type": "response.function_call_arguments.delta",
            "item_id": "call_1",
            "delta": '{"city": "Tokyo"}',
        }
        assert chunks[1] == {
            "type": "response.function_call_arguments.done",
            "item_id": "call_1",
            "name": "get_weather",
            "arguments": '{"city": "Tokyo"}',
        }

    @pytest.mark.asyncio
    async def test_chat_stream_skips_done_sentinel(self):
        """[DONE] sentinel is skipped."""
        client = OpenAICompatibleClient()

        fake_sse_lines = [
            "data: [DONE]\n",
        ]

        fake_response = self._make_fake_stream_response(fake_sse_lines)

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(httpx.AsyncClient, "stream", MagicMock(return_value=fake_response))
            model = LanguageModel(
                base_url="http://test.local/v1", model_name="gpt-4o-mini"
            )
            result = await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                model_config=model,
                stream=True,
            )

            chunks = [c async for c in result]

        assert len(chunks) == 0

    @pytest.mark.asyncio
    async def test_chat_stream_raises_on_http_error(self):
        """HTTP error during streaming raises HTTPStatusError."""
        client = OpenAICompatibleClient()

        fake_response = self._make_fake_stream_response([])
        fake_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "401 Unauthorized", request=None, response=MagicMock()
            )
        )

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(httpx.AsyncClient, "stream", MagicMock(return_value=fake_response))
            model = LanguageModel(
                base_url="http://test.local/v1", model_name="gpt-4o-mini"
            )
            stream = await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                model_config=model,
                stream=True,
            )
            with pytest.raises(httpx.HTTPStatusError):
                async for _ in stream:
                    pass

    @pytest.mark.asyncio
    async def test_chat_stream_emits_usage_event(self):
        """SSE with usage event yields response.usage event."""
        client = OpenAICompatibleClient()

        fake_sse_lines = [
            'data: {"type":"response.output_text.delta","delta":"Hello","item_id":"1"}\n',
            'data: {"type":"response.usage","usage":{"input_tokens":5,"output_tokens":3,"total_tokens":8}}\n',
            "data: [DONE]\n",
        ]

        fake_response = self._make_fake_stream_response(fake_sse_lines)

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(httpx.AsyncClient, "stream", MagicMock(return_value=fake_response))
            model = LanguageModel(
                base_url="http://test.local/v1", model_name="gpt-4o-mini"
            )
            result = await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                model_config=model,
                stream=True,
            )

            chunks = [c async for c in result]

        assert any(c["type"] == "response.usage" for c in chunks)
        usage = [c for c in chunks if c["type"] == "response.usage"][0]
        assert usage["usage"]["total_tokens"] == 8

    @pytest.mark.asyncio
    async def test_create_client(self):
        client = OpenAICompatibleClient()

        model = LanguageModel(
            model_name="gpt-4o-mini",
            base_url="http://test.local/v1",
            api_key="test-key",
        )

        httpx_client = client._get_client(model)
        assert httpx_client is not None
        assert str(httpx_client.base_url) == "http://test.local/v1/"

        # Verify caching: same config returns same client
        httpx_client_2 = client._get_client(model)
        assert httpx_client_2 is httpx_client

        await client.close()
