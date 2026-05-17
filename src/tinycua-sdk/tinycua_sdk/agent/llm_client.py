"""LLM client ABC and OpenAI-compatible implementation.

Defines the canonical ``LLMClient`` abstract base class with a concrete
``chat()`` method that performs shared validation and delegates to the
abstract ``_chat_impl()``. Provider-specific subclasses implement
``_chat_impl()`` with their own streaming and non-streaming logic.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import httpx

from tinycua_sdk.agent.events import (
    LLMEvent,
    LLMResponse,
    RawSseEvent,
    ContentDeltaEvent,
    ContentDoneEvent,
    ToolCallArgumentsDeltaEvent,
    ToolCallArgumentsDoneEvent,
    ToolCallReadyEvent,
    ToolCallStartedEvent,
)
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.core.exceptions import ProviderApiError, ProviderAuthError
from tinycua_sdk.core.providers import normalize_base_url

if TYPE_CHECKING:
    from tinycua_sdk.agent.events import LLMMessage, LLMToolSpec


class LLMClient(ABC):
    """Abstract base for LLM API clients with canonical event contract.

    Subclasses must implement ``_chat_impl()`` and ``close()``.
    The concrete ``chat()`` method validates shared constraints
    (e.g. ``raw_events=True`` requires ``stream=True``) then delegates
    to ``_chat_impl()``.

    Tool-call state machine (canonical event flow)::

        tool_call.started  →  tool_call.arguments.delta*  →  tool_call.arguments.done  →  tool_call.ready

    """

    @abstractmethod
    async def _chat_impl(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        stream: bool = False,
        raw_events: bool = False,
    ) -> (
        LLMResponse
        | AsyncIterator[LLMEvent]
        | AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]
    ):
        """Provider-specific chat implementation.

        Args:
            messages: Canonical message list.
            tools: Optional list of tool specs.
            stream: When True, return an async iterator of stream events.
            raw_events: When True *and* stream=True, yield ``(canonical, raw)``
                tuples instead of bare ``LLMEvent`` items. Providers that
                do not support raw events ignore this flag.

        Returns:
            Non-streaming: ``LLMResponse``.
            Streaming with ``raw_events=False``: ``AsyncIterator[LLMEvent]``.
            Streaming with ``raw_events=True``: ``AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]``.
        """

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        *,
        stream: bool = False,
        raw_events: bool = False,
    ) -> (
        LLMResponse
        | AsyncIterator[LLMEvent]
        | AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]
    ):
        """Send a chat request with shared validation.

        Validates that ``raw_events=True`` requires ``stream=True``,
        then delegates to ``_chat_impl()``.

        Args:
            messages: Canonical message list.
            tools: Optional list of tool specs.
            stream: When True, return an async iterator of stream events.
            raw_events: When True *and* stream=True, yield ``(canonical, raw)``
                tuples from ``_chat_impl()``.

        Returns:
            Non-streaming: ``LLMResponse``.
            Streaming: ``AsyncIterator[LLMEvent]`` or paired tuples.
        """
        if raw_events and not stream:
            raise ValueError("raw_events=True requires stream=True")
        return await self._chat_impl(messages, tools, stream=stream, raw_events=raw_events)

    @abstractmethod
    async def close(self) -> None:
        """Close and release any resources held by the client."""


class OpenAICompatibleClient(LLMClient):
    """Client for OpenAI-compatible endpoints using httpx.

    Configuration is bound at construction via ``model_config``.
    All API calls use this fixed configuration — callers that need
    different settings create a new client via ``ProviderRegistry``.
    """

    def __init__(self, model_config: LanguageModel) -> None:
        self._model_config = model_config
        self._clients: dict[tuple[str, str], httpx.AsyncClient] = {}

    def _client_key(self, model_config: LanguageModel | None = None) -> tuple[str, str]:
        cfg = model_config or self._model_config
        api_key = cfg.api_key.get_secret_value()
        base_url = normalize_base_url(cfg.base_url, cfg.provider)
        return (base_url, api_key)

    def _get_client(self, model_config: LanguageModel | None = None) -> httpx.AsyncClient:
        cfg = model_config or self._model_config
        key = self._client_key(cfg)
        if key not in self._clients:
            api_key = key[1]
            headers: dict[str, str] = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            self._clients[key] = httpx.AsyncClient(
                base_url=key[0], headers=headers, timeout=60.0
            )
        return self._clients[key]

    async def close(self) -> None:
        """Close all cached HTTP clients and clear the cache."""
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

    @staticmethod
    def _translate_tools(tools: list[LLMToolSpec]) -> list[dict[str, Any]]:
        """Translate canonical tool specs to OpenAI Responses tool format.

        Each canonical ``LLMToolSpec`` (``name``, ``description``,
        ``parameters``) is wrapped with the OpenAI ``type="function"``
        marker required by the Responses API.

        Args:
            tools: Canonical tool specification list.

        Returns:
            Provider-native tool list.
        """
        result: list[dict[str, Any]] = []
        for tool in tools:
            translated = dict(tool)
            translated["type"] = "function"
            result.append(translated)
        return result

    @staticmethod
    def _translate_messages(messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Translate canonical messages to OpenAI Responses API ``input`` items.

        - ``SystemMessage``, ``UserMessage``, ``AssistantMessage`` pass
          through unchanged (their ``role`` field matches the API).
        - ``ToolResultMessage`` is converted to the Responses API
          ``function_call_output`` shape.

        Args:
            messages: Canonical message list.

        Returns:
            Provider-native input items for the Responses API ``input`` array.
        """
        result: list[dict[str, Any]] = []
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "tool_result":
                result.append(
                    {
                        "type": "function_call_output",
                        "call_id": msg["call_id"],
                        "output": msg["content"],
                    }
                )
            else:
                result.append(msg)  # type: ignore[arg-type]
        return result

    @staticmethod
    def _build_payload(
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None,
        model_config: LanguageModel,
    ) -> dict[str, Any]:
        """Build the chat completion payload shared by sync and streaming paths.

        Translates canonical inputs (messages and tool specs) into
        OpenAI Responses API native request format before building the
        payload dict.

        Args:
            messages: Canonical message list.
            tools: Optional list of tool specs.
            model_config: Language model configuration.

        Returns:
            Complete payload dict ready for the LLM API request.
        """
        translated_messages = OpenAICompatibleClient._translate_messages(messages)

        payload: dict[str, Any] = {
            "model": model_config.model_name,
            "input": translated_messages,
        }

        _FIELD_MAP = {
            "max_tokens": "max_output_tokens",
        }
        for field in (
            "temperature",
            "max_tokens",
            "top_p",
            "frequency_penalty",
            "presence_penalty",
            "stop",
            "seed",
            "response_format",
            "tool_choice",
            "logprobs",
            "top_logprobs",
            "user",
        ):
            value = getattr(model_config, field)
            if value is not None:
                payload[_FIELD_MAP.get(field, field)] = value

        if tools:
            payload["tools"] = OpenAICompatibleClient._translate_tools(tools)
            if "tool_choice" not in payload:
                payload["tool_choice"] = "auto"

        return payload

    async def _chat_impl(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        stream: bool = False,
        raw_events: bool = False,
    ) -> LLMResponse | AsyncIterator[LLMEvent] | AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]:
        """Send a chat completion request via the OpenAI Responses API.

        Args:
            messages: Canonical message list.
            tools: Optional list of tool specs.
            stream: When True, return an async generator of SSE chunk events.
            raw_events: When True and stream=True, yield ``(canonical, raw)``
                tuples. OpenAI-compatible endpoints do not support raw event
                passthrough in Phase 1 — this flag has no effect.

        Returns:
            Non-streaming: ``LLMResponse``.
            Streaming: ``AsyncIterator[LLMEvent]``.
        """
        if not stream:
            return await self._chat_sync(messages, tools)
        return self._chat_stream(messages, tools, raw_events=raw_events)

    async def _chat_sync(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None,
    ) -> LLMResponse:
        """Non-streaming Responses API call.

        Args:
            messages: List of message dicts.
            tools: Optional list of tool schemas.

        Returns:
            Canonical ``LLMResponse`` with content, tool_calls, usage.
        """
        client = self._get_client()
        payload = self._build_payload(messages, tools, self._model_config)

        try:
            response = await client.post("/responses", json=payload)
        except httpx.RequestError as e:
            raise ProviderApiError(
                0,
                f"Failed to connect to LLM at {self._model_config.base_url}: {e}",
            ) from e

        if response.status_code in (401, 403):
            raise ProviderAuthError(
                f"Authentication failed for provider '{self._model_config.provider}'"
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ProviderApiError(
                response.status_code,
                f"Provider API error: {e}",
            ) from e
        data = response.json()

        content = None
        tool_calls = None
        for item in data.get("output", []):
            if item.get("type") == "message":
                text_parts = [
                    p.get("text", "")
                    for p in item.get("content", [])
                    if p.get("type") == "output_text"
                ]
                content = "".join(text_parts) or None
            elif item.get("type") == "function_call":
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append(
                    {
                        "id": item.get("id", ""),
                        "call_id": item.get("call_id", ""),
                        "name": item.get("name", ""),
                        "arguments": item.get("arguments", "{}"),
                    }
                )

        usage_raw = data.get("usage")
        from tinycua_sdk.agent.events import TokenUsage

        usage: TokenUsage | None = None
        if usage_raw:
            usage = TokenUsage(
                input_tokens=usage_raw.get("input_tokens"),
                output_tokens=usage_raw.get("output_tokens"),
                total_tokens=usage_raw.get("total_tokens"),
            )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=None,
            model=self._model_config.model_name,
        )

    @staticmethod
    def _normalize_responses_event(
        event: dict[str, Any],
    ) -> list[LLMEvent]:
        """Normalize a raw Responses API stream event into canonical events.

        Converts provider-specific event names to canonical SDK stream
        event types so that consumers are decoupled from the upstream
        provider's SSE dialect. Some provider events may expand into
        multiple canonical events (e.g. ``response.function_call_arguments.done``
        yields both ``tool_call.arguments.done`` and ``tool_call.ready``).

        Args:
            event: Raw Responses API stream event dict.

        Returns:
            List of canonical SDK stream events (``list[LLMEvent]``).
        """
        event_type = event.get("type", "")

        if event_type == "response.output_text.delta":
            return [
                ContentDeltaEvent(
                    type="content.delta",
                    delta=event.get("delta", ""),
                    index=0,
                ),
            ]

        if event_type == "response.output_text.done":
            return [
                ContentDoneEvent(
                    type="content.done",
                    index=0,
                ),
            ]

        if event_type == "response.output_item.added":
            item = event.get("item", {})
            if item.get("type") == "function_call":
                return [
                    ToolCallStartedEvent(
                        type="tool_call.started",
                        id=item.get("id", ""),
                        call_id=item.get("call_id", ""),
                        name=item.get("name", ""),
                    ),
                ]
            # Non-function items (e.g. message items) have no canonical
            # equivalent; content is delivered via output_text.delta/done.
            return []

        if event_type == "response.function_call_arguments.delta":
            return [
                ToolCallArgumentsDeltaEvent(
                    type="tool_call.arguments.delta",
                    id=event.get("item_id", ""),
                    arguments=event.get("delta", ""),
                ),
            ]

        if event_type == "response.function_call_arguments.done":
            item_id = event.get("item_id", "")
            call_id = event.get("call_id", "")
            name = event.get("name", "")
            arguments = event.get("arguments", "")
            return [
                ToolCallArgumentsDoneEvent(
                    type="tool_call.arguments.done",
                    id=item_id,
                    call_id=call_id,
                    name=name,
                    arguments=arguments,
                ),
                ToolCallReadyEvent(
                    type="tool_call.ready",
                    id=item_id,
                    call_id=call_id,
                    name=name,
                    arguments=arguments,
                ),
            ]

        # All other events pass through unchanged (they are already canonical)
        return [event]  # type: ignore[return-value]

    async def _chat_stream(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None,
        raw_events: bool = False,
    ) -> AsyncIterator[LLMEvent] | AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]:
        """Streaming Responses API via SSE.

        Args:
            messages: List of message dicts.
            tools: Optional list of tool schemas.
            raw_events: When True, yield ``(canonical_event, raw_event)``
                tuples. Synthetic events (generated from one provider event)
                yield ``(canonical_event, None)`` for the synthetic slot.

        Yields:
            Canonical ``LLMEvent`` items, or ``(LLMEvent | None, RawSseEvent | None)``
            tuples when ``raw_events=True``.
        """
        client = self._get_client()

        req_payload = self._build_payload(messages, tools, self._model_config)
        req_payload["stream"] = True

        try:
            async with client.stream("POST", "/responses", json=req_payload) as response:
                if response.status_code in (401, 403):
                    raise ProviderAuthError(
                        f"Authentication failed for provider '{self._model_config.provider}'"
                    )
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    raise ProviderApiError(response.status_code, str(e)) from e

                buffer: str = ""
                async for line in response.aiter_lines():
                    line = line.strip()
                    if line.startswith("data:"):
                        data_chunk = line[5:].strip()
                        if data_chunk == "[DONE]":
                            continue
                        if buffer:
                            buffer += "\n" + data_chunk
                        else:
                            buffer = data_chunk
                        try:
                            data = json.loads(buffer)
                        except json.JSONDecodeError:
                            continue
                        events = self._normalize_responses_event(data)
                        raw_event_obj = RawSseEvent(provider=self._model_config.provider, raw_event=data)
                        for i, event in enumerate(events):
                            if raw_events:
                                yield (event, raw_event_obj if i == 0 else None)
                            else:
                                yield event
                        buffer = ""
                    elif not line and buffer:
                        data = json.loads(buffer)
                        events = self._normalize_responses_event(data)
                        raw_event_obj = RawSseEvent(provider=self._model_config.provider, raw_event=data)
                        for i, event in enumerate(events):
                            if raw_events:
                                yield (event, raw_event_obj if i == 0 else None)
                            else:
                                yield event
                        buffer = ""
                if buffer:
                    data = json.loads(buffer)
                    events = self._normalize_responses_event(data)
                    raw_event_obj = RawSseEvent(provider=self._model_config.provider, raw_event=data)
                    for i, event in enumerate(events):
                        if raw_events:
                            yield (event, raw_event_obj if i == 0 else None)
                        else:
                            yield event
        except httpx.RequestError as e:
            raise ProviderApiError(
                0,
                f"Failed to connect to LLM at {self._model_config.base_url}: {e}",
            ) from e


__all__ = ["LLMClient", "OpenAICompatibleClient"]
