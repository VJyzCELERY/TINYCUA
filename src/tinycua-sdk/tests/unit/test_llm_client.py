"""Tests for LLMClient and OpenAIResponsesClient."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from tinycua_sdk.agent.llm_client import (
    LLMClient,
    OpenAIResponsesClient,
    _build_payload,
)
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.core.exceptions import ProviderApiError, ProviderAuthError


class TestLLMClientABC:
    """Test LLMClient is abstract."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            LLMClient()


class TestPayloadUtilities:
    """Tests for module-level payload utility functions.

    ``OpenAICompatibleClient`` has been removed; these utilities are now
    module-level functions (``_build_payload``, ``_translate_messages``,
    ``_translate_tools``).
    """

    def test_build_payload_translates_tool_result_messages(self):
        """ToolResultMessage is translated to function_call_output in the payload."""
        model = LanguageModel(model_name="gpt-4o-mini")

        payload = _build_payload(
            [
                {"role": "user", "content": "hi"},
                {"role": "tool_result", "call_id": "call_1", "content": "42"},
            ],
            [{"name": "lookup", "description": "Lookup", "parameters": {"type": "object", "properties": {}}}],
            model,
        )

        assert payload["tools"][0].get("type") == "function"
        assert payload["tools"][0]["name"] == "lookup"

        assert any(
            item.get("type") == "function_call_output" and item.get("output") == "42"
            for item in payload["input"]
        ), payload["input"]

    def test_build_payload_passes_through_regular_messages(self):
        """System, user, and assistant messages pass through unchanged."""
        model = LanguageModel(model_name="gpt-4o-mini")
        payload = _build_payload(
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
        payload = _build_payload(
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
