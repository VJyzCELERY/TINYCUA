"""Unit tests for Chat Completions request/response behavior.

Tests payload translation, non-streaming/streaming normalization,
tool-call accumulation, error mapping, and raw-events pairing.
"""

import base64

import pytest
from unittest.mock import AsyncMock, MagicMock

from tinycua_sdk.agent.events import LLMResponse
from tinycua_sdk.providers.open_ai import (
    OpenAIChatCompletionsClient,
    _translate_chat_attachment,
    _translate_chat_content_part,
    _translate_chat_user_message,
)
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.core.exceptions import ProviderApiError, ProviderAuthError
from tinycua_sdk.models.attachment import ContentPart, FileAttachment


class TestChatCompletionsPayloadTranslation:
    """Chat Completions payload uses messages, max_tokens, response_format, tool-result role='tool'."""

    @pytest.fixture
    def model(self) -> LanguageModel:
        return LanguageModel(model_name="gpt-4o-mini")

    @pytest.fixture
    def client(self, model: LanguageModel) -> OpenAIChatCompletionsClient:
        return OpenAIChatCompletionsClient(model)

    def test_payload_uses_messages_not_input(self, client: OpenAIChatCompletionsClient):
        """Payload key is 'messages', not 'input'."""
        payload = client._build_chat_payload(
            [{"role": "user", "content": "hi"}],
        )
        assert "messages" in payload
        assert "input" not in payload

    def test_payload_uses_max_tokens_not_max_output_tokens(self, client: OpenAIChatCompletionsClient):
        """Payload uses 'max_tokens' directly, not 'max_output_tokens'."""
        payload = client._build_chat_payload(
            [{"role": "user", "content": "hi"}],
        )
        assert "max_tokens" not in payload

        client._model_config = LanguageModel(model_name="gpt-4o-mini", max_tokens=100)
        payload = client._build_chat_payload(
            [{"role": "user", "content": "hi"}],
        )
        assert payload["max_tokens"] == 100

    def test_response_format_passed_directly(self, client: OpenAIChatCompletionsClient):
        """response_format is passed directly, not wrapped in 'text.format'."""
        client._model_config = LanguageModel(
            model_name="gpt-4o-mini",
            response_format={"type": "json_object"},
        )
        payload = client._build_chat_payload(
            [{"role": "user", "content": "hi"}],
        )
        assert payload["response_format"] == {"type": "json_object"}

    def test_tool_result_maps_to_tool_role(self, client: OpenAIChatCompletionsClient):
        """ToolResultMessage maps to {role: 'tool', tool_call_id, content} with prior tool_calls."""
        client._prior_tool_calls = {
            "call_1": {"id": "call_1", "type": "function", "function": {"name": "lookup", "arguments": '{"q":"time"}'}},
        }
        messages = client._translate_chat_messages([
            {"role": "user", "content": "what is the result?"},
            {"role": "tool_result", "call_id": "call_1", "content": "42"},
        ])
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["tool_calls"] == [{"id": "call_1", "type": "function", "function": {"name": "lookup", "arguments": '{"q":"time"}'}}]
        assert messages[2]["role"] == "tool"
        assert messages[2]["tool_call_id"] == "call_1"
        assert messages[2]["content"] == "42"

    def test_multi_turn_tool_result_batches_pair_correctly(self, client: OpenAIChatCompletionsClient):
        """Each contiguous tool-result batch is paired with its own originating tool_calls.

        Simulates two tool-calling turns with the *full* accumulated history
        in ``_prior_tool_calls``.  The first batch lacks a preceding assistant
        with tool_calls and thus needs injection from the history dict.  The
        second batch has an assistant with tool_calls already embedded (as the
        agent loop now does), so no injection occurs — ensuring that each
        ``tool`` message's ``tool_call_id`` matches the immediately preceding
        ``assistant.tool_calls`` entry.
        """
        # After two tool-calling turns the history dict contains both
        # the first and second batch's call_ids.
        client._prior_tool_calls = {
            "call_1": {"id": "call_1", "type": "function", "function": {"name": "first", "arguments": "{}"}},
            "call_2": {"id": "call_2", "type": "function", "function": {"name": "second", "arguments": "{}"}},
        }
        messages = client._translate_chat_messages([
            {"role": "user", "content": "start"},
            {"role": "assistant", "content": ""},  # No tool_calls — needs injection
            # Batch 1
            {"role": "tool_result", "call_id": "call_1", "content": "first-result"},
            # Assistant with embedded tool_calls (agent loop did this after second response)
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "call_2", "type": "function", "function": {"name": "second", "arguments": "{}"}},
            ]},
            # Batch 2 — already preceded by assistant with matching tool_calls
            {"role": "tool_result", "call_id": "call_2", "content": "second-result"},
        ])
        # user, assistant(empty), assistant(injected=[call_1]), tool(call_1),
        # assistant(embedded=[call_2]), tool(call_2) = 6 messages
        assert len(messages) == 6, f"Expected 6 messages, got {len(messages)}: {messages}"

        # Batch 1: injection from history
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[1].get("content") == ""
        assert "tool_calls" not in messages[1]
        assert messages[2]["role"] == "assistant"
        assert "tool_calls" in messages[2]
        assert len(messages[2]["tool_calls"]) == 1
        assert messages[2]["tool_calls"][0]["id"] == "call_1"
        assert messages[3]["role"] == "tool"
        assert messages[3]["tool_call_id"] == "call_1"

        # Batch 2: preceding assistant ALREADY has tool_calls — no injection
        assert messages[4]["role"] == "assistant"
        assert "tool_calls" in messages[4]
        assert messages[4]["tool_calls"][0]["id"] == "call_2"
        assert messages[5]["role"] == "tool"
        assert messages[5]["tool_call_id"] == "call_2"

    def test_multi_turn_with_full_history_no_embedded_tc(self, client: OpenAIChatCompletionsClient):
        """When no assistant has embedded tool_calls, each batch is injected from history.

        Tests the fallback injection path: all ``_prior_tool_calls`` are in the
        history dict, and no assistant message carries pre-embedded ``tool_calls``.
        Each contiguous batch must still get its own matching tool_calls injected.
        """
        client._prior_tool_calls = {
            "call_1": {"id": "call_1", "type": "function", "function": {"name": "first", "arguments": "{}"}},
            "call_2": {"id": "call_2", "type": "function", "function": {"name": "second", "arguments": "{}"}},
        }
        messages = client._translate_chat_messages([
            {"role": "user", "content": "start"},
            {"role": "assistant", "content": ""},
            # Batch 1
            {"role": "tool_result", "call_id": "call_1", "content": "first-result"},
            # Assistant without tool_calls (simulates path where agent loop does NOT embed)
            {"role": "assistant", "content": "intermediate"},
            # Batch 2
            {"role": "tool_result", "call_id": "call_2", "content": "second-result"},
        ])
        # user, assistant(empty), assistant(injected=[call_1]), tool(call_1),
        # assistant(intermediate), assistant(injected=[call_2]), tool(call_2) = 7 messages
        assert len(messages) == 7, f"Expected 7 messages, got {len(messages)}: {messages}"

        # Batch 1 injection
        assert messages[2]["role"] == "assistant"
        assert "tool_calls" in messages[2]
        assert messages[2]["tool_calls"][0]["id"] == "call_1"
        assert messages[3]["role"] == "tool"
        assert messages[3]["tool_call_id"] == "call_1"

        # Batch 2 injection
        assert messages[5]["role"] == "assistant"
        assert "tool_calls" in messages[5]
        assert messages[5]["tool_calls"][0]["id"] == "call_2"
        assert messages[6]["role"] == "tool"
        assert messages[6]["tool_call_id"] == "call_2"

    def test_translate_chat_tools_adds_function_wrapper(self, client: OpenAIChatCompletionsClient):
        """Tool specs are wrapped with type='function' and function nested object."""
        tools = client._translate_chat_tools([
            {"name": "lookup", "description": "Lookup something", "parameters": {"type": "object"}},
        ])
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "lookup"
        assert tools[0]["function"]["description"] == "Lookup something"
        assert tools[0]["function"]["parameters"] == {"type": "object"}


