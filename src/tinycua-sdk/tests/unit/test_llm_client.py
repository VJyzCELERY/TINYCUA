"""Tests for LLMClient and OpenAICompatibleClient."""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import FakeLLMResponse
from tinycua_sdk.agent.llm_client import LLMClient, OpenAICompatibleClient
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
            "type": "content.delta",
            "delta": "Hello",
            "index": 0,
        }
        assert chunks[1] == {
            "type": "content.delta",
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
            "type": "tool_call.arguments.delta",
            "id": "call_1",
            "arguments": '{"city": "Tokyo"}',
        }
        # ToolCallArgumentsDoneEvent now includes call_id and name fields
        assert chunks[1]["type"] == "tool_call.arguments.done"
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
        assert chunks[0]["type"] == "content.delta"
        assert chunks[0]["delta"] == "Hello"
        assert chunks[1]["type"] == "content.done"

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
        assert chunks[0]["type"] == "tool_call.arguments.done"
        assert chunks[0]["id"] == "item_1"
        assert chunks[1]["type"] == "tool_call.ready"
        assert chunks[1]["id"] == "item_1"
        assert chunks[1]["call_id"] == "call_1"
        assert chunks[1]["name"] == "get_weather"
        assert chunks[1]["arguments"] == "{}"

    # ── ISSUE-002: Payload translation ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_build_payload_translates_tool_result_messages(self, model: LanguageModel):
        """ToolResultMessage is translated to function_call_output in the payload."""
        from tinycua_sdk.agent.events import LLMToolSpec

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
        assert canonical["type"] == "content.delta"
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
        assert pairs[0][0]["type"] == "tool_call.arguments.done"
        assert pairs[0][1] is not None
        assert pairs[0][1]["provider"] == "openai-responses"
        # Second event (tool_call.ready) is synthetic → None
        assert pairs[1][0]["type"] == "tool_call.ready"
        assert pairs[1][1] is None
