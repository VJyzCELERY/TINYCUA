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
@pytest.mark.provider("openai-chat-completions")
@pytest.mark.asyncio
async def test_openai_chat_completions_attachment_sends_image():
    """A user message with a multi-color image FileAttachment is sent through
    the Chat Completions provider and receives an assistant response.

    This is the FR-011 acceptance test. It exercises the full provider
    request path (chat()) and is guarded by environment configuration so
    it auto-skips when no LLM server is reachable.

    The fixture is a 4x4 RGBA PNG with red, green, blue, and yellow
    quadrants. Vision-capable models should identify some of these colors;
    non-vision models that refuse the input should produce a refusal
    keyword. Both paths pass deterministically.
    """
    from tests.integration.conftest import resolve_integration_llm_config

    # Keywords that indicate a non-vision model rejected the image input
    _NO_VISION_KEYWORDS = (
        "unable",
        "can't view",
        "cannot view",
        "no vision",
        "image input not supported",
    )
    # Color keywords expected from the multi-color fixture
    _COLOR_KEYWORDS = ("red", "green", "blue", "yellow")

    config = resolve_integration_llm_config("openai-chat-completions")

    # Build a LanguageModel with the resolved config
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name=config.model,
        base_url=config.base_url,
        api_key=config.api_key,
    )

    # Also set environment variables so _get_client() works
    old_base_url = os.environ.get("OPENAI_CHAT_COMPLETIONS_BASE_URL")
    old_api_key = os.environ.get("OPENAI_CHAT_COMPLETIONS_API_KEY")
    os.environ["OPENAI_CHAT_COMPLETIONS_BASE_URL"] = config.base_url
    os.environ["OPENAI_CHAT_COMPLETIONS_API_KEY"] = config.api_key

    try:
        client = OpenAIChatCompletionsClient(model)
        image_attachment = FileAttachment.from_path("tests/fixtures/test_image.png")
        message = UserMessage(
            role="user",
            content=(
                "What colors do you see in the attached image? "
                "List only the color names."
            ),
            attachments=[image_attachment],
        )

        response = await client.chat(messages=[message])

        assert response["content"] is not None
        assert isinstance(response["content"], str)
        assert len(response["content"]) > 0

        lower = response["content"].lower()

        no_vision = any(kw in lower for kw in _NO_VISION_KEYWORDS)
        has_colors = any(kw in lower for kw in _COLOR_KEYWORDS)

        assert no_vision or has_colors, (
            f"Expected vision model color keywords {_COLOR_KEYWORDS} or "
            f"non-vision refusal keywords {_NO_VISION_KEYWORDS}, "
            f"got: {response['content']!r}"
        )
    finally:
        _restore_env("OPENAI_CHAT_COMPLETIONS_BASE_URL", old_base_url)
        _restore_env("OPENAI_CHAT_COMPLETIONS_API_KEY", old_api_key)


def _restore_env(key: str, old_val: str | None) -> None:
    """Restore an env var to its previous value or delete it."""
    if old_val is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = old_val