class TestChatCompletionsNonStreaming:
    """Non-streaming response normalization."""

    @pytest.fixture
    def client(self) -> OpenAIChatCompletionsClient:
        return OpenAIChatCompletionsClient(LanguageModel(model_name="gpt-4o-mini"))

    def test_normalize_text_response(self, client: OpenAIChatCompletionsClient):
        """Text response normalizes content, finish_reason, usage."""
        data = {
            "model": "gpt-4o-mini",
            "choices": [{
                "message": {"role": "assistant", "content": "Hello world", "tool_calls": None},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        result: LLMResponse = client._normalize_non_streaming_response(data)
        assert result["content"] == "Hello world"
        assert result["finish_reason"] == "stop"
        assert result["usage"]["input_tokens"] == 10
        assert result["usage"]["output_tokens"] == 5
        assert result["usage"]["total_tokens"] == 15
        assert result["model"] == "gpt-4o-mini"

    def test_normalize_tool_call_response(self, client: OpenAIChatCompletionsClient):
        """Tool call response has content=None and populated tool_calls."""
        data = {
            "model": "gpt-4o-mini",
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": "call_1", "type": "function", "function": {"name": "lookup", "arguments": '{"q":"time"}'}},
                    ],
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        result: LLMResponse = client._normalize_non_streaming_response(data)
        assert result["content"] is None
        assert result["finish_reason"] == "tool_calls"
        assert result["tool_calls"] is not None
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["call_id"] == "call_1"
        assert result["tool_calls"][0]["name"] == "lookup"
        assert result["tool_calls"][0]["arguments"] == '{"q":"time"}'


class TestChatCompletionsStreamingContent:
    """Streaming content delta normalization."""

    @pytest.fixture
    def client(self) -> OpenAIChatCompletionsClient:
        return OpenAIChatCompletionsClient(LanguageModel(model_name="gpt-4o-mini"))

    @pytest.mark.asyncio
    async def test_streaming_content_deltas(self, client: OpenAIChatCompletionsClient):
        """Content deltas produce ContentDeltaEvent, then ContentDoneEvent, then ResponseCompletedEvent."""
        chunks = [
            _mock_chunk({"content": "Hello"}),
            _mock_chunk({"content": " world"}),
            _mock_chunk({}, finish_reason="stop"),
        ]
        sdk = MagicMock()
        sdk.chat.completions.create = AsyncMock(return_value=async_iter(chunks))
        client._client = sdk

        result = await client.chat(
            [{"role": "user", "content": "hi"}],
            stream=True,
        )
        events = [e async for e in result]

        types = [e["type"] for e in events]
        assert types == [
            "response.created",
            "response.output_text.delta",
            "response.output_text.delta",
            "response.output_text.done",
            "response.completed",
        ]
        assert events[1]["delta"] == "Hello"
        assert events[2]["delta"] == " world"

    @pytest.mark.asyncio
    async def test_streaming_tool_call_accumulation(self, client: OpenAIChatCompletionsClient):
        """Partial tool-call deltas accumulate into one ToolCallReadyEvent."""
        chunks = [
            _mock_chunk({"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": "lookup", "arguments": ""}}]}),
            _mock_chunk({"tool_calls": [{"index": 0, "function": {"arguments": '{"q":'}}]}),
            _mock_chunk({"tool_calls": [{"index": 0, "function": {"arguments": '"time"}'}}]}),
            _mock_chunk({}, finish_reason="tool_calls"),
        ]
        sdk = MagicMock()
        sdk.chat.completions.create = AsyncMock(return_value=async_iter(chunks))
        client._client = sdk

        result = await client.chat(
            [{"role": "user", "content": "time?"}],
            tools=[{"name": "lookup", "description": "Lookup", "parameters": {"type": "object"}}],
            stream=True,
        )
        events = [e async for e in result]

        types = [e["type"] for e in events]
        ready_count = types.count("tool_call.ready")
        assert ready_count == 1, f"Expected exactly 1 tool_call.ready, got {ready_count}"
        ready = next(e for e in events if e["type"] == "tool_call.ready")
        assert ready["call_id"] == "call_1"
        assert ready["name"] == "lookup"
        assert ready["arguments"] == '{"q":"time"}'

    @pytest.mark.asyncio
    async def test_streaming_content_events_order(self, client: OpenAIChatCompletionsClient):
        """Streaming content events: created, delta, done, usage if present, completed."""
        chunks = [
            _mock_chunk({"content": "A"}),
            _mock_chunk({"content": "B"}),
            _mock_chunk({}, finish_reason="stop"),
        ]
        sdk = MagicMock()
        sdk.chat.completions.create = AsyncMock(return_value=async_iter(chunks))
        client._client = sdk

        result = await client.chat(
            [{"role": "user", "content": "hi"}],
            stream=True,
        )
        events = [e async for e in result]
        assert events[0]["type"] == "response.created"
        assert events[-1]["type"] == "response.completed"

    @pytest.mark.asyncio
    async def test_streaming_usage_before_completed(self, client: OpenAIChatCompletionsClient):
        """Usage-only chunk after terminal choice chunk: usage emitted before completed."""
        chunks = [
            _mock_chunk({"content": "x"}, finish_reason="stop"),
            _mock_chunk({}, usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}),
        ]
        sdk = MagicMock()
        sdk.chat.completions.create = AsyncMock(return_value=async_iter(chunks))
        client._client = sdk

        result = await client.chat(
            [{"role": "user", "content": "hi"}],
            stream=True,
        )
        events = [e async for e in result]
        types = [e["type"] for e in events]
        usage_idx = types.index("response.usage")
        completed_idx = types.index("response.completed")
        assert usage_idx < completed_idx, f"usage at {usage_idx} must precede completed at {completed_idx}"

    @pytest.mark.asyncio
    async def test_streaming_tool_events_order(self, client: OpenAIChatCompletionsClient):
        """Streaming tool events: started, argument delta, arguments done, ready, completed."""
        chunks = [
            _mock_chunk({"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": "lookup", "arguments": ""}}]}),
            _mock_chunk({"tool_calls": [{"index": 0, "function": {"arguments": '{}'}}]}),
            _mock_chunk({}, finish_reason="tool_calls"),
        ]
        sdk = MagicMock()
        sdk.chat.completions.create = AsyncMock(return_value=async_iter(chunks))
        client._client = sdk

        result = await client.chat(
            [{"role": "user", "content": "hi"}],
            tools=[{"name": "lookup", "description": "Lookup", "parameters": {"type": "object"}}],
            stream=True,
        )
        events = [e async for e in result]
        types = [e["type"] for e in events]
        assert "response.output_item.added" in types
        assert "response.function_call_arguments.delta" in types
        assert "response.function_call_arguments.done" in types
        assert "tool_call.ready" in types
        assert "response.completed" in types

    @pytest.mark.asyncio
    async def test_tool_only_response_content_none(self, client: OpenAIChatCompletionsClient):
        """Non-streaming tool-only response returns content=None and populated tool_calls."""
        data = {
            "model": "gpt-4o-mini",
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": "call_1", "type": "function", "function": {"name": "lookup", "arguments": "{}"}},
                    ],
                },
                "finish_reason": "tool_calls",
            }],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        result = client._normalize_non_streaming_response(data)
        assert result["content"] is None
        assert result["tool_calls"] is not None
        assert len(result["tool_calls"]) == 1


