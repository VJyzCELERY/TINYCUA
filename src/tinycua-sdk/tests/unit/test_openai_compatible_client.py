"""Unit and contract tests for the refactored OpenAICompatibleClient.

Verifies that OpenAICompatibleClient:
- Instantiates from LanguageModel and implements _chat_impl()
- Resolves through ProviderRegistry.create_client()
- Non-streaming chat() returns correct LLMResponse shape
- Streaming chat() yields canonical LLMEvent items
- raw_events=True with stream=False raises ValueError via base class
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from tinycua_sdk.agent.events import ToolResultMessage, UserMessage
from tinycua_sdk.agent.llm_client import LLMClient, OpenAICompatibleClient
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.core.providers import ProviderInfo, ProviderRegistry

from tests.conftest import FakeLLMResponse


class TestOpenAICompatibleClient:
    """OpenAICompatibleClient contract tests."""

    def test_instantiation_from_language_model(self) -> None:
        """Client can be instantiated from a LanguageModel config."""
        model = LanguageModel(
            provider="openai-responses",
            model_name="gpt-4o-mini",
            base_url="https://api.openai.com/v1",
        )
        client = OpenAICompatibleClient(model)
        assert isinstance(client, LLMClient)
        assert client._model_config is model

    def test_implements_chat_impl(self) -> None:
        """Client implements the abstract _chat_impl method."""
        model = LanguageModel(model_name="gpt-4o-mini")
        client = OpenAICompatibleClient(model)
        # _chat_impl should be a coroutine function (abstract method resolved)
        assert hasattr(client, "_chat_impl")
        import inspect
        assert inspect.iscoroutinefunction(client._chat_impl)

    def test_resolves_through_registry(self) -> None:
        """Client can be resolved through ProviderRegistry.create_client()."""
        registry = ProviderRegistry()

        def factory(cfg: LanguageModel) -> OpenAICompatibleClient:
            return OpenAICompatibleClient(cfg)

        registry.register(
            "openai-responses",
            factory,
            ProviderInfo(id="openai-responses", factory=factory, description=""),
        )

        model = LanguageModel(provider="openai-responses", model_name="gpt-4o-mini")
        client = registry.create_client(model)
        assert isinstance(client, OpenAICompatibleClient)

    def test_resolves_through_default_registry(self) -> None:
        """Client resolves through the default singleton registry."""
        from tinycua_sdk.core.providers import get_provider_registry

        registry = get_provider_registry()
        model = LanguageModel(provider="openai-responses", model_name="gpt-4o-mini")
        client = registry.create_client(model)
        assert isinstance(client, OpenAICompatibleClient)

    @pytest.mark.asyncio
    async def test_non_streaming_chat_returns_llm_response(self) -> None:
        """Non-streaming chat returns correct LLMResponse shape."""
        model = LanguageModel(model_name="gpt-4o-mini")
        client = OpenAICompatibleClient(model)

        fake_response_data = {
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Hello!", "annotations": []}],
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }

        mock_post = AsyncMock()
        mock_post.return_value = FakeLLMResponse(json_data=fake_response_data)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(httpx.AsyncClient, "post", mock_post)
            result = await client.chat(
                messages=[UserMessage(role="user", content="Hi")],
                tools=None,
            )

        assert isinstance(result, dict)
        assert result["content"] == "Hello!"
        assert result["tool_calls"] is None
        assert result["usage"] == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        assert result["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_streaming_chat_yields_events(self) -> None:
        """Streaming chat yields canonical LLMEvent items."""
        model = LanguageModel(model_name="gpt-4o-mini")
        client = OpenAICompatibleClient(model)

        fake_sse_lines = [
            'data: {"type":"response.output_text.delta","delta":"Hello","item_id":"1"}\n',
            'data: {"type":"response.completed","finish_reason":"completed"}\n',
            "data: [DONE]\n",
        ]

        async def fake_aiter_lines():
            for line in fake_sse_lines:
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

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                httpx.AsyncClient,
                "stream",
                MagicMock(return_value=FakeStreamResponse()),
            )
            stream = await client.chat(
                messages=[UserMessage(role="user", content="hi")],
                tools=None,
                stream=True,
            )

            chunks = [c async for c in stream]

        assert len(chunks) >= 1
        # First event should be a delta
        assert chunks[0]["type"] in ("response.output_text.delta",)

    @pytest.mark.asyncio
    async def test_raw_events_requires_stream(self) -> None:
        """raw_events=True with stream=False raises ValueError from base class."""
        model = LanguageModel(model_name="test")
        client = OpenAICompatibleClient(model)

        with pytest.raises(ValueError, match="raw_events=True requires stream=True"):
            await client.chat(
                messages=[UserMessage(role="user", content="hi")],
                raw_events=True,
            )


class TestPreviousResponseId:
    """Tests for OpenAI Responses tool-result continuation (previous_response_id)."""

    def test_build_payload_no_previous_response_id(self) -> None:
        """Payload omits previous_response_id when none is provided."""
        model = LanguageModel(model_name="gpt-4o-mini")
        messages: list[dict] = [{"role": "user", "content": "Hello"}]
        payload = OpenAICompatibleClient._build_payload(
            messages, None, model, previous_response_id=None,
        )
        assert "previous_response_id" not in payload

    def test_build_payload_with_previous_id_and_tool_results(self) -> None:
        """Payload includes previous_response_id when provided with tool results."""
        model = LanguageModel(model_name="gpt-4o-mini")
        messages: list[dict] = [
            {"role": "tool_result", "call_id": "call_123", "content": "42"},
        ]
        payload = OpenAICompatibleClient._build_payload(
            messages, None, model, previous_response_id="resp_abc123",
        )
        assert payload.get("previous_response_id") == "resp_abc123"
        assert any(
            i.get("type") == "function_call_output" for i in payload["input"]
        )

    def test_build_payload_with_previous_id_no_tool_results(self) -> None:
        """Payload omits previous_response_id when there are no function_call_output items."""
        model = LanguageModel(model_name="gpt-4o-mini")
        messages: list[dict] = [{"role": "user", "content": "Follow up"}]
        payload = OpenAICompatibleClient._build_payload(
            messages, None, model, previous_response_id="resp_def456",
        )
        # No function_call_output in the translated input, so previous_response_id
        # should NOT be included even though it was provided.
        assert "previous_response_id" not in payload

    @pytest.mark.asyncio
    async def test_non_streaming_captures_response_id(self) -> None:
        """Non-streaming chat captures response id for continuation state."""
        model = LanguageModel(model_name="gpt-4o-mini")
        client = OpenAICompatibleClient(model)
        assert client._previous_response_id is None

        fake_response_data = {
            "id": "resp_test123",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Got it!", "annotations": []}],
                }
            ],
            "usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
        }

        mock_post = AsyncMock()
        mock_post.return_value = FakeLLMResponse(json_data=fake_response_data)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(httpx.AsyncClient, "post", mock_post)
            await client.chat(
                messages=[UserMessage(role="user", content="Hi")],
                tools=None,
            )

        assert client._previous_response_id == "resp_test123"

    @pytest.mark.asyncio
    async def test_non_streaming_passes_previous_id_to_next_call(self) -> None:
        """After one non-streaming call, the next call includes previous_response_id in the payload."""
        model = LanguageModel(model_name="gpt-4o-mini")
        client = OpenAICompatibleClient(model)

        # First call returns a response with id
        first_response_data = {
            "id": "resp_first",
            "output": [
                {
                    "type": "function_call",
                    "id": "fc_1",
                    "call_id": "call_1",
                    "name": "get_weather",
                    "arguments": '{"city": "Tokyo"}',
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }
        # Second call returns a response with id (what we send is what matters)
        second_response_data = {
            "id": "resp_second",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Sunny!", "annotations": []}],
                }
            ],
            "usage": {"input_tokens": 15, "output_tokens": 5, "total_tokens": 20},
        }

        call_count = 0
        sent_payloads: list[dict] = []

        async def mock_post_side_effect(url, json=None, **kwargs):
            nonlocal call_count
            sent_payloads.append(json)
            call_count += 1
            if call_count == 1:
                return FakeLLMResponse(json_data=first_response_data)
            return FakeLLMResponse(json_data=second_response_data)

        mock_post = AsyncMock(side_effect=mock_post_side_effect)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(httpx.AsyncClient, "post", mock_post)
            # First call — no previous_response_id
            await client.chat(
                messages=[UserMessage(role="user", content="Weather?")],
                tools=None,
            )
            # Second call — with tool_result, should include previous_response_id
            await client.chat(
                messages=[
                    ToolResultMessage(role="tool_result", call_id="call_1", content="Sunny"),
                ],
                tools=None,
            )

        assert len(sent_payloads) == 2
        # First payload should NOT have previous_response_id
        assert "previous_response_id" not in sent_payloads[0]
        # Second payload SHOULD have previous_response_id from first response
        assert sent_payloads[1].get("previous_response_id") == "resp_first"
        assert any(
            i.get("type") == "function_call_output" for i in sent_payloads[1].get("input", [])
        )
