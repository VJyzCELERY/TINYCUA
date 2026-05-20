"""Unit tests for canonical SSE event schema and input types.

Validates TypedDict shapes, imports, and discriminated union narrowing
by ``type`` field.
"""

import typing

from tinycua_sdk.agent.events import (
    AssistantMessage,
    ContentDeltaEvent,
    ContentDoneEvent,
    LLMEvent,
    LLMMessage,
    LLMResponse,
    LLMToolSpec,
    RawSseEvent,
    ResponseCompletedEvent,
    ResponseFailedEvent,
    ResponseUsageEvent,
    SystemMessage,
    TokenUsage,
    ToolCallArgumentsDeltaEvent,
    ToolCallArgumentsDoneEvent,
    ToolCallReadyEvent,
    ToolCallStartedEvent,
    ToolResultMessage,
    UserMessage,
)
from tinycua_sdk.models import ContentPart, FileAttachment


class TestCanonicalEventShapes:
    """TypedDict shapes for canonical SSE events."""

    def test_content_delta_event_shape(self) -> None:
        event: ContentDeltaEvent = {
            "type": "response.output_text.delta",
            "delta": "Hello",
            "index": 0,
        }
        assert event["type"] == "response.output_text.delta"
        assert event["delta"] == "Hello"
        assert event["index"] == 0

    def test_content_done_event_shape(self) -> None:
        event: ContentDoneEvent = {
            "type": "response.output_text.done",
            "index": 0,
        }
        assert event["type"] == "response.output_text.done"
        assert event["index"] == 0

    def test_tool_call_started_event_shape(self) -> None:
        event: ToolCallStartedEvent = {
            "type": "response.output_item.added",
            "id": "call_1",
            "call_id": "call_1",
            "name": "get_weather",
        }
        assert event["type"] == "response.output_item.added"
        assert event["id"] == "call_1"
        assert event["name"] == "get_weather"

    def test_tool_call_arguments_delta_event_shape(self) -> None:
        event: ToolCallArgumentsDeltaEvent = {
            "type": "response.function_call_arguments.delta",
            "id": "call_1",
            "arguments": '{"city": "Tokyo"}',
        }
        assert event["type"] == "response.function_call_arguments.delta"

    def test_tool_call_arguments_done_event_shape(self) -> None:
        event: ToolCallArgumentsDoneEvent = {
            "type": "response.function_call_arguments.done",
            "id": "call_1",
            "call_id": "call_1",
            "name": "get_weather",
            "arguments": '{"city": "Tokyo"}',
        }
        assert event["type"] == "response.function_call_arguments.done"

    def test_tool_call_ready_event_shape(self) -> None:
        event: ToolCallReadyEvent = {
            "type": "tool_call.ready",
            "id": "call_1",
            "call_id": "call_1",
            "name": "get_weather",
            "arguments": '{"city": "Tokyo"}',
        }
        assert event["type"] == "tool_call.ready"

    def test_token_usage_shape(self) -> None:
        usage: TokenUsage = {
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        }
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 5
        assert usage["total_tokens"] == 15

    def test_token_usage_none_fields(self) -> None:
        usage: TokenUsage = {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }
        assert usage["input_tokens"] is None

    def test_response_usage_event_shape(self) -> None:
        event: ResponseUsageEvent = {
            "type": "response.usage",
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }
        assert event["type"] == "response.usage"
        assert event["usage"]["total_tokens"] == 15

    def test_response_completed_event_shape(self) -> None:
        event: ResponseCompletedEvent = {
            "type": "response.completed",
            "finish_reason": "stop",
        }
        assert event["type"] == "response.completed"
        assert event["finish_reason"] == "stop"

    def test_response_failed_event_shape(self) -> None:
        event: ResponseFailedEvent = {
            "type": "response.failed",
            "error": {"message": "API error"},
        }
        assert event["type"] == "response.failed"
        assert event["error"]["message"] == "API error"

    def test_llm_response_shape(self) -> None:
        response: LLMResponse = {
            "content": "Hello!",
            "tool_calls": None,
            "usage": None,
            "finish_reason": "stop",
            "model": "gpt-4o",
        }
        assert response["content"] == "Hello!"
        assert response["finish_reason"] == "stop"
        assert response["model"] == "gpt-4o"

    def test_llm_response_with_tool_calls(self) -> None:
        response: LLMResponse = {
            "content": None,
            "tool_calls": [
                {"id": "call_1", "call_id": "call_1", "name": "get_weather", "arguments": "{}"}
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            "finish_reason": "tool_calls",
            "model": "gpt-4o",
        }
        assert response["tool_calls"] is not None
        assert len(response["tool_calls"]) == 1

    def test_raw_sse_event_shape(self) -> None:
        event: RawSseEvent = {
            "provider": "openai",
            "raw_event": {"type": "response.created"},
        }
        assert event["provider"] == "openai"


class TestCanonicalInputTypes:
    """Canonical input message types."""

    def test_system_message_shape(self) -> None:
        msg: SystemMessage = {"role": "system", "content": "You are helpful."}
        assert msg["role"] == "system"

    def test_user_message_shape(self) -> None:
        msg: UserMessage = {"role": "user", "content": "Hello"}
        assert msg["role"] == "user"

    def test_assistant_message_shape(self) -> None:
        msg: AssistantMessage = {"role": "assistant", "content": "Hi there!"}
        assert msg["role"] == "assistant"

    def test_assistant_message_none_content(self) -> None:
        msg: AssistantMessage = {"role": "assistant", "content": None}
        assert msg["content"] is None

    def test_tool_result_message_shape(self) -> None:
        msg: ToolResultMessage = {
            "role": "tool_result",
            "call_id": "call_1",
            "content": '{"temperature": 22}',
        }
        assert msg["role"] == "tool_result"
        assert msg["call_id"] == "call_1"

    def test_llm_tool_spec_shape(self) -> None:
        spec: LLMToolSpec = {
            "name": "get_weather",
            "description": "Get the weather",
            "parameters": {"type": "object", "properties": {}},
        }
        assert spec["name"] == "get_weather"
        assert spec["description"] == "Get the weather"
        assert "type" in spec["parameters"]


class TestLLMEventNarrowing:
    """Test LLMEvent union can be narrowed by type field."""

    def test_narrow_content_delta(self) -> None:
        event: LLMEvent = {"type": "response.output_text.delta", "delta": "Hello", "index": 0}
        assert event["type"] == "response.output_text.delta"
        if event["type"] == "response.output_text.delta":
            assert event["delta"] == "Hello"
            assert event["index"] == 0

    def test_narrow_response_completed(self) -> None:
        event: LLMEvent = {"type": "response.completed", "finish_reason": "stop"}
        assert event["type"] == "response.completed"
        if event["type"] == "response.completed":
            assert event["finish_reason"] == "stop"

    def test_narrow_tool_call_started(self) -> None:
        event: LLMEvent = {
            "type": "response.output_item.added",
            "id": "call_1",
            "call_id": "call_1",
            "name": "get_weather",
        }
        assert event["type"] == "response.output_item.added"
        if event["type"] == "response.output_item.added":
            assert event["name"] == "get_weather"


class TestLLMMessageNarrowing:
    """Test LLMMessage union can be narrowed by role field."""

    def test_narrow_user_message(self) -> None:
        msg: LLMMessage = {"role": "user", "content": "Hello"}
        assert msg["role"] == "user"
        if msg["role"] == "user":
            assert msg["content"] == "Hello"

    def test_narrow_system_message(self) -> None:
        msg: LLMMessage = {"role": "system", "content": "Instructions"}
        assert msg["role"] == "system"
        if msg["role"] == "system":
            assert msg["content"] == "Instructions"

    def test_narrow_tool_result(self) -> None:
        msg: LLMMessage = {
            "role": "tool_result",
            "call_id": "call_1",
            "content": "result",
        }
        assert msg["role"] == "tool_result"
        if msg["role"] == "tool_result":
            assert msg["call_id"] == "call_1"


class TestWidenedMessageContent:
    """UserMessage and ToolResultMessage now accept structured content parts."""

    def test_user_message_accepts_string(self) -> None:
        """UserMessage still accepts a plain string."""
        msg: UserMessage = {"role": "user", "content": "Hello"}
        assert msg["content"] == "Hello"

    def test_user_message_accepts_content_parts(self) -> None:
        """UserMessage now accepts list[ContentPart]."""
        parts = [
            ContentPart(type="text", text="What is this?"),
            ContentPart(type="file", file=FileAttachment.from_url(
                "https://example.com/img.png", "image/png"
            )),
        ]
        msg: UserMessage = {"role": "user", "content": parts}
        assert len(msg["content"]) == 2
        assert msg["content"][0].text == "What is this?"
        assert msg["content"][1].file is not None

    def test_tool_result_message_accepts_string(self) -> None:
        """ToolResultMessage still accepts a plain string."""
        msg: ToolResultMessage = {
            "role": "tool_result",
            "call_id": "call_1",
            "content": '{"result": "ok"}',
        }
        assert msg["content"] == '{"result": "ok"}'

    def test_tool_result_message_accepts_content_parts(self) -> None:
        """ToolResultMessage now accepts list[ContentPart]."""
        parts = [ContentPart(type="text", text="Done.")]
        msg: ToolResultMessage = {
            "role": "tool_result",
            "call_id": "call_2",
            "content": parts,
        }
        assert len(msg["content"]) == 1
        assert msg["content"][0].text == "Done."

    def test_user_message_content_type_hints_union(self) -> None:
        """UserMessage.__annotations__['content'] resolves to str | list[ContentPart]."""
        hints = typing.get_type_hints(UserMessage)
        content_type = hints["content"]
        args = typing.get_args(content_type)
        assert str in args
        assert list[ContentPart] in args

    def test_tool_result_message_content_type_hints_union(self) -> None:
        """ToolResultMessage.__annotations__['content'] resolves to str | list[ContentPart]."""
        hints = typing.get_type_hints(ToolResultMessage)
        content_type = hints["content"]
        args = typing.get_args(content_type)
        assert str in args
        assert list[ContentPart] in args