class TestChatCompletionsErrorMapping:
    """Error translation to ProviderAuthError and ProviderApiError."""

    @pytest.fixture
    def client(self) -> OpenAIChatCompletionsClient:
        return OpenAIChatCompletionsClient(LanguageModel(model_name="gpt-4o-mini"))

    def test_401_raises_auth_error(self, client: OpenAIChatCompletionsClient):
        exc = Exception("invalid API key")
        exc.status_code = 401
        with pytest.raises(ProviderAuthError, match="invalid API key"):
            client._handle_provider_error(exc)

    def test_403_raises_auth_error(self, client: OpenAIChatCompletionsClient):
        exc = Exception("forbidden")
        exc.status_code = 403
        with pytest.raises(ProviderAuthError, match="forbidden"):
            client._handle_provider_error(exc)

    def test_500_raises_api_error(self, client: OpenAIChatCompletionsClient):
        exc = Exception("server error")
        exc.status_code = 500
        with pytest.raises(ProviderApiError) as excinfo:
            client._handle_provider_error(exc)
        assert excinfo.value.status_code == 500

    def test_auth_keyword_raises_auth_error(self, client: OpenAIChatCompletionsClient):
        exc = Exception("authentication failed")
        with pytest.raises(ProviderAuthError):
            client._handle_provider_error(exc)


