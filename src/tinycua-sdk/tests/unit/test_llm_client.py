"""Tests for LLMClient and OpenAICompatibleClient."""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import FakeLLMResponse
from tinycua_sdk.agent.llm_client import LLMClient, OpenAICompatibleClient, OpenAIResponsesClient
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.core.exceptions import ProviderApiError, ProviderAuthError


class TestLLMClientABC:
    """Test LLMClient is abstract."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            LLMClient()


class TestOpenAICompatibleClient:
    """Test OpenAICompatibleClient with mocked httpx."""

    @pytest.fixture
    def model(self) -> LanguageModel:
        return LanguageModel(model_name="gpt-4o-mini")

    @pytest.fixture
    def client(self, model: LanguageModel) -> OpenAICompatibleClient:
        return OpenAICompatibleClient(model)

    @pytest.mark.asyncio
    async def test_chat_returns_normalized_response(self, client: OpenAICompatibleClient):
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
            result = await client.chat(
                messages=[{"role": "user", "content": "Hi"}],
                tools=None,
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
    async def test_chat_with_tool_calls(self, client: OpenAICompatibleClient):
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
            result = await client.chat(
                messages=[{"role": "user", "content": "Weather?"}],
                tools=[{"type": "function", "name": "get_weather"}],
            )

        assert result["content"] is None
        assert result["tool_calls"] is not None
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["id"] == "call_abc123"
        assert result["tool_calls"][0]["name"] == "get_weather"
        assert result["tool_calls"][0]["arguments"] == '{"city": "Tokyo"}'
        assert mock_post.call_args[0][0] == "/responses"

    @pytest.mark.asyncio
    async def test_chat_sends_tool_choice_auto_when_tools_present(self, client: OpenAICompatibleClient):
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
            await client.chat(
                messages=[],
                tools=[{"type": "function", "name": "test"}],
            )

        assert captured_url == "/responses"
        assert captured_payload.get("tool_choice") == "auto"

    @pytest.mark.asyncio
    async def test_chat_forwards_model_config_fields(self, model: LanguageModel):
        client = OpenAICompatibleClient(model)

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
            await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
            )

        assert captured_url == "/responses"
        assert captured_payload["model"] == "gpt-4o-mini"
        assert captured_payload["temperature"] == 1.0
        assert "input" in captured_payload

    @pytest.mark.asyncio
    async def test_chat_raises_on_http_error(self, client: OpenAICompatibleClient):
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

            with pytest.raises(ProviderAuthError):
                await client.chat(
                    messages=[{"role": "user", "content": "hi"}],
                    tools=None,
                )

        assert mock_post.call_args[0][0] == "/responses"

    @pytest.mark.asyncio
    async def test_chat_no_tool_calls_when_omitted(self, client: OpenAICompatibleClient):
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
            result = await client.chat(
                messages=[{"role": "user", "content": "Hello"}],
                tools=None,
            )

        assert result["tool_calls"] is None
        assert result["content"] == "No tools needed."
        assert mock_post.call_args[0][0] == "/responses"

    @pytest.mark.asyncio
    async def test_chat_dispatches_to_chat_sync_when_stream_false(self, client: OpenAICompatibleClient):
        """chat(stream=False) returns a dict."""
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
            result = await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                stream=False,
            )

        assert isinstance(result, dict)
        assert result["content"] == "sync"
        assert mock_post.call_args[0][0] == "/responses"

    def _make_fake_stream_response(self, sse_lines, status_code=200):
        """Create a FakeStreamResponse that yields the given SSE lines."""

        async def fake_aiter_lines():
            for line in sse_lines:
                yield line

        class FakeStreamResponse:
            def __init__(self):
                self.status_code = status_code

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise httpx.HTTPStatusError(
                        f"{self.status_code} error", request=None, response=self
                    )

            def aiter_lines(self):
                return fake_aiter_lines()

        return FakeStreamResponse()

    @pytest.mark.asyncio
    async def test_chat_stream_returns_async_iterator_when_stream_true(self, model: LanguageModel):
        """chat(stream=True) returns an async iterator."""
        client = OpenAICompatibleClient(model)

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
            result = await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
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

        assert len(chunks) == 3
        assert chunks[0] == {
            "type": "response.output_text.delta",
            "delta": "Hello",
            "index": 0,
        }
        assert chunks[1] == {
            "type": "response.output_text.delta",
            "delta": " world",
            "index": 0,
        }
        assert chunks[2] == {
            "type": "response.completed",
            "finish_reason": "completed",
        }

    @pytest.mark.asyncio
    async def test_chat_stream_parses_function_call_arguments(self, model: LanguageModel):
        """SSE parsing yields normalized tool_call.arguments events."""
        client = OpenAICompatibleClient(model)

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
            result = await client.chat(
                messages=[{"role": "user", "content": "weather?"}],
                tools=[{"type": "function", "name": "get_weather"}],
                stream=True,
            )

            chunks = [c async for c in result]

        assert len(chunks) == 3
        assert chunks[0] == {
            "type": "response.function_call_arguments.delta",
            "id": "call_1",
            "arguments": '{"city": "Tokyo"}',
        }
        # ToolCallArgumentsDoneEvent now includes call_id and name fields
        assert chunks[1]["type"] == "response.function_call_arguments.done"
        assert chunks[1]["id"] == "call_1"
        assert chunks[1]["arguments"] == '{"city": "Tokyo"}'
        assert chunks[1]["name"] == "get_weather"
        # function_call_arguments.done also emits tool_call.ready
        assert chunks[2]["type"] == "tool_call.ready"
        assert chunks[2]["id"] == "call_1"
        assert chunks[2]["name"] == "get_weather"
        assert chunks[2]["arguments"] == '{"city": "Tokyo"}'

    @pytest.mark.asyncio
    async def test_chat_stream_skips_done_sentinel(self, model: LanguageModel):
        """[DONE] sentinel is skipped."""
        client = OpenAICompatibleClient(model)

        fake_sse_lines = [
            "data: [DONE]\n",
        ]

        fake_response = self._make_fake_stream_response(fake_sse_lines)

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(httpx.AsyncClient, "stream", MagicMock(return_value=fake_response))
            result = await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                stream=True,
            )

            chunks = [c async for c in result]

        assert len(chunks) == 0

    @pytest.mark.asyncio
    async def test_chat_stream_raises_on_http_error(self, model: LanguageModel):
        """HTTP error during streaming raises HTTPStatusError."""
        client = OpenAICompatibleClient(model)

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
            stream = await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                stream=True,
            )
            with pytest.raises(ProviderApiError):
                async for _ in stream:
                    pass

    @pytest.mark.asyncio
    async def test_chat_stream_emits_usage_event(self, model: LanguageModel):
        """SSE with usage event yields response.usage event."""
        client = OpenAICompatibleClient(model)

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
            result = await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                stream=True,
            )

            chunks = [c async for c in result]

        assert any(c["type"] == "response.usage" for c in chunks)
        usage = [c for c in chunks if c["type"] == "response.usage"][0]
        assert usage["usage"]["total_tokens"] == 8

    @pytest.mark.asyncio
    async def test_create_client(self, model: LanguageModel):
        # Use a model with explicit URL to test client key resolution
        explicit_model = LanguageModel(
            model_name="gpt-4o-mini",
            base_url="http://test.local/v1",
            api_key="test-key",
        )
        client = OpenAICompatibleClient(explicit_model)

        httpx_client = client._get_client()
        assert httpx_client is not None
        assert str(httpx_client.base_url) == "http://test.local/v1/"

        # Verify caching: same config returns same client
        httpx_client_2 = client._get_client()
        assert httpx_client_2 is httpx_client

        await client.close()

    # ── ISSUE-001: Content streaming normalization ──────────────────────────

    @pytest.mark.asyncio
    async def test_chat_stream_normalizes_output_text_delta(self, model: LanguageModel):
        """response.output_text.delta is normalized to content.delta."""
        client = OpenAICompatibleClient(model)

        fake_sse_lines = [
            'data: {"type":"response.output_text.delta","delta":"Hello","item_id":"1"}\n',
            'data: {"type":"response.output_text.done","item_id":"1"}\n',
            "data: [DONE]\n",
        ]

        fake_response = self._make_fake_stream_response(fake_sse_lines)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(httpx.AsyncClient, "stream", MagicMock(return_value=fake_response))
            result = await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                stream=True,
            )
            chunks = [c async for c in result]

        assert len(chunks) == 2
        assert chunks[0]["type"] == "response.output_text.delta"
        assert chunks[0]["delta"] == "Hello"
        assert chunks[1]["type"] == "response.output_text.done"

    @pytest.mark.asyncio
    async def test_chat_stream_emits_tool_call_ready(self, model: LanguageModel):
        """function_call_arguments.done emits both arguments.done and tool_call.ready."""
        client = OpenAICompatibleClient(model)

        fake_sse_lines = [
            'data: {"type":"response.function_call_arguments.done","item_id":"item_1","call_id":"call_1","name":"get_weather","arguments":"{}"}\n',
            "data: [DONE]\n",
        ]

        fake_response = self._make_fake_stream_response(fake_sse_lines)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(httpx.AsyncClient, "stream", MagicMock(return_value=fake_response))
            result = await client.chat(
                messages=[{"role": "user", "content": "weather?"}],
                tools=[{"type": "function", "name": "get_weather"}],
                stream=True,
            )
            chunks = [c async for c in result]

        assert len(chunks) == 2
        assert chunks[0]["type"] == "response.function_call_arguments.done"
        assert chunks[0]["id"] == "item_1"
        assert chunks[1]["type"] == "tool_call.ready"
        assert chunks[1]["id"] == "item_1"
        assert chunks[1]["call_id"] == "call_1"
        assert chunks[1]["name"] == "get_weather"
        assert chunks[1]["arguments"] == "{}"

    # ── ISSUE-004: Streaming auth error and cache-path tests ──────────────────

    @pytest.mark.asyncio
    async def test_chat_stream_raises_provider_auth_error_on_401(self, model: LanguageModel):
        """401 during streaming raises ProviderAuthError, not ProviderApiError."""
        client = OpenAICompatibleClient(model)

        fake_response = self._make_fake_stream_response([], status_code=401)

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(httpx.AsyncClient, "stream", MagicMock(return_value=fake_response))
            stream = await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                stream=True,
            )
            with pytest.raises(ProviderAuthError) as excinfo:
                async for _ in stream:
                    pass
        assert "Authentication failed" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_chat_stream_normalizer_cache_path(self, model: LanguageModel):
        """output_item.added supplies call_id/name; done event omits them → cache used."""
        client = OpenAICompatibleClient(model)

        # The output_item.added event caches item metadata.
        # The done event omits call_id/name — cache must supply them.
        fake_sse_lines = [
            'data: {"type":"response.output_item.added","item":{"id":"item_1","type":"function_call","call_id":"call_1","name":"get_weather"}}\n',
            'data: {"type":"response.function_call_arguments.done","item_id":"item_1","arguments":"{}"}\n',
            "data: [DONE]\n",
        ]

        fake_response = self._make_fake_stream_response(fake_sse_lines)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(httpx.AsyncClient, "stream", MagicMock(return_value=fake_response))
            result = await client.chat(
                messages=[{"role": "user", "content": "weather?"}],
                tools=[{"type": "function", "name": "get_weather"}],
                stream=True,
            )
            chunks = [c async for c in result]

        # output_item.added → tool_call.started
        assert chunks[0]["type"] == "response.output_item.added"
        assert chunks[0]["id"] == "item_1"
        assert chunks[0]["call_id"] == "call_1"

        # function_call_arguments.done → tool_call.arguments.done with cached metadata
        assert chunks[1]["type"] == "response.function_call_arguments.done"
        assert chunks[1]["id"] == "item_1"
        # call_id and name should come from cache since done event omitted them
        assert chunks[1].get("call_id") == "call_1", f"Expected call_id from cache, got: {chunks[1]}"
        assert chunks[1].get("name") == "get_weather", f"Expected name from cache, got: {chunks[1]}"

        # tool_call.ready also has cached metadata
        assert chunks[2]["type"] == "tool_call.ready"
        assert chunks[2]["call_id"] == "call_1"
        assert chunks[2]["name"] == "get_weather"

    # ── ISSUE-002: Payload translation ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_build_payload_translates_tool_result_messages(self, model: LanguageModel):
        """ToolResultMessage is translated to function_call_output in the payload."""

        payload = OpenAICompatibleClient._build_payload(
            [
                {"role": "user", "content": "hi"},
                {"role": "tool_result", "call_id": "call_1", "content": "42"},
            ],
            [{"name": "lookup", "description": "Lookup", "parameters": {"type": "object", "properties": {}}}],
            model,
        )

        # Tools get type="function" wrapper
        assert payload["tools"][0].get("type") == "function"
        assert payload["tools"][0]["name"] == "lookup"

        # tool_result messages become function_call_output
        assert any(
            item.get("type") == "function_call_output" and item.get("output") == "42"
            for item in payload["input"]
        ), payload["input"]

    @pytest.mark.asyncio
    async def test_build_payload_passes_through_regular_messages(self, model: LanguageModel):
        """System, user, and assistant messages pass through unchanged."""
        payload = OpenAICompatibleClient._build_payload(
            [
                {"role": "system", "content": "you are a bot"},
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
            ],
            None,
            model,
        )

        assert any(i["role"] == "system" for i in payload["input"])
        assert any(i["role"] == "user" for i in payload["input"])
        assert any(i["role"] == "assistant" for i in payload["input"])

    # ── ISSUE-003: Provider error wrappers ─────────────────────────────────

    @pytest.mark.asyncio
    async def test_chat_raises_provider_api_error_on_connection_failure(self, client: OpenAICompatibleClient):
        """httpx.RequestError is wrapped in ProviderApiError."""
        mock_post = AsyncMock(side_effect=httpx.RequestError("connection refused"))

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(httpx.AsyncClient, "post", mock_post)
            with pytest.raises(ProviderApiError) as excinfo:
                await client.chat(
                    messages=[{"role": "user", "content": "hi"}],
                    tools=None,
                )
        assert "Failed to connect" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_chat_raises_provider_api_error_on_server_error(self, client: OpenAICompatibleClient):
        """500 error is wrapped in ProviderApiError."""
        mock_post = AsyncMock(
            return_value=FakeLLMResponse(json_data={"error": "server error"}, status_code=500)
        )

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(httpx.AsyncClient, "post", mock_post)
            with pytest.raises(ProviderApiError) as excinfo:
                await client.chat(
                    messages=[{"role": "user", "content": "hi"}],
                    tools=None,
                )
        assert excinfo.value.status_code == 500

    # ── ISSUE-004: Raw events pass-through ─────────────────────────────────

    async def _make_raw_stream_response(self, sse_lines):
        """Create a FakeStreamResponse for raw event testing."""
        async def fake_aiter_lines():
            for line in sse_lines:
                yield line

        class FakeStreamResponse:
            def __init__(self):
                self.status_code = 200

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
    async def test_chat_stream_raw_events_yields_paired_tuples(self, model: LanguageModel):
        """raw_events=True yields (canonical_event, raw_event) tuples."""
        client = OpenAICompatibleClient(model)

        fake_sse_lines = [
            'data: {"type":"response.output_text.delta","delta":"Hi","item_id":"1"}\n',
            "data: [DONE]\n",
        ]

        fake_response = await self._make_raw_stream_response(fake_sse_lines)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(httpx.AsyncClient, "stream", MagicMock(return_value=fake_response))
            result = await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                stream=True,
                raw_events=True,
            )
            pairs = [pair async for pair in result]

        assert len(pairs) == 1
        canonical, raw = pairs[0]
        assert canonical["type"] == "response.output_text.delta"
        assert raw is not None
        assert raw["provider"] == "openai-responses"
        assert raw["raw_event"]["delta"] == "Hi"

    @pytest.mark.asyncio
    async def test_chat_stream_raw_events_synthetic_gets_none(self, model: LanguageModel):
        """Synthetic events (tool_call.ready) get None for raw slot."""
        client = OpenAICompatibleClient(model)

        fake_sse_lines = [
            'data: {"type":"response.function_call_arguments.done","item_id":"call_1","call_id":"call_1","name":"get_weather","arguments":"{}"}\n',
            "data: [DONE]\n",
        ]

        fake_response = await self._make_raw_stream_response(fake_sse_lines)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(httpx.AsyncClient, "stream", MagicMock(return_value=fake_response))
            result = await client.chat(
                messages=[{"role": "user", "content": "weather?"}],
                tools=[{"type": "function", "name": "get_weather"}],
                stream=True,
                raw_events=True,
            )
            pairs = [pair async for pair in result]

        assert len(pairs) == 2
        # First event (arguments.done) has raw data
        assert pairs[0][0]["type"] == "response.function_call_arguments.done"
        assert pairs[0][1] is not None
        assert pairs[0][1]["provider"] == "openai-responses"
        # Second event (tool_call.ready) is synthetic → None
        assert pairs[1][0]["type"] == "tool_call.ready"
        assert pairs[1][1] is None

    # ── ISSUE-001: Supported field forwarding ────────────────────────────────

    def test_build_payload_only_includes_responses_supported_fields(self):
        """_build_payload excludes unsupported Responses API fields even when set."""
        model = LanguageModel(
            temperature=0.7,
            max_tokens=100,
            top_p=0.9,
            frequency_penalty=0.5,
            presence_penalty=0.5,
            stop=["."],
            seed=42,
            logprobs=True,
            top_logprobs=3,
        )
        payload = OpenAICompatibleClient._build_payload(
            [{"role": "user", "content": "hi"}], None, model,
        )
        assert payload.get("temperature") == 0.7
        assert payload.get("max_output_tokens") == 100
        assert payload.get("top_p") == 0.9
        assert payload.get("top_logprobs") == 3
        assert "frequency_penalty" not in payload
        assert "presence_penalty" not in payload
        assert "stop" not in payload
        assert "seed" not in payload
        assert "logprobs" not in payload

    def test_build_request_kwargs_includes_top_logprobs(self):
        """OpenAIResponsesClient._build_request_kwargs includes top_logprobs."""
        model = LanguageModel(top_logprobs=2)
        client = OpenAIResponsesClient(model)
        kwargs = client._build_request_kwargs([{"role": "user", "content": "hi"}])
        assert kwargs.get("top_logprobs") == 2


class TestOpenAIResponsesClientSDK:
    """OpenAIResponsesClient tests with a mocked SDK ``responses.create()``.

    These tests inject a fake ``AsyncOpenAI`` client so that
    ``OpenAIResponsesClient`` never makes a real HTTP call.
    """

    @pytest.fixture
    def model(self) -> LanguageModel:
        return LanguageModel(model_name="gpt-4o-mini")

    @pytest.fixture
    def sdk_client(self, model: LanguageModel) -> OpenAIResponsesClient:
        client = OpenAIResponsesClient(model)
        # Pre-set a mock so _get_client() returns a mock instead of
        # constructing a real AsyncOpenAI.
        mock_async_openai = MagicMock()
        mock_async_openai.responses = MagicMock()
        client._client = mock_async_openai
        return client

    # ── Non-streaming ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_chat_non_streaming_calls_responses_create(self, sdk_client):
        """Non-streaming ``chat()`` calls ``responses.create()`` and normalizes."""
        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            "id": "resp_1",
            "model": "gpt-4o-mini",
            "status": "completed",
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "Hello!"}]},
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }
        sdk_client._client.responses.create = AsyncMock(return_value=mock_response)

        result = await sdk_client.chat(
            messages=[{"role": "user", "content": "hi"}],
        )

        assert result["content"] == "Hello!"
        assert result["usage"]["input_tokens"] == 10
        assert result["finish_reason"] == "stop"
        sdk_client._client.responses.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_chat_non_streaming_passes_model_and_input(self, sdk_client):
        """responses.create() receives model and input in kwargs."""
        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            "id": "resp_1",
            "model": "gpt-4o-mini",
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "Hi"}]}],
            "usage": {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
        }
        sdk_client._client.responses.create = AsyncMock(return_value=mock_response)

        await sdk_client.chat(
            messages=[{"role": "user", "content": "hello"}],
        )

        call_kwargs = sdk_client._client.responses.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert any(item["content"] == "hello" for item in call_kwargs["input"])

    # ── Streaming ────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_chat_streaming_calls_responses_create_with_stream(self, sdk_client):
        """``chat(stream=True)`` passes ``stream=True`` to ``responses.create()``."""

        class MockStreamEvent:
            def __init__(self, data: dict) -> None:
                self._data = data

            def model_dump(self) -> dict:
                return self._data

        async def mock_stream():
            # Note: response.created is dropped by _normalize_responses_event
            # (it is not in the recognised lifecycle set).
            yield MockStreamEvent({"type": "response.output_text.delta", "delta": "Hello", "item_id": "1"})
            yield MockStreamEvent({"type": "response.output_text.done", "item_id": "1"})
            yield MockStreamEvent({"type": "response.completed"})

        sdk_client._client.responses.create = AsyncMock(return_value=mock_stream())

        result = await sdk_client.chat(
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
        )
        events = [e async for e in result]

        assert len(events) == 3
        assert events[0]["type"] == "response.output_text.delta"
        assert events[1]["type"] == "response.output_text.done"
        assert events[2]["type"] == "response.completed"

    # ── Raw events ───────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_chat_stream_raw_events_yields_paired_tuples(self, sdk_client):
        """``raw_events=True`` yields ``(canonical, raw)`` tuples."""

        class MockStreamEvent:
            def __init__(self, data: dict) -> None:
                self._data = data

            def model_dump(self) -> dict:
                return self._data

        async def mock_stream():
            yield MockStreamEvent({"type": "response.output_text.delta", "delta": "Hi", "item_id": "1"})

        sdk_client._client.responses.create = AsyncMock(return_value=mock_stream())

        result = await sdk_client.chat(
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
            raw_events=True,
        )
        pairs = [pair async for pair in result]

        assert len(pairs) == 1
        canonical, raw = pairs[0]
        assert canonical["type"] == "response.output_text.delta"
        assert raw is not None
        assert raw["provider"] == "openai-responses"
        # Raw event in OpenAIResponsesClient is the SDK event object itself
        assert raw["raw_event"]._data["delta"] == "Hi"

    # ── Continuation ─────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_chat_continuation_sets_previous_response_id(self, sdk_client):
        """A tool_result message triggers ``previous_response_id`` in kwargs."""
        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            "id": "resp_prev",
            "model": "gpt-4o-mini",
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "First"}]}],
            "usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
        }
        sdk_client._client.responses.create = AsyncMock(return_value=mock_response)

        # First call to set previous_response_id
        await sdk_client.chat(messages=[{"role": "user", "content": "first call"}])

        # Second call with tool_result should include previous_response_id
        mock_response2 = MagicMock()
        mock_response2.model_dump.return_value = {
            "id": "resp_2",
            "model": "gpt-4o-mini",
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "Second"}]}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }
        sdk_client._client.responses.create = AsyncMock(return_value=mock_response2)

        await sdk_client.chat(
            messages=[
                {"role": "user", "content": "first call"},
                {"role": "tool_result", "call_id": "call_1", "content": "42"},
            ],
        )

        call_kwargs = sdk_client._client.responses.create.call_args[1]
        assert call_kwargs.get("previous_response_id") == "resp_prev"

    # ── Error mapping ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_chat_sync_401_raises_provider_auth_error(self, sdk_client):
        """401 status_code on ``responses.create()`` raises ``ProviderAuthError``."""

        class AuthException(Exception):
            pass

        exc = AuthException("invalid API key")
        exc.status_code = 401
        sdk_client._client.responses.create = AsyncMock(side_effect=exc)

        with pytest.raises(ProviderAuthError) as excinfo:
            await sdk_client.chat(
                messages=[{"role": "user", "content": "hi"}],
            )
        assert "invalid API key" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_chat_sync_403_raises_provider_auth_error(self, sdk_client):
        """403 status_code on ``responses.create()`` raises ``ProviderAuthError``."""

        class AuthException(Exception):
            pass

        exc = AuthException("forbidden")
        exc.status_code = 403
        sdk_client._client.responses.create = AsyncMock(side_effect=exc)

        with pytest.raises(ProviderAuthError) as excinfo:
            await sdk_client.chat(
                messages=[{"role": "user", "content": "hi"}],
            )
        assert "forbidden" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_chat_sync_500_raises_provider_api_error(self, sdk_client):
        """500 status_code on ``responses.create()`` raises ``ProviderApiError``."""

        class ServerException(Exception):
            pass

        exc = ServerException("server error")
        exc.status_code = 500
        sdk_client._client.responses.create = AsyncMock(side_effect=exc)

        with pytest.raises(ProviderApiError) as excinfo:
            await sdk_client.chat(
                messages=[{"role": "user", "content": "hi"}],
            )
        assert excinfo.value.status_code == 500

    @pytest.mark.asyncio
    async def test_chat_stream_401_raises_provider_auth_error(self, sdk_client):
        """401 during stream ``responses.create()`` raises ``ProviderAuthError``.

        Note: ``_chat_stream`` is an async generator, so the exception only
        propagates when the generator is iterated.
        """

        class AuthException(Exception):
            pass

        exc = AuthException("stream auth error")
        exc.status_code = 401
        sdk_client._client.responses.create = AsyncMock(side_effect=exc)

        result = await sdk_client.chat(
            messages=[{"role": "user", "content": "hi"}],
            stream=True,
        )
        with pytest.raises(ProviderAuthError) as excinfo:
            async for _ in result:
                pass
        assert "stream auth error" in str(excinfo.value)
