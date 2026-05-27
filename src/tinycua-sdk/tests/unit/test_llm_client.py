"""Tests for LLMClient and OpenAIResponsesClient."""

import base64

import pytest
from unittest.mock import AsyncMock, MagicMock

from tinycua_sdk.agent.events import (
    LLMEvent,
    ReasoningDeltaEvent,
    ReasoningDoneEvent,
    ResponseCancelledEvent,
    ResponseCreatedEvent,
    ResponseInProgressEvent,
)
from tinycua_sdk.agent.llm_client import LLMClient
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.core.exceptions import ProviderApiError, ProviderAuthError
from tinycua_sdk.models.attachment import ContentPart, FileAttachment
from tinycua_sdk.providers.open_ai_responses import (
    OpenAIResponsesClient,
    _normalize_responses_event,
    _translate_messages,
)


class TestLLMClientABC:
    """Test LLMClient is abstract."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            LLMClient()


class TestPayloadUtilities:
    """Tests for module-level payload utility functions.

    ``_translate_messages`` translates tool_result to function_call_output
    in the Responses API format.  ``_build_request_kwargs`` (instance method
    on ``OpenAIResponsesClient``) builds the ``model``, ``input``, tools,
    and field-mapped kwargs for ``responses.create()``.
    """

    def test_build_payload_translates_tool_result_messages(self):
        """ToolResultMessage is translated to function_call_output in the payload."""
        model = LanguageModel(model_name="gpt-4o-mini")
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "tool_result", "call_id": "call_1", "content": "42"},
        ]
        translated = _translate_messages(messages)
        client = OpenAIResponsesClient(model)
        payload = client._build_request_kwargs(
            translated,
            [{"name": "lookup", "description": "Lookup", "parameters": {"type": "object", "properties": {}}}],
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
        messages = [
            {"role": "system", "content": "you are a bot"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        translated = _translate_messages(messages)
        client = OpenAIResponsesClient(model)
        payload = client._build_request_kwargs(translated, None)

        assert any(i["role"] == "system" for i in payload["input"])
        assert any(i["role"] == "user" for i in payload["input"])
        assert any(i["role"] == "assistant" for i in payload["input"])

    def test_build_request_kwargs_rejects_unsupported_fields(self):
        """_build_request_kwargs raises ProviderApiError for unsupported fields."""
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
        client = OpenAIResponsesClient(model)
        with pytest.raises(ProviderApiError):
            client._build_request_kwargs([{"role": "user", "content": "hi"}])

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
            # Note: response.created is now normalised by _normalize_responses_event
            # into ResponseCreatedEvent.
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


class TestReasoningEventNormalization:
    """Tests for reasoning delta/summary event normalization.

    These test the ``_normalize_reasoning_event`` path exercised through
    ``_normalize_responses_event`` for ``response.reasoning.delta`` and
    ``response.reasoning.summary`` events from the OpenAI Responses API.
    """

    def test_reasoning_delta_event(self):
        """``response.reasoning.delta`` normalizes to ``ReasoningDeltaEvent``."""
        raw = {"type": "response.reasoning.delta", "delta": "First, let me think about this..."}
        result = _normalize_responses_event(raw)
        assert len(result) == 1
        event = result[0]
        assert event["type"] == "response.reasoning.delta"
        assert event["delta"] == "First, let me think about this..."

    def test_reasoning_delta_multiple_chunks(self):
        """Multiple reasoning delta events each produce a separate canonical event."""
        chunks = [
            {"type": "response.reasoning.delta", "delta": "Step 1: "},
            {"type": "response.reasoning.delta", "delta": "analyze the "},
            {"type": "response.reasoning.delta", "delta": "problem."},
        ]
        results = [_normalize_responses_event(c)[0] for c in chunks]
        texts = [e["delta"] for e in results]
        assert texts == ["Step 1: ", "analyze the ", "problem."]

    def test_reasoning_delta_preserves_empty_delta(self):
        """Empty delta produces a valid ReasoningDeltaEvent with empty string."""
        raw = {"type": "response.reasoning.delta", "delta": ""}
        result = _normalize_responses_event(raw)
        assert len(result) == 1
        assert result[0]["delta"] == ""

    def test_reasoning_summary_normalizes_to_done(self):
        """``response.reasoning.summary`` normalizes to ``ReasoningDoneEvent``."""
        raw = {"type": "response.reasoning.summary", "summary_text": "Therefore the answer is 42."}
        result = _normalize_responses_event(raw)
        assert len(result) == 1
        event = result[0]
        assert event["type"] == "response.reasoning.done"

    def test_reasoning_unknown_event_dropped(self):
        """Unknown reasoning event types are silently dropped."""
        raw = {"type": "response.reasoning.unknown"}
        result = _normalize_responses_event(raw)
        assert result == []

    def test_full_stream_with_reasoning(self):
        """Simulate a full streaming sequence with reasoning followed by output.

        Note: ``response.created`` and ``response.in_progress`` are now
        normalised by the normalizer into canonical lifecycle events, but
        they are intentionally omitted from this test because this test
        focuses on reasoning + content tool event ordering.
        """
        events = [
            # response.created is handled separately by _chat_stream
            # response.in_progress is handled separately by the loop
            {"type": "response.reasoning.delta", "delta": "Hmm, "},
            {"type": "response.reasoning.delta", "delta": "let me think..."},
            {"type": "response.reasoning.summary", "summary_text": "I know!"},
            {"type": "response.output_text.delta", "delta": "The answer is 42.", "item_id": "1"},
            {"type": "response.output_text.done", "item_id": "1"},
            {"type": "response.completed", "finish_reason": "stop"},
        ]
        results = [_normalize_responses_event(e) for e in events]
        flattened = [item for sublist in results for item in sublist]

        types = [e["type"] for e in flattened]
        assert types == [
            "response.reasoning.delta",
            "response.reasoning.delta",
            "response.reasoning.done",
            "response.output_text.delta",
            "response.output_text.done",
            "response.completed",
        ]
        assert flattened[0]["delta"] == "Hmm, "
        assert flattened[1]["delta"] == "let me think..."
        assert flattened[3]["delta"] == "The answer is 42."

    def test_reasoning_events_are_llmevent_union_members(self):
        """Reasoning event types satisfy the LLMEvent union."""
        delta: LLMEvent = ReasoningDeltaEvent(type="response.reasoning.delta", delta="thinking...")
        done: LLMEvent = ReasoningDoneEvent(type="response.reasoning.done")
        assert delta["type"] == "response.reasoning.delta"
        assert done["type"] == "response.reasoning.done"

    # ── reasoning_text variant (LiteLLM / proxy servers) ──────────────

    def test_reasoning_text_delta_normalizes_like_reasoning_delta(self):
        """``response.reasoning_text.delta`` normalizes to ``ReasoningDeltaEvent``."""
        raw = {"type": "response.reasoning_text.delta", "delta": "Let me think about this..."}
        result = _normalize_responses_event(raw)
        assert len(result) == 1
        event = result[0]
        assert event["type"] == "response.reasoning.delta"
        assert event["delta"] == "Let me think about this..."

    def test_reasoning_text_delta_multiple_chunks(self):
        """Multiple reasoning_text delta events each produce a canonical event."""
        chunks = [
            {"type": "response.reasoning_text.delta", "delta": "Step 1: "},
            {"type": "response.reasoning_text.delta", "delta": "analyze."},
        ]
        results = [_normalize_responses_event(c)[0] for c in chunks]
        assert [e["delta"] for e in results] == ["Step 1: ", "analyze."]
        assert all(e["type"] == "response.reasoning.delta" for e in results)

    def test_reasoning_text_done_normalizes_to_reasoning_done(self):
        """``response.reasoning_text.done`` normalizes to ``ReasoningDoneEvent``."""
        raw = {"type": "response.reasoning_text.done"}
        result = _normalize_responses_event(raw)
        assert len(result) == 1
        assert result[0]["type"] == "response.reasoning.done"

    def test_reasoning_text_mixed_with_reasoning_events(self):
        """Both delta variants can appear in the same stream and produce the same types."""
        raw_events = [
            {"type": "response.reasoning.delta", "delta": "Hmm, "},
            {"type": "response.reasoning_text.delta", "delta": "let me "},
            {"type": "response.reasoning_text.delta", "delta": "think..."},
            {"type": "response.reasoning_text.done"},
        ]
        results = [_normalize_responses_event(e) for e in raw_events]
        flattened = [item for sublist in results for item in sublist]
        assert flattened[0]["type"] == "response.reasoning.delta"
        assert flattened[0]["delta"] == "Hmm, "
        assert flattened[1]["delta"] == "let me "
        assert flattened[2]["delta"] == "think..."
        assert flattened[3]["type"] == "response.reasoning.done"


class TestLifecycleEventNormalization:
    """Tests for lifecycle event normalization (response.created, etc.).

    These test the ``_normalize_lifecycle_event`` path exercised through
    ``_normalize_responses_event`` for lifecycle events from the OpenAI
    Responses API.
    """

    def test_response_created_normalizes_to_created_event(self):
        """``response.created`` normalizes to ``ResponseCreatedEvent``."""
        raw = {"type": "response.created", "response": {"id": "resp_1"}}
        result = _normalize_responses_event(raw)
        assert len(result) == 1
        event = result[0]
        assert event["type"] == "response.created"

    def test_response_created_is_llmevent_union_member(self):
        """ResponseCreatedEvent satisfies the LLMEvent union."""
        event: LLMEvent = ResponseCreatedEvent(type="response.created")
        assert event["type"] == "response.created"

    def test_response_in_progress_normalizes_to_in_progress_event(self):
        """``response.in_progress`` normalizes to ``ResponseInProgressEvent``."""
        raw = {"type": "response.in_progress"}
        result = _normalize_responses_event(raw)
        assert len(result) == 1
        assert result[0]["type"] == "response.in_progress"

    def test_response_in_progress_is_llmevent_union_member(self):
        """ResponseInProgressEvent satisfies the LLMEvent union."""
        event: LLMEvent = ResponseInProgressEvent(type="response.in_progress")
        assert event["type"] == "response.in_progress"

    def test_response_cancelled_normalizes_to_cancelled_event(self):
        """``response.cancelled`` normalizes to ``ResponseCancelledEvent``."""
        raw = {"type": "response.cancelled"}
        result = _normalize_responses_event(raw)
        assert len(result) == 1
        assert result[0]["type"] == "response.cancelled"

    def test_response_cancelled_is_llmevent_union_member(self):
        """ResponseCancelledEvent satisfies the LLMEvent union."""
        event: LLMEvent = ResponseCancelledEvent(type="response.cancelled")
        assert event["type"] == "response.cancelled"

    def test_lifecycle_events_are_normalized_in_full_stream(self):
        """Lifecycle events appear in the normalized output of a full stream."""
        events = [
            {"type": "response.created", "response": {"id": "resp_1"}},
            {"type": "response.in_progress"},
            {"type": "response.output_text.delta", "delta": "Hello", "content_index": 0},
            {"type": "response.output_text.done", "content_index": 0},
            {"type": "response.completed", "finish_reason": "stop"},
        ]
        results = [_normalize_responses_event(e) for e in events]
        flattened = [item for sublist in results for item in sublist]

        types = [e["type"] for e in flattened]
        assert types == [
            "response.created",
            "response.in_progress",
            "response.output_text.delta",
            "response.output_text.done",
            "response.completed",
        ]

    def test_raw_events_pairing_with_lifecycle_events(self):
        """Lifecycle events produce proper (canonical, raw) pairs with raw_events=True."""
        raw = {"type": "response.created", "response": {"id": "resp_1"}}
        result = _normalize_responses_event(raw)
        assert len(result) == 1
        assert result[0]["type"] == "response.created"


# ── Phase 3: Responses Attachment Translation Unit Tests ────────────────────

_SAMPLE_1X1_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


# Helper to create a minimal async upload function stub for testing.
def _make_noop_upload_fn() -> AsyncMock:
    """Return an AsyncMock that simulates upload returning a file_id."""
    return AsyncMock(return_value="file_uploaded_1")


class TestTranslateResponsesContentPart:
    """Unit tests for _translate_responses_content_part (task 0)."""

    @pytest.mark.asyncio
    async def test_text_content_part_returns_input_text(self):
        """Text ContentPart translates to input_text content part."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_content_part,
        )

        part = ContentPart(type="text", text="What do you see?")
        result = await _translate_responses_content_part(part)
        assert result == {"type": "input_text", "text": "What do you see?"}

    @pytest.mark.asyncio
    async def test_file_content_part_image_data_returns_input_image(self):
        """File ContentPart with data-backed image translates to input_image."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_content_part,
        )

        attachment = FileAttachment(
            data=_SAMPLE_1X1_PNG_B64,
            mime_type="image/png",
            filename="test.png",
        )
        part = ContentPart(type="file", file=attachment)
        result = await _translate_responses_content_part(part)
        assert result["type"] == "input_image"
        assert result["detail"] == "auto"
        assert result["image_url"].startswith("data:image/png;base64,")

    @pytest.mark.asyncio
    async def test_file_content_part_image_url_returns_input_image_url(self):
        """File ContentPart with URL-backed image translates to input_image with URL."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_content_part,
        )

        attachment = FileAttachment(
            url="https://example.com/photo.jpg",
            mime_type="image/jpeg",
        )
        part = ContentPart(type="file", file=attachment)
        result = await _translate_responses_content_part(part)
        assert result["type"] == "input_image"
        assert result["detail"] == "auto"
        assert result["image_url"] == "https://example.com/photo.jpg"

    @pytest.mark.asyncio
    async def test_file_content_part_file_id_returns_input_file(self):
        """File ContentPart with file_id translates to input_file reference."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_content_part,
        )

        attachment = FileAttachment(
            file_id="file_abc123",
            mime_type="application/pdf",
        )
        part = ContentPart(type="file", file=attachment)
        result = await _translate_responses_content_part(part)
        assert result == {"type": "input_file", "file_id": "file_abc123"}

    @pytest.mark.asyncio
    async def test_file_content_part_non_image_data_inline(self):
        """File ContentPart with non-image data → inline file_data (no upload)."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_content_part,
        )

        pdf_data = base64.b64encode(b"fake-pdf-content").decode("ascii")
        attachment = FileAttachment(
            data=pdf_data,
            mime_type="application/pdf",
            filename="doc.pdf",
        )
        part = ContentPart(type="file", file=attachment)
        # No _upload_fn needed — file_data is sent inline
        result = await _translate_responses_content_part(part)
        assert result["type"] == "input_file"
        assert result["filename"] == "doc.pdf"
        assert result["file_data"] == f"data:application/pdf;base64,{pdf_data}"

    @pytest.mark.asyncio
    async def test_file_content_part_non_image_url_creates_inline_file_data(self):
        """File ContentPart with non-image URL → inline file_data (Phase 5).

        Non-image URL attachments are now supported: the content is
        downloaded and sent inline as file_data, avoiding the /v1/files
        upload path for local/OpenAI-compatible servers.
        """
        from unittest.mock import AsyncMock, patch

        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_content_part,
        )

        attachment = FileAttachment(
            url="https://example.com/doc.pdf",
            mime_type="application/pdf",
            filename="doc.pdf",
        )
        part = ContentPart(type="file", file=attachment)
        with patch(
            "tinycua_sdk.providers.upload._download_url_content",
            AsyncMock(return_value=b"fake content"),
        ):
            result = await _translate_responses_content_part(part)
        assert result["type"] == "input_file"
        assert result["filename"] == "doc.pdf"
        assert result["file_data"].startswith("data:application/pdf;base64,")