class TestChatCompletionsRawEvents:
    """Raw-events one-to-many pairing."""

    @pytest.fixture
    def client(self) -> OpenAIChatCompletionsClient:
        return OpenAIChatCompletionsClient(LanguageModel(model_name="gpt-4o-mini"))

    @pytest.mark.asyncio
    async def test_raw_events_first_gets_raw_follow_on_none(self, client: OpenAIChatCompletionsClient):
        """One chunk producing multiple canonical events: first gets raw, follow-on gets raw=None."""
        terminal_chunk = _mock_chunk({"content": "Bye"}, finish_reason="stop")
        sdk = MagicMock()
        sdk.chat.completions.create = AsyncMock(return_value=async_iter([terminal_chunk]))
        client._client = sdk

        result = await client.chat(
            [{"role": "user", "content": "hi"}],
            stream=True,
            raw_events=True,
        )
        pairs = [p async for p in result]

        assert pairs[0][1] is not None
        assert pairs[0][1]["raw_event"] is terminal_chunk
        assert any(p[1] is None for p in pairs[1:]), "Expected at least one follow-on event with raw=None"


class TestChatCompletionsAttachmentTranslation:
    """Unit tests for Chat Completions file attachment translation.

    Covers ``_translate_chat_attachment()``,
    ``_translate_chat_content_part()``, and
    ``_translate_chat_user_message()`` private helpers.
    """

    # ── _translate_chat_attachment ────────────────────────────────────────

    def test_translate_attachment_data_backed_image_png(self):
        """Data-backed image/png attachment produces a data URL image_url part."""
        encoded = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode("ascii")
        attachment = FileAttachment(data=encoded, mime_type="image/png")
        result = _translate_chat_attachment(attachment)
        assert result["type"] == "image_url"
        assert result["image_url"]["url"].startswith("data:image/png;base64,")
        assert encoded in result["image_url"]["url"]

    def test_translate_attachment_url_backed_image_jpeg(self):
        """URL-backed image/jpeg passes through as-is."""
        attachment = FileAttachment(
            url="https://example.com/photo.jpg", mime_type="image/jpeg"
        )
        result = _translate_chat_attachment(attachment)
        assert result["type"] == "image_url"
        assert result["image_url"]["url"] == "https://example.com/photo.jpg"

    def test_translate_attachment_file_id_only_raises_value_error(self):
        """file_id-only attachment raises ValueError — no upload/cache mapping."""
        attachment = FileAttachment(file_id="file-abc123", mime_type="image/png")
        with pytest.raises(ValueError, match="file_id"):
            _translate_chat_attachment(attachment)

    def test_translate_attachment_non_image_mime_raises_value_error(self):
        """Non-image MIME type raises ValueError."""
        attachment = FileAttachment(
            url="https://example.com/doc.pdf", mime_type="application/pdf"
        )
        with pytest.raises(ValueError, match="image"):
            _translate_chat_attachment(attachment)

    # ── _translate_chat_content_part ──────────────────────────────────────

    def test_translate_content_part_text(self):
        """Text ContentPart maps to a Chat Completions text part."""
        part = ContentPart(type="text", text="Hello world")
        result = _translate_chat_content_part(part)
        assert result == {"type": "text", "text": "Hello world"}

    def test_translate_content_part_file_delegates_to_attachment(self):
        """File ContentPart delegates to _translate_chat_attachment."""
        encoded = base64.b64encode(b"fake_image_data").decode("ascii")
        part = ContentPart(
            type="file", file=FileAttachment(data=encoded, mime_type="image/png")
        )
        result = _translate_chat_content_part(part)
        assert result["type"] == "image_url"
        assert "data:image/png;base64," in result["image_url"]["url"]

    def test_translate_content_part_file_none_raises_value_error(self):
        """ContentPart with type='file' and file=None raises ValueError."""
        part = ContentPart.model_construct(type="file", file=None)
        with pytest.raises(ValueError, match="file"):
            _translate_chat_content_part(part)

    # ── _translate_chat_user_message ──────────────────────────────────────

    def test_translate_user_message_plain_string_no_attachments(self):
        """String content without attachments passes through unchanged."""
        msg: dict[str, object] = {"role": "user", "content": "Hello"}
        result = _translate_chat_user_message(msg)
        assert result == {"role": "user", "content": "Hello"}

    def test_translate_user_message_string_with_attachments(self):
        """String content with attachments produces text + image parts."""
        encoded = base64.b64encode(b"img").decode("ascii")
        attachment = FileAttachment(data=encoded, mime_type="image/png")
        msg: dict[str, object] = {
            "role": "user",
            "content": "Describe this",
            "attachments": [attachment],
        }
        result = _translate_chat_user_message(msg)
        assert result["role"] == "user"
        assert "attachments" not in result
        content = result["content"]
        assert isinstance(content, list)
        assert len(content) == 2
        assert content[0] == {"type": "text", "text": "Describe this"}
        assert content[1]["type"] == "image_url"
        assert "data:image/png;base64," in content[1]["image_url"]["url"]

    def test_translate_user_message_content_parts_preserves_order(self):
        """list[ContentPart] preserves caller-specified order."""
        encoded = base64.b64encode(b"img1").decode("ascii")
        parts = [
            ContentPart(type="text", text="Part A"),
            ContentPart(
                type="file",
                file=FileAttachment(data=encoded, mime_type="image/png"),
            ),
            ContentPart(type="text", text="Part B"),
        ]
        msg: dict[str, object] = {"role": "user", "content": parts}
        result = _translate_chat_user_message(msg)
        assert result["role"] == "user"
        content = result["content"]
        assert len(content) == 3
        assert content[0] == {"type": "text", "text": "Part A"}
        assert content[1]["type"] == "image_url"
        assert content[2] == {"type": "text", "text": "Part B"}

    def test_translate_user_message_with_dict_content_part(self):
        """Dict-form ContentPart items are coerced correctly."""
        msg: dict[str, object] = {
            "role": "user",
            "content": [{"type": "text", "text": "hello from dict"}],
        }
        result = _translate_chat_user_message(msg)
        assert result["content"] == [{"type": "text", "text": "hello from dict"}]

    def test_translate_user_message_content_parts_plus_attachments(self):
        """list[ContentPart] + attachments: content parts first, then attachments."""
        cp_encoded = base64.b64encode(b"cp").decode("ascii")
        att_encoded = base64.b64encode(b"att").decode("ascii")
        parts = [
            ContentPart(
                type="file",
                file=FileAttachment(data=cp_encoded, mime_type="image/png"),
            ),
        ]
        attachments = [
            FileAttachment(data=att_encoded, mime_type="image/jpeg"),
        ]
        msg: dict[str, object] = {
            "role": "user",
            "content": parts,
            "attachments": attachments,
        }
        result = _translate_chat_user_message(msg)
        content = result["content"]
        assert len(content) == 2
        # content part first
        assert "data:image/png;base64," in content[0]["image_url"]["url"]
        # attachment part second
        assert "data:image/jpeg;base64," in content[1]["image_url"]["url"]

    def test_translate_user_message_empty_attachments_list(self):
        """Empty attachments list: same as no attachments."""
        msg: dict[str, object] = {
            "role": "user",
            "content": "Hello",
            "attachments": [],
        }
        result = _translate_chat_user_message(msg)
        assert result == {"role": "user", "content": "Hello"}

    def test_translate_user_message_multiple_attachments_order_preserved(self):
        """Multiple attachments preserve caller order."""
        encoded1 = base64.b64encode(b"img1").decode("ascii")
        encoded2 = base64.b64encode(b"img2").decode("ascii")
        attachments = [
            FileAttachment(data=encoded1, mime_type="image/png", filename="first"),
            FileAttachment(data=encoded2, mime_type="image/jpeg", filename="second"),
        ]
        msg: dict[str, object] = {
            "role": "user",
            "content": "Compare these",
            "attachments": attachments,
        }
        result = _translate_chat_user_message(msg)
        content = result["content"]
        assert len(content) == 3
        assert content[0] == {"type": "text", "text": "Compare these"}
        assert "data:image/png;base64," in content[1]["image_url"]["url"]
        assert "data:image/jpeg;base64," in content[2]["image_url"]["url"]

    def test_translate_user_message_empty_content_list_raises_value_error(self):
        """Empty list[ContentPart] raises ValueError."""
        msg: dict[str, object] = {"role": "user", "content": []}
        with pytest.raises(ValueError, match="content"):
            _translate_chat_user_message(msg)

    def test_translate_user_message_empty_string_with_attachments(self):
        """Empty string content with attachments omits text part."""
        encoded = base64.b64encode(b"img").decode("ascii")
        attachment = FileAttachment(data=encoded, mime_type="image/png")
        msg: dict[str, object] = {
            "role": "user",
            "content": "",
            "attachments": [attachment],
        }
        result = _translate_chat_user_message(msg)
        content = result["content"]
        assert len(content) == 1
        assert content[0]["type"] == "image_url"


