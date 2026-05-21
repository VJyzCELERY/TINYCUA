"""Integration tests for the OpenAI Chat Completions provider."""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from tinycua_sdk.agent.events import UserMessage
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.models.attachment import FileAttachment
from tinycua_sdk.providers.open_ai_chat_completions import OpenAIChatCompletionsClient
from tinycua_sdk.providers.open_ai_responses import OpenAIResponsesClient
from tinycua_sdk.providers.registry import get_provider_registry


@pytest.mark.asyncio
async def test_openai_chat_completions_provider_resolves():
    """provider='openai-chat-completions' creates OpenAIChatCompletionsClient."""
    registry = get_provider_registry()
    assert registry.is_supported("openai-chat-completions")
    assert registry.is_supported("openai")
    assert registry.is_supported("openai-responses")

    chat_client = registry.create_client(
        LanguageModel(provider="openai-chat-completions", model_name="gpt-4o"),
    )
    responses_client = registry.create_client(
        LanguageModel(provider="openai-responses", model_name="gpt-4o"),
    )

    assert isinstance(chat_client, OpenAIChatCompletionsClient)
    assert not isinstance(chat_client, OpenAIResponsesClient)
    assert isinstance(responses_client, OpenAIResponsesClient)


@pytest.mark.asyncio
async def test_openai_chat_non_streaming_normalizes_response():
    """Non-streaming Chat Completions responses normalize to LLMResponse."""
    client = OpenAIChatCompletionsClient(LanguageModel(provider="openai-chat-completions", model_name="gpt-4o"))
    sdk = MagicMock()
    sdk.chat.completions.create = AsyncMock(return_value=MagicMock(model_dump=lambda: {
        "model": "gpt-4o",
        "choices": [{
            "message": {"role": "assistant", "content": "Hello!", "tool_calls": None},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    }))
    client._client = sdk

    response = await client.chat([UserMessage(role="user", content="Hello")])

    assert response["content"] == "Hello!"
    assert response["finish_reason"] == "stop"
    assert response["usage"]["input_tokens"] == 3
    assert response["usage"]["output_tokens"] == 2
    sdk.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_openai_chat_streaming_tool_calls_emit_ready_once():
    """Streaming tool deltas accumulate into exactly one ready event."""
    client = OpenAIChatCompletionsClient(LanguageModel(provider="openai-chat-completions", model_name="gpt-4o"))
    stream = _mock_chat_stream([
        _chunk({"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": "lookup", "arguments": "{\"q\":"}}]}),
        _chunk({"tool_calls": [{"index": 0, "function": {"arguments": "\"time\"}"}}]}),
        _chunk({}, finish_reason="tool_calls"),
    ])
    sdk = MagicMock()
    sdk.chat.completions.create = AsyncMock(return_value=stream)
    client._client = sdk

    result = await client.chat(
        [UserMessage(role="user", content="What time is it?")],
        tools=[{"name": "lookup", "description": "Lookup", "parameters": {"type": "object"}}],
        stream=True,
    )
    events = [event async for event in result]

    assert [event["type"] for event in events].count("tool_call.ready") == 1
    ready = next(event for event in events if event["type"] == "tool_call.ready")
    assert ready["call_id"] == "call_1"
    assert ready["name"] == "lookup"
    assert ready["arguments"] == '{"q":"time"}'


@pytest.mark.asyncio
async def test_openai_chat_raw_events_pair_canonical_with_sdk_chunks():
    """raw_events=True preserves the original ChatCompletionChunk object."""
    client = OpenAIChatCompletionsClient(LanguageModel(provider="openai-chat-completions", model_name="gpt-4o"))
    raw_chunk = _chunk({"content": "Hi"})
    sdk = MagicMock()
    sdk.chat.completions.create = AsyncMock(return_value=_mock_chat_stream([raw_chunk]))
    client._client = sdk

    result = await client.chat(
        [UserMessage(role="user", content="Hello")],
        stream=True,
        raw_events=True,
    )
    pairs = [pair async for pair in result]

    assert pairs[0][0]["type"] == "response.created"
    assert pairs[0][1]["provider"] == "openai-chat-completions"
    assert pairs[0][1]["raw_event"] is raw_chunk
    assert pairs[1][0]["type"] == "response.output_text.delta"
    assert pairs[1][1] is None


@pytest.mark.asyncio
async def test_openai_chat_raw_events_one_to_many_pairing():
    """One chunk producing >=2 canonical events: first gets raw, follow-on gets raw=None."""
    client = OpenAIChatCompletionsClient(LanguageModel(provider="openai-chat-completions", model_name="gpt-4o"))
    terminal_chunk = _chunk({"content": "Bye"}, finish_reason="stop", usage={"prompt_tokens": 5, "completion_tokens": 8})
    sdk = MagicMock()
    sdk.chat.completions.create = AsyncMock(return_value=_mock_chat_stream([terminal_chunk]))
    client._client = sdk

    result = await client.chat(
        [UserMessage(role="user", content="Hello")],
        stream=True,
        raw_events=True,
    )
    pairs = [pair async for pair in result]

    assert pairs[0][1] is not None
    assert pairs[0][1]["raw_event"] is terminal_chunk
    assert any(p[1] is None for p in pairs[1:]), "Expected at least one follow-on event with raw=None"


async def _mock_chat_stream(chunks):
    for chunk in chunks:
        yield chunk


def _chunk(delta, finish_reason=None, usage=None):
    data = {
        "id": "chatcmpl_1",
        "model": "gpt-4o",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    if usage is not None:
        data["usage"] = usage
    return MagicMock(model_dump=lambda: data)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_openai_chat_completions_attachment_sends_image():
    """A user message with an image FileAttachment is sent through the Chat
    Completions provider and receives a non-empty assistant response.

    This is the FR-011 acceptance test. It exercises the full provider
    request path (chat()) and is guarded by environment configuration so
    it auto-skips when no LLM server is reachable.
    """
    from tests.integration.conftest import resolve_integration_llm_config

    config = resolve_integration_llm_config()

    # Build a LanguageModel with the resolved config
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name=config.model,
        base_url=config.base_url,
        api_key=config.api_key,
    )

    # Also set environment variables so _get_client() works
    old_provider = os.environ.get("TINYCUA_PROVIDER")
    old_model = os.environ.get("TINYCUA_MODEL")
    old_base_url = os.environ.get("TINYCUA_BASE_URL")
    old_api_key = os.environ.get("TINYCUA_API_KEY")
    os.environ["TINYCUA_PROVIDER"] = "openai-chat-completions"
    os.environ["TINYCUA_MODEL"] = config.model
    os.environ["TINYCUA_BASE_URL"] = config.base_url
    os.environ["TINYCUA_API_KEY"] = config.api_key

    try:
        client = OpenAIChatCompletionsClient(model)
        image_attachment = FileAttachment.from_path("tests/fixtures/test_image.png")
        message = UserMessage(
            role="user",
            content="Describe this image in one sentence.",
            attachments=[image_attachment],
        )

        response = await client.chat(messages=[message])

        assert response["content"] is not None
        assert len(response["content"]) > 0
        assert isinstance(response["content"], str)
    finally:
        for key, old_val in (
            ("TINYCUA_PROVIDER", old_provider),
            ("TINYCUA_MODEL", old_model),
            ("TINYCUA_BASE_URL", old_base_url),
            ("TINYCUA_API_KEY", old_api_key),
        ):
            if old_val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_val