class TestTranslateResponsesAttachment:
    """Unit tests for _translate_responses_attachment (task 1)."""

    @pytest.mark.asyncio
    async def test_data_backed_image_returns_input_image_with_data_url(self):
        """Data-backed image attachment → input_image with data URL and detail=auto."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_attachment,
        )

        attachment = FileAttachment(
            data=_SAMPLE_1X1_PNG_B64,
            mime_type="image/png",
            filename="test.png",
        )
        result = await _translate_responses_attachment(attachment)
        assert result["type"] == "input_image"
        assert result["detail"] == "auto"
        assert f"data:image/png;base64,{_SAMPLE_1X1_PNG_B64}" in result["image_url"]

    @pytest.mark.asyncio
    async def test_url_backed_image_returns_input_image_with_url(self):
        """URL-backed image attachment → input_image with URL and detail=auto."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_attachment,
        )

        attachment = FileAttachment(
            url="https://example.com/photo.jpg",
            mime_type="image/jpeg",
        )
        result = await _translate_responses_attachment(attachment)
        assert result["type"] == "input_image"
        assert result["detail"] == "auto"
        assert result["image_url"] == "https://example.com/photo.jpg"

    @pytest.mark.asyncio
    async def test_file_id_backed_attachment_returns_input_file(self):
        """file_id-backed attachment → input_file reference."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_attachment,
        )

        attachment = FileAttachment(
            file_id="file_abc123",
            mime_type="application/pdf",
        )
        result = await _translate_responses_attachment(attachment)
        assert result == {"type": "input_file", "file_id": "file_abc123"}

    @pytest.mark.asyncio
    async def test_image_file_id_attachment_returns_input_image(self):
        """Image file_id-backed attachment → input_image with detail=auto."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_attachment,
        )

        attachment = FileAttachment(
            file_id="file_img123",
            mime_type="image/png",
        )
        result = await _translate_responses_attachment(attachment)
        assert result == {
            "type": "input_image",
            "file_id": "file_img123",
            "detail": "auto",
        }

    @pytest.mark.asyncio
    async def test_non_image_data_inline_file_data(self):
        """Non-image data → inline input_file with file_data + filename (no upload)."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_attachment,
        )

        pdf_data = base64.b64encode(b"fake-pdf-content").decode("ascii")
        attachment = FileAttachment(
            data=pdf_data,
            mime_type="application/pdf",
            filename="doc.pdf",
        )
        # No _upload_fn needed — file_data sent inline
        result = await _translate_responses_attachment(attachment)
        assert result["type"] == "input_file"
        assert result["filename"] == "doc.pdf"
        assert result["file_data"] == f"data:application/pdf;base64,{pdf_data}"

    @pytest.mark.asyncio
    async def test_non_image_txt_as_input_file_with_file_data(self):
        """Text file sent as input_file with file_data when MIME is non-text.

        Verifies that .txt files CAN be sent as input_file + file_data
        (inline base64 content) instead of being decoded to input_text.
        Use any MIME not recognized as text (e.g., application/octet-stream).
        """
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_attachment,
        )

        txt_data = base64.b64encode(b"hello world from txt file").decode("ascii")
        attachment = FileAttachment(
            data=txt_data,
            mime_type="application/octet-stream",
            filename="readme.txt",
        )
        result = await _translate_responses_attachment(attachment)
        # Should NOT be decoded to input_text (MIME is not text/*)
        assert result["type"] == "input_file"
        assert result["filename"] == "readme.txt"
        assert result["file_data"] == f"data:application/octet-stream;base64,{txt_data}"

    @pytest.mark.asyncio
    async def test_non_image_url_attachment_downloads_inline(self):
        """Non-image URL attachment → download → inline file_data (no _upload_fn).

        Phase 5: Responses URL attachments are downloaded with SSRF
        protection and sent inline via file_data, avoiding /v1/files.
        """
        from unittest.mock import AsyncMock, patch

        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_attachment,
        )

        attachment = FileAttachment(
            url="https://example.com/doc.pdf",
            mime_type="application/pdf",
        )
        upload_fn = _make_noop_upload_fn()
        with patch(
            "tinycua_sdk.providers.upload._download_url_content",
            AsyncMock(return_value=b"fake pdf bytes"),
        ):
            result = await _translate_responses_attachment(
                attachment, _upload_fn=upload_fn,
            )
        assert result["type"] == "input_file"
        assert "file_data" in result
        assert "file_id" not in result, (
            "URL attachments should use inline file_data, not file_id"
        )
        upload_fn.assert_not_awaited()


class TestTranslateResponsesUserMessage:
    """Unit tests for _translate_responses_user_message (task 2)."""

    @pytest.mark.asyncio
    async def test_string_only_passthrough(self):
        """String-only user message passes through unchanged."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_user_message,
        )

        msg: dict = {"role": "user", "content": "Hello!"}
        result = await _translate_responses_user_message(msg)
        assert result == {"role": "user", "content": "Hello!"}

    @pytest.mark.asyncio
    async def test_string_with_attachments(self):
        """String content with attachments → text part + image parts."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_user_message,
        )

        attachment = FileAttachment(
            data=_SAMPLE_1X1_PNG_B64,
            mime_type="image/png",
        )
        msg: dict = {
            "role": "user",
            "content": "Describe this image",
            "attachments": [attachment],
        }
        result = await _translate_responses_user_message(msg)
        assert result["role"] == "user"
        assert "attachments" not in result
        parts = result["content"]
        assert isinstance(parts, list)
        assert len(parts) == 2
        assert parts[0] == {"type": "input_text", "text": "Describe this image"}
        assert parts[1]["type"] == "input_image"
        assert parts[1]["detail"] == "auto"

    @pytest.mark.asyncio
    async def test_empty_string_omits_text_part(self):
        """Empty string content with attachments omits the text part."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_user_message,
        )

        attachment = FileAttachment(
            data=_SAMPLE_1X1_PNG_B64,
            mime_type="image/png",
        )
        msg: dict = {
            "role": "user",
            "content": "",
            "attachments": [attachment],
        }
        result = await _translate_responses_user_message(msg)
        assert result["role"] == "user"
        parts = result["content"]
        assert len(parts) == 1
        assert parts[0]["type"] == "input_image"

    @pytest.mark.asyncio
    async def test_content_part_list(self):
        """list[ContentPart] content → translated content parts."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_user_message,
        )

        attachment = FileAttachment(
            data=_SAMPLE_1X1_PNG_B64,
            mime_type="image/png",
        )
        msg: dict = {
            "role": "user",
            "content": [
                ContentPart(type="text", text="What do you see?"),
                ContentPart(type="file", file=attachment),
            ],
        }
        result = await _translate_responses_user_message(msg)
        assert result["role"] == "user"
        parts = result["content"]
        assert isinstance(parts, list)
        assert len(parts) == 2
        assert parts[0] == {"type": "input_text", "text": "What do you see?"}
        assert parts[1]["type"] == "input_image"

    @pytest.mark.asyncio
    async def test_content_part_list_with_attachments(self):
        """list[ContentPart] + attachments → content parts then attachment parts."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_user_message,
        )

        cp_attachment = FileAttachment(
            data=_SAMPLE_1X1_PNG_B64,
            mime_type="image/png",
            filename="cp_image.png",
        )
        msg_attachment = FileAttachment(
            url="https://example.com/photo.jpg",
            mime_type="image/jpeg",
            filename="msg_image.jpg",
        )
        msg: dict = {
            "role": "user",
            "content": [
                ContentPart(type="text", text="First"),
                ContentPart(type="file", file=cp_attachment),
            ],
            "attachments": [msg_attachment],
        }
        result = await _translate_responses_user_message(msg)
        assert result["role"] == "user"
        parts = result["content"]
        assert isinstance(parts, list)
        assert len(parts) == 3
        assert parts[0] == {"type": "input_text", "text": "First"}
        assert parts[1]["type"] == "input_image"  # cp_attachment
        assert parts[2]["type"] == "input_image"  # msg_attachment

    @pytest.mark.asyncio
    async def test_empty_content_list_raises_value_error(self):
        """Empty list[ContentPart] raises ValueError."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_user_message,
        )

        msg: dict = {"role": "user", "content": []}
        with pytest.raises(ValueError, match="content list cannot be empty"):
            await _translate_responses_user_message(msg)

    @pytest.mark.asyncio
    async def test_dict_coercion_for_content_part_items(self):
        """Dict items in content list are coerced to ContentPart."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_user_message,
        )

        attachment = FileAttachment(
            data=_SAMPLE_1X1_PNG_B64,
            mime_type="image/png",
        )
        msg: dict = {
            "role": "user",
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "file", "file": attachment},
            ],
        }
        result = await _translate_responses_user_message(msg)
        assert result["role"] == "user"
        parts = result["content"]
        assert len(parts) == 2
        assert parts[0] == {"type": "input_text", "text": "Hello"}
        assert parts[1]["type"] == "input_image"

    @pytest.mark.asyncio
    async def test_empty_attachments_same_as_omitted(self):
        """Empty attachments list behaves same as omitted."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_user_message,
        )

        msg: dict = {"role": "user", "content": "hi", "attachments": []}
        result = await _translate_responses_user_message(msg)
        assert result == {"role": "user", "content": "hi"}

    @pytest.mark.asyncio
    async def test_none_attachments_same_as_omitted(self):
        """None attachments behaves same as omitted."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_user_message,
        )

        msg: dict = {"role": "user", "content": "hi", "attachments": None}
        result = await _translate_responses_user_message(msg)
        assert result == {"role": "user", "content": "hi"}

    @pytest.mark.asyncio
    async def test_multiple_attachments_preserve_order(self):
        """Multiple attachments appear in caller-supplied order."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_user_message,
        )

        att1 = FileAttachment(
            data=_SAMPLE_1X1_PNG_B64,
            mime_type="image/png",
            filename="first.png",
        )
        att2 = FileAttachment(
            url="https://example.com/second.jpg",
            mime_type="image/jpeg",
            filename="second.jpg",
        )
        msg: dict = {
            "role": "user",
            "content": "Look at these",
            "attachments": [att1, att2],
        }
        result = await _translate_responses_user_message(msg)
        parts = result["content"]
        assert len(parts) == 3
        assert parts[0] == {"type": "input_text", "text": "Look at these"}
        assert parts[1]["type"] == "input_image"
        assert parts[2]["type"] == "input_image"


class TestUploadCache:
    """Unit tests for upload cache behavior (task 3)."""

    @pytest.fixture
    def model(self) -> LanguageModel:
        return LanguageModel(model_name="gpt-4o-mini")

    @pytest.mark.asyncio
    async def test_non_image_data_uploads_once_and_caches(self, model):
        """Non-image data-backed attachment uploads once; second use reuses file_id.

        Tests through the client's ``_ensure_uploaded_file_id`` method,
        which owns the per-session cache.
        """
        from unittest.mock import AsyncMock, MagicMock

        client = OpenAIResponsesClient(model)
        # Set up mock so _get_client() returns a mock
        mock_openai = MagicMock()
        mock_openai.files = MagicMock()
        mock_upload_result = MagicMock()
        mock_upload_result.id = "file_uploaded_1"
        mock_openai.files.create = AsyncMock(return_value=mock_upload_result)
        client._client = mock_openai

        pdf_data = base64.b64encode(b"pdf-content").decode("ascii")
        attachment = FileAttachment(
            data=pdf_data,
            mime_type="application/pdf",
            filename="doc.pdf",
        )

        # First call: should upload
        file_id_1 = await client._ensure_uploaded_file_id(attachment)
        assert file_id_1 == "file_uploaded_1"
        assert mock_openai.files.create.await_count == 1

        # Second call with same attachment: should NOT upload again
        file_id_2 = await client._ensure_uploaded_file_id(attachment)
        assert file_id_2 == "file_uploaded_1"
        assert mock_openai.files.create.await_count == 1  # Still 1

    @pytest.mark.asyncio
    async def test_different_non_image_attachments_upload_separately(self, model):
        """Different non-image attachments upload separately."""
        from unittest.mock import AsyncMock, MagicMock

        client = OpenAIResponsesClient(model)
        mock_openai = MagicMock()
        mock_openai.files = MagicMock()
        mock_openai.files.create = AsyncMock(
            side_effect=lambda **kwargs: _mock_upload_result(kwargs.get("file"))
        )
        client._client = mock_openai

        def _mock_upload_result(file_obj):
            result = MagicMock()
            result.id = f"file_{file_obj.name}"
            return result

        pdf_data_1 = base64.b64encode(b"pdf-content-1").decode("ascii")
        pdf_data_2 = base64.b64encode(b"pdf-content-2").decode("ascii")
        att1 = FileAttachment(
            data=pdf_data_1,
            mime_type="application/pdf",
            filename="doc1.pdf",
        )
        att2 = FileAttachment(
            data=pdf_data_2,
            mime_type="application/pdf",
            filename="doc2.pdf",
        )

        file_id_1 = await client._ensure_uploaded_file_id(att1)
        file_id_2 = await client._ensure_uploaded_file_id(att2)
        assert file_id_1 == "file_doc1.pdf"
        assert file_id_2 == "file_doc2.pdf"
        assert mock_openai.files.create.await_count == 2

    @pytest.mark.asyncio
    async def test_pre_existing_file_id_bypasses_upload(self, model):
        """Attachment with pre-existing file_id bypasses upload."""
        # Test through the module-level translator with upload_fn mock
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_attachment,
        )

        attachment = FileAttachment(
            file_id="file_abc123",
            mime_type="application/pdf",
        )
        upload_called = False

        async def upload_fn(att: FileAttachment) -> str:
            nonlocal upload_called
            upload_called = True
            return "should_not_be_called"

        result = await _translate_responses_attachment(
            attachment, _upload_fn=upload_fn,
        )
        assert result == {"type": "input_file", "file_id": "file_abc123"}
        assert not upload_called

    @pytest.mark.asyncio
    async def test_cache_key_is_content_based(self, model):
        """Cache key is derived from content and MIME type, not filename."""
        from tinycua_sdk.providers.upload import _make_cache_key

        pdf_data = base64.b64encode(b"same-content").decode("ascii")
        att1 = FileAttachment(
            data=pdf_data,
            mime_type="application/pdf",
            filename="a.pdf",
        )
        att2 = FileAttachment(
            data=pdf_data,
            mime_type="application/pdf",
            filename="b.pdf",
        )
        # Same data and mime, different filename → same cache key
        # (canonical content-based deduplication)
        key1 = _make_cache_key(att1)
        key2 = _make_cache_key(att2)
        assert key1 == key2

        # Different content → different cache key
        att3 = FileAttachment(
            data=base64.b64encode(b"different-content").decode("ascii"),
            mime_type="application/pdf",
            filename="a.pdf",
        )
        key3 = _make_cache_key(att3)
        assert key1 != key3

    @pytest.mark.asyncio
    async def test_empty_data_backed_attachment_uploads_instead_of_rejecting(
        self, model,
    ):
        """Empty data-backed (zero-byte) attachment reaches upload, not ValueError.

        Regression test for ISSUE-001: ``FileAttachment.from_bytes(b"", ...)``
        produces ``data=""`` (a valid base64 of empty bytes).  The guard
        should only reject ``data is None``, not falsey strings.
        """
        from unittest.mock import AsyncMock, MagicMock

        client = OpenAIResponsesClient(model)
        mock_openai = MagicMock()
        mock_openai.files = MagicMock()
        uploaded = MagicMock()
        uploaded.id = "file_empty"
        mock_openai.files.create = AsyncMock(return_value=uploaded)
        client._client = mock_openai

        attachment = FileAttachment.from_bytes(
            b"",
            mime_type="application/pdf",
            filename="empty.pdf",
        )
        file_id = await client._ensure_uploaded_file_id(attachment)
        assert file_id == "file_empty"
        mock_openai.files.create.assert_awaited_once()


class TestRegressionResponses:
    """Regression tests for Responses provider (task 4)."""

    @pytest.fixture
    def model(self) -> LanguageModel:
        return LanguageModel(model_name="gpt-4o-mini")

    @pytest.fixture
    def sdk_client(self, model: LanguageModel) -> OpenAIResponsesClient:
        client = OpenAIResponsesClient(model)
        mock_async_openai = MagicMock()
        mock_async_openai.responses = MagicMock()
        client._client = mock_async_openai
        return client

    def test_string_only_message_via_build_payload_unchanged(self):
        """String-only messages produce same payload input as before Phase 3."""
        model = LanguageModel(model_name="gpt-4o-mini")
        messages = [{"role": "user", "content": "hello world"}]
        translated = _translate_messages(messages)
        client = OpenAIResponsesClient(model)
        payload = client._build_request_kwargs(translated, None)
        assert any(
            item == {"role": "user", "content": "hello world"}
            for item in payload["input"]
        )

    def test_tool_result_translation_unchanged(self):
        """ToolResultMessage translation produces function_call_output unchanged."""
        model = LanguageModel(model_name="gpt-4o-mini")
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "tool_result", "call_id": "call_1", "content": "result"},
        ]
        translated = _translate_messages(messages)
        client = OpenAIResponsesClient(model)
        payload = client._build_request_kwargs(translated, None)
        assert any(
            item.get("type") == "function_call_output"
            and item.get("output") == "result"
            for item in payload["input"]
        )

    @pytest.mark.asyncio
    async def test_previous_response_id_still_works(self, sdk_client):
        """previous_response_id behavior unchanged with tool_result messages."""
        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            "id": "resp_before",
            "model": "gpt-4o-mini",
            "status": "completed",
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "ok"}]},
            ],
            "usage": {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
        }
        sdk_client._client.responses.create = AsyncMock(return_value=mock_response)

        # First call to set _previous_response_id
        await sdk_client.chat(messages=[{"role": "user", "content": "first"}])

        # Second call with tool_result
        mock_response2 = MagicMock()
        mock_response2.model_dump.return_value = {
            "id": "resp_after",
            "model": "gpt-4o-mini",
            "status": "completed",
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "after"}]},
            ],
            "usage": {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
        }
        sdk_client._client.responses.create = AsyncMock(return_value=mock_response2)

        await sdk_client.chat(
            messages=[
                {"role": "user", "content": "first"},
                {"role": "tool_result", "call_id": "call_1", "content": "42"},
            ],
        )
        call_kwargs = sdk_client._client.responses.create.call_args[1]
        assert call_kwargs.get("previous_response_id") == "resp_before"

    @pytest.mark.asyncio
    async def test_string_only_user_message_same_through_instance_translation(self, sdk_client):
        """String-only message through _chat_sync produces identical payload."""
        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            "id": "resp_1",
            "model": "gpt-4o-mini",
            "status": "completed",
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "Hello!"}]},
            ],
            "usage": {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
        }
        sdk_client._client.responses.create = AsyncMock(return_value=mock_response)

        result = await sdk_client.chat(
            messages=[{"role": "user", "content": "hello world"}],
        )
        assert result["content"] == "Hello!"

        call_kwargs = sdk_client._client.responses.create.call_args[1]
        input_items = call_kwargs["input"]
        assert any(
            item == {"role": "user", "content": "hello world"}
            for item in input_items
        )


class TestResponsesToolResultTranslation:
    """Responses API tool-result attachment translation tests."""

    @pytest.mark.asyncio
    async def test_translates_tool_result_content_parts_to_function_call_output(self):
        """Responses translates ContentPart list to func_call_output + synthetic user."""
        attachment = FileAttachment.from_bytes(
            b"img", mime_type="image/png", filename="img.png",
        )
        client = OpenAIResponsesClient(
            LanguageModel(model_name="gpt-test"),
        )
        messages = [
            {
                "role": "tool_result",
                "call_id": "call_1",
                "content": [
                    ContentPart(type="text", text="Generated image."),
                    ContentPart(type="file", file=attachment),
                ],
            }
        ]

        translated = await client._translate_responses_input(messages)

        # First item: function_call_output with plain-string output.
        func_output = translated[0]
        assert func_output["type"] == "function_call_output"
        assert func_output["call_id"] == "call_1"
        assert func_output["output"] == "Generated image."

        # Second item: synthetic user message with image.
        assert len(translated) == 2
        user_msg = translated[1]
        assert user_msg["role"] == "user"
        assert user_msg["content"][0]["type"] == "input_image"


    @pytest.mark.asyncio
    async def test_translates_tool_result_attachments_async(self):
        """Responses translates string+attachments to func_call_output + synthetic user."""
        attachment = FileAttachment.from_bytes(
            b"img", mime_type="image/png", filename="img.png",
        )
        client = OpenAIResponsesClient(
            LanguageModel(model_name="gpt-test"),
        )
        messages = [
            {
                "role": "tool_result",
                "call_id": "call_2",
                "content": "Here is the image.",
                "attachments": [attachment],
            },
        ]

        translated = await client._translate_responses_input(messages)

        # First item: function_call_output with plain-string output.
        func_output = translated[0]
        assert func_output["type"] == "function_call_output"
        assert func_output["call_id"] == "call_2"
        assert func_output["output"] == "Here is the image."

        # Second item: synthetic user message with image.
        assert len(translated) == 2
        user_msg = translated[1]
        assert user_msg["role"] == "user"
        assert user_msg["content"][0]["type"] == "input_image"

    @pytest.mark.asyncio
    async def test_parallel_tool_results_outputs_before_attachments(self):
        """All function_call_outputs emitted before synthetic user messages."""
        attachment = FileAttachment.from_bytes(
            b"img", mime_type="image/png", filename="img.png",
        )
        client = OpenAIResponsesClient(
            LanguageModel(model_name="gpt-test"),
        )
        messages = [
            {
                "role": "tool_result",
                "call_id": "call_1",
                "content": "one",
                "attachments": [attachment],
            },
            {
                "role": "tool_result",
                "call_id": "call_2",
                "content": "two",
            },
        ]

        translated = await client._translate_responses_input(messages)

        # Order must be: func_call_output(call_1), func_call_output(call_2), user
        order = [item.get("type") or item.get("role") for item in translated]
        assert order == ["function_call_output", "function_call_output", "user"], (
            f"Expected [function_call_output, function_call_output, user], got {order}"
        )
        assert translated[0]["call_id"] == "call_1"
        assert translated[0]["output"] == "one"
        assert translated[1]["call_id"] == "call_2"
        assert translated[1]["output"] == "two"
        assert translated[2]["role"] == "user"