class TestChatCompletionsAttachmentIntegration:
    """End-to-end tests for _translate_chat_messages() with attachments."""

    @pytest.fixture
    def client(self) -> OpenAIChatCompletionsClient:
        return OpenAIChatCompletionsClient(LanguageModel(model_name="gpt-4o-mini"))

    def test_translate_messages_multipart_user_with_system_and_assistant(
        self, client: OpenAIChatCompletionsClient
    ):
        """Multipart user message translates correctly alongside system/assistant."""
        encoded = base64.b64encode(b"img").decode("ascii")
        parts = [
            ContentPart(type="text", text="Look at this"),
            ContentPart(
                type="file",
                file=FileAttachment(data=encoded, mime_type="image/png"),
            ),
        ]
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": parts},
            {"role": "assistant", "content": "I see an image."},
        ]
        result = client._translate_chat_messages(messages)
        assert len(result) == 3
        # system unchanged
        assert result[0] == {"role": "system", "content": "You are helpful."}
        # user has multimodal content
        assert result[1]["role"] == "user"
        assert isinstance(result[1]["content"], list)
        assert result[1]["content"][0]["type"] == "text"
        assert result[1]["content"][1]["type"] == "image_url"
        # assistant unchanged
        assert result[2] == {"role": "assistant", "content": "I see an image."}

    def test_translate_messages_string_only_other_roles_unchanged(
        self, client: OpenAIChatCompletionsClient
    ):
        """String-only messages for non-user roles remain unchanged."""
        messages = [
            {"role": "system", "content": "You are a bot."},
            {"role": "assistant", "content": "Hello user."},
        ]
        result = client._translate_chat_messages(messages)
        assert result == messages

    def test_translate_messages_tool_result_and_prior_tool_calls_unchanged(
        self, client: OpenAIChatCompletionsClient
    ):
        """Tool-result and assistant-with-tool_calls paths remain unchanged."""
        client._prior_tool_calls = {
            "call_1": {
                "id": "call_1",
                "type": "function",
                "function": {"name": "lookup", "arguments": "{}"},
            },
        }
        messages = [
            {"role": "user", "content": "lookup time"},
            {"role": "tool_result", "call_id": "call_1", "content": "12:00"},
        ]
        result = client._translate_chat_messages(messages)
        # Should still produce the assistant injection + tool mapping
        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[2]["role"] == "tool"

    def test_translate_messages_user_with_attachments_via_dict(
        self, client: OpenAIChatCompletionsClient
    ):
        """User message dict with attachments is translated end-to-end."""
        encoded = base64.b64encode(b"img").decode("ascii")
        attachment = FileAttachment(data=encoded, mime_type="image/png")
        messages = [
            {"role": "system", "content": "You are helpful."},
            {
                "role": "user",
                "content": "Describe this image.",
                "attachments": [attachment],
            },
            {"role": "assistant", "content": "OK"},
        ]
        result = client._translate_chat_messages(messages)
        assert len(result) == 3
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"
        assert isinstance(result[1]["content"], list)
        assert "attachments" not in result[1]
        assert result[1]["content"][0] == {
            "type": "text",
            "text": "Describe this image.",
        }
        assert result[1]["content"][1]["type"] == "image_url"
        assert result[2]["role"] == "assistant"


def _mock_chunk(delta, finish_reason=None, usage=None):
    data = {
        "id": "chatcmpl_1",
        "model": "gpt-4o-mini",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    if usage is not None:
        data["usage"] = usage
    return MagicMock(model_dump=lambda: data)


async def async_iter(items):
    for item in items:
        yield item
