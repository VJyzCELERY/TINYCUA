"""Unit tests for Chat Completions request/response behavior.

Tests payload translation, non-streaming/streaming normalization,
tool-call accumulation, error mapping, and raw-events pairing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from tinycua_sdk.agent.events import LLMResponse
from tinycua_sdk.agent.llm_client import OpenAIChatCompletionsClient
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.core.exceptions import ProviderApiError, ProviderAuthError


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
