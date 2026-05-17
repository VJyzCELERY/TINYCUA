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

from tinycua_sdk.agent.events import LLMResponse
from tinycua_sdk.agent.llm_client import LLMClient, OpenAICompatibleClient
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.core.exceptions import ProviderNotSupportedError
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
                messages=[{"role": "user", "content": "Hi"}],  # type: ignore[arg-type]
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
                messages=[{"role": "user", "content": "hi"}],  # type: ignore[arg-type]
                tools=None,
                stream=True,
            )

            chunks = [c async for c in stream]

        assert len(chunks) >= 1
        # First event should be a delta
        assert chunks[0]["type"] in ("content.delta",)

    @pytest.mark.asyncio
    async def test_raw_events_requires_stream(self) -> None:
        """raw_events=True with stream=False raises ValueError from base class."""
        model = LanguageModel(model_name="test")
        client = OpenAICompatibleClient(model)

        with pytest.raises(ValueError, match="raw_events=True requires stream=True"):
            await client.chat(
                messages=[{"role": "user", "content": "hi"}],  # type: ignore[arg-type]
                raw_events=True,
            )
