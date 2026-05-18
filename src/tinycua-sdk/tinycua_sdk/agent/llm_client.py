"""LLM client ABC and OpenAI-compatible implementation.

Defines the canonical ``LLMClient`` abstract base class with a concrete
``chat()`` method that performs shared validation and delegates to the
abstract ``_chat_impl()``. Provider-specific subclasses implement
``_chat_impl()`` with their own streaming and non-streaming logic.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import httpx

from tinycua_sdk.agent.events import (
    ContentDeltaEvent,
    ContentDoneEvent,
    LLMEvent,
    LLMResponse,
    RawSseEvent,
    ResponseCompletedEvent,
    ResponseFailedEvent,
    ResponseUsageEvent,
    TokenUsage,
    ToolCallArgumentsDeltaEvent,
    ToolCallArgumentsDoneEvent,
    ToolCallDict,
    ToolCallReadyEvent,
    ToolCallStartedEvent,
)
from tinycua_sdk.core.exceptions import ProviderApiError, ProviderAuthError
from tinycua_sdk.core.providers import normalize_base_url

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from openai import AsyncOpenAI

    from tinycua_sdk.agent.events import LLMMessage, LLMToolSpec
    from tinycua_sdk.agent.llm_model import LanguageModel

def _yield_events(
    events: list[LLMEvent],
    raw_event_obj: RawSseEvent | None,
    raw_events: bool,
) -> Iterator[LLMEvent | tuple[LLMEvent | None, RawSseEvent | None]]:
    """Yield canonical events, optionally paired with raw event.

    Pairing rules (applied when ``raw_events=True``):

    - **Raw-only** (no canonical equivalent): ``(None, raw_event)``
    - **Canonical-only** (synthetic event): ``(canonical_event, None)``
    - **One-to-one** (one raw → one canonical): ``(canonical_event, raw_event)``
    - **One-to-many** (one raw → N canonicals): first gets
      ``(canonical, raw)``, subsequent get ``(canonical, None)``

    Args:
        events: List of canonical events from the normalizer.
        raw_event_obj: Raw SSE event object for pairing.
        raw_events: When True, yield ``(canonical, raw)`` tuples.

    Yields:
        Canonical ``LLMEvent`` items, or ``(LLMEvent | None, RawSseEvent | None)``
        tuples when ``raw_events=True``.
    """
    if not events and raw_events:
        yield (None, raw_event_obj)
    else:
        for i, event in enumerate(events):
            if raw_events:
                yield (event, raw_event_obj if i == 0 else None)
            else:
                yield event


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

        .. note::
            When ``raw_events=True``, the yielded ``(canonical, raw)`` tuples
            follow these pairing rules:

            - **Raw-only** (no canonical equivalent): ``(None, raw_event)``
            - **Canonical-only** (synthetic event): ``(canonical_event, None)``
            - **One-to-one**: ``(canonical_event, raw_event)``
            - **One-to-many**: first gets ``(canonical, raw)``, subsequent
              get ``(canonical, None)``

            Consumers MUST handle ``None`` in either slot.

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
            msg = "raw_events=True requires stream=True"
            raise ValueError(msg)
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
        self._previous_response_id: str | None = None

    def _client_key(self) -> tuple[str, str]:
        api_key = self._model_config.api_key.get_secret_value()
        base_url = normalize_base_url(self._model_config.base_url, self._model_config.provider)
        return (base_url, api_key)

    def _get_client(self) -> httpx.AsyncClient:
        key = self._client_key()
        if key not in self._clients:
            api_key = key[1]
            headers: dict[str, str] = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            self._clients[key] = httpx.AsyncClient(
                base_url=key[0], headers=headers, timeout=60.0,
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
                        "call_id": msg.get("call_id", ""),
                        "output": msg.get("content", ""),
                    },
                )
            else:
                result.append(msg)  # type: ignore[arg-type]
        return result

    @staticmethod
    def _build_payload(
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None,
        model_config: LanguageModel,
        previous_response_id: str | None = None,
    ) -> dict[str, Any]:
        """Build the chat completion payload shared by sync and streaming paths.

        Translates canonical inputs (messages and tool specs) into
        OpenAI Responses API native request format before building the
        payload dict.

        Args:
            messages: Canonical message list.
            tools: Optional list of tool specs.
            model_config: Language model configuration.
            previous_response_id: The ``id`` of the preceding response when
                continuing a conversation with tool-result inputs. Only
                included in the payload when there are ``function_call_output``
                items in the translated input.

        Returns:
            Complete payload dict ready for the LLM API request.
        """
        translated_messages = OpenAICompatibleClient._translate_messages(messages)

        payload: dict[str, Any] = {
            "model": model_config.model_name,
            "input": translated_messages,
        }

        if previous_response_id:
            has_function_call_output = any(
                item.get("type") == "function_call_output"
                for item in translated_messages
            )
            if has_function_call_output:
                payload["previous_response_id"] = previous_response_id

        _FIELD_MAP = {
            "max_tokens": "max_output_tokens",
            "response_format": "text",
        }
        for field in (
            "temperature",
            "max_tokens",
            "top_p",
            "response_format",
            "tool_choice",
            "top_logprobs",
            "user",
        ):
            value = getattr(model_config, field)
            if value is not None:
                mapped = _FIELD_MAP.get(field, field)
                if mapped == "text":
                    payload[mapped] = {"format": value}
                else:
                    payload[mapped] = value

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
                tuples. Synthetic events (generated from one provider event)
                yield ``(canonical_event, None)`` for the synthetic slot.

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
        payload = self._build_payload(messages, tools, self._model_config, self._previous_response_id)

        try:
            response = await client.post("/responses", json=payload)
        except httpx.RequestError as e:
            raise ProviderApiError(
                0,
                f"Failed to connect to LLM at {self._model_config.base_url}: {e}",
            ) from e

        if response.status_code in (401, 403):
            msg = f"Authentication failed for provider '{self._model_config.provider}'"
            raise ProviderAuthError(
                msg,
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ProviderApiError(
                response.status_code,
                f"Provider API error: {e}",
            ) from e
        data = response.json()

        self._previous_response_id = data.get("id") or None

        content = None
        tool_calls: list[ToolCallDict] | None = None
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
                    ToolCallDict(
                        id=item.get("id", ""),
                        call_id=item.get("call_id", ""),
                        name=item.get("name", ""),
                        arguments=item.get("arguments", "{}"),
                    ),
                )

        usage_raw = data.get("usage")

        usage: TokenUsage | None = None
        if usage_raw:
            usage = TokenUsage(
                input_tokens=usage_raw.get("input_tokens"),
                output_tokens=usage_raw.get("output_tokens"),
                total_tokens=usage_raw.get("total_tokens"),
            )

        # Derive finish_reason from the Responses API status field.
        # "completed" with tool_calls → "tool_calls", otherwise "stop".
        # "incomplete" → "length"; "failed" → "error".
        status: str = data.get("status", "completed")
        if status == "completed":
            finish_reason: str = "tool_calls" if tool_calls else "stop"
        elif status == "incomplete":
            finish_reason = "length"
        elif status == "failed":
            finish_reason = "error"
        else:
            finish_reason = "stop"

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
            model=self._model_config.model_name,
        )

    @staticmethod
    def _normalize_content_event(event: dict[str, Any]) -> list[LLMEvent]:
        """Normalize a content-related stream event into canonical events.

        Handles ``response.output_text.delta`` and ``response.output_text.done``.

        Args:
            event: Raw Responses API stream event dict.

        Returns:
            List of canonical SDK stream events.
        """
        event_type = event.get("type", "")
        content_index = event.get("content_index", 0)
        if event_type == "response.output_text.delta":
            return [
                ContentDeltaEvent(
                    type="response.output_text.delta",
                    delta=event.get("delta", ""),
                    index=content_index,
                ),
            ]
        if event_type == "response.output_text.done":
            return [
                ContentDoneEvent(
                    type="response.output_text.done",
                    index=content_index,
                ),
            ]
        return []

    @staticmethod
    def _normalize_tool_event(
        event: dict[str, Any],
        _tool_cache: dict[str, dict[str, str]],
    ) -> list[LLMEvent]:
        """Normalize a tool-related stream event into canonical events.

        Handles ``response.output_item.added`` (function_call items),
        ``response.function_call_arguments.delta``, and
        ``response.function_call_arguments.done``.

        The ``_tool_cache`` is mutated to cache tool identity metadata
        (``call_id``, ``name``) keyed by ``item_id`` across a single stream,
        so that ``done`` events lacking identity fields can be enriched.

        Args:
            event: Raw Responses API stream event dict.
            _tool_cache: Per-stream dict mapping ``item_id`` to
                ``{"call_id": str, "name": str}``.

        Returns:
            List of canonical SDK stream events.
        """
        event_type = event.get("type", "")

        if event_type == "response.output_item.added":
            item = event.get("item", {})
            if item.get("type") == "function_call":
                item_id = item.get("id", "")
                cached_call_id = item.get("call_id", "")
                cached_name = item.get("name", "")
                if item_id:
                    _tool_cache[item_id] = {
                        "call_id": cached_call_id,
                        "name": cached_name,
                    }
                return [
                    ToolCallStartedEvent(
                        type="response.output_item.added",
                        id=item_id,
                        call_id=cached_call_id,
                        name=cached_name,
                    ),
                ]
            # Non-function items (e.g. message items) have no canonical
            # equivalent; content is delivered via output_text.delta/done.
            return []

        if event_type == "response.function_call_arguments.delta":
            return [
                ToolCallArgumentsDeltaEvent(
                    type="response.function_call_arguments.delta",
                    id=event.get("item_id", ""),
                    arguments=event.get("delta", ""),
                ),
            ]

        if event_type == "response.function_call_arguments.done":
            item_id = event.get("item_id", "")
            call_id = event.get("call_id", "")
            name = event.get("name", "")
            arguments = event.get("arguments", "")
            # Fall back to cached metadata if the done event omits identity.
            if item_id and (not call_id or not name) and item_id in _tool_cache:
                cached = _tool_cache[item_id]
                call_id = call_id or cached.get("call_id", "")
                name = name or cached.get("name", "")
            return [
                ToolCallArgumentsDoneEvent(
                    type="response.function_call_arguments.done",
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

        return []

    @staticmethod
    def _normalize_lifecycle_event(event: dict[str, Any]) -> list[LLMEvent]:
        """Normalize a lifecycle-related stream event into canonical events.

        Handles ``response.completed``, ``response.failed``, and
        ``response.usage``. The completed event may also embed a nested
        usage object that gets emitted as a separate ``response.usage``
        event before the completion event.

        Args:
            event: Raw Responses API stream event dict.

        Returns:
            List of canonical SDK stream events.
        """
        event_type = event.get("type", "")

        if event_type == "response.completed":
            finish_reason = event.get("finish_reason")
            if not finish_reason:
                status = event.get("response", {}).get("status", "completed")
                _FINISH_REASON_MAP = {"completed": "stop", "incomplete": "length", "failed": "error"}
                finish_reason = _FINISH_REASON_MAP.get(status, "stop")
                # When status is "completed", check if the completed response
                # contains function_call output — if so, emit tool_calls.
                if status == "completed":
                    output = event.get("response", {}).get("output", [])
                    if any(
                        isinstance(item, dict) and item.get("type") == "function_call"
                        for item in output
                    ):
                        finish_reason = "tool_calls"
            result: list[LLMEvent] = [ResponseCompletedEvent(type="response.completed", finish_reason=finish_reason)]
            # Preserve nested usage from the completed response payload.
            nested_usage = event.get("response", {}).get("usage")
            if isinstance(nested_usage, dict) and any(
                k in nested_usage for k in ("input_tokens", "output_tokens", "total_tokens")
            ):
                result.insert(
                    0,
                    ResponseUsageEvent(
                        type="response.usage",
                        usage=TokenUsage(
                            input_tokens=nested_usage.get("input_tokens"),
                            output_tokens=nested_usage.get("output_tokens"),
                            total_tokens=nested_usage.get("total_tokens"),
                        ),
                    ),
                )
            return result

        if event_type == "response.failed":
            raw_error = event.get("error") or event.get("response", {}).get("error", {})
            error: dict[str, Any] = {}
            if isinstance(raw_error, dict):
                error = {str(k): v for k, v in raw_error.items()}
            return [ResponseFailedEvent(type="response.failed", error=error)]

        if event_type == "response.usage":
            usage_data = event.get("usage", event)
            if not isinstance(usage_data, dict):
                return []
            input_t = usage_data.get("input_tokens")
            output_t = usage_data.get("output_tokens")
            total_t = usage_data.get("total_tokens")
            if any(v is not None for v in (input_t, output_t, total_t)):
                return [
                    ResponseUsageEvent(
                        type="response.usage",
                        usage=TokenUsage(
                            input_tokens=input_t,
                            output_tokens=output_t,
                            total_tokens=total_t,
                        ),
                    ),
                ]
            return []

        return []

    @staticmethod
    def _normalize_responses_event(
        event: dict[str, Any],
        _tool_cache: dict[str, dict[str, str]] | None = None,
    ) -> list[LLMEvent]:
        """Normalize a raw Responses API stream event into canonical events.

        Dispatches to specialised helpers for content, tool, and lifecycle
        events so that no single function exceeds the cyclomatic complexity
        threshold. Unknown provider events are silently dropped.

        The optional ``_tool_cache`` maintains tool identity metadata
        (``call_id``, ``name``) keyed by ``item_id`` across a single stream.
        When ``response.output_item.added`` carries a ``function_call`` item,
        its ``call_id`` and ``name`` are cached. When
        ``response.function_call_arguments.done`` lacks those fields
        (the Responses API may omit them in the done event), the cache
        supplies them so that ``tool_call.ready`` always carries complete
        tool identity metadata.

        Args:
            event: Raw Responses API stream event dict.
            _tool_cache: Per-stream dict mapping ``item_id`` to
                ``{"call_id": str, "name": str}``. Created automatically
                when ``None`` and mutated during normalization.

        Returns:
            List of canonical SDK stream events (``list[LLMEvent]``).
        """
        if _tool_cache is None:
            _tool_cache = {}

        event_type = event.get("type", "")

        # Content events.
        if event_type in ("response.output_text.delta", "response.output_text.done"):
            return OpenAICompatibleClient._normalize_content_event(event)

        # Tool events.
        if event_type in (
            "response.output_item.added",
            "response.function_call_arguments.delta",
            "response.function_call_arguments.done",
        ):
            return OpenAICompatibleClient._normalize_tool_event(event, _tool_cache)

        # Lifecycle events.
        if event_type in ("response.completed", "response.failed", "response.usage"):
            return OpenAICompatibleClient._normalize_lifecycle_event(event)

        # Unknown provider events are not canonical — drop them.
        # In raw_events=True mode, _chat_stream handles yielding the
        # raw event separately.
        return []

    @staticmethod
    async def _iter_sse_raw_events(
        response: httpx.Response,
    ) -> AsyncIterator[dict[str, Any]]:
        """Parse SSE lines from an httpx streaming response into raw event dicts.

        Accumulates partial JSON chunks across consecutive ``data:`` lines
        and yields complete parsed dicts.

        Args:
            response: An active httpx streaming response.

        Yields:
            Parsed JSON dicts from SSE ``data:`` lines.
        """
        buffer: str = ""
        async for line in response.aiter_lines():
            line = line.strip()
            if line.startswith("data:"):
                data_chunk = line[5:].strip()
                if data_chunk == "[DONE]":
                    continue
                buffer += data_chunk
                try:
                    data = json.loads(buffer)
                except json.JSONDecodeError:
                    continue
                yield data
                buffer = ""
            elif not line and buffer:
                try:
                    data = json.loads(buffer)
                except json.JSONDecodeError:
                    continue
                yield data
                buffer = ""
        if buffer:
            try:
                data = json.loads(buffer)
            except json.JSONDecodeError:
                return
            yield data

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

        req_payload = self._build_payload(messages, tools, self._model_config, self._previous_response_id)
        req_payload["stream"] = True

        try:
            async with client.stream("POST", "/responses", json=req_payload) as response:
                if response.status_code in (401, 403):
                    msg = f"Authentication failed for provider '{self._model_config.provider}'"
                    raise ProviderAuthError(
                        msg,
                    )
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    raise ProviderApiError(response.status_code, str(e)) from e

                tool_cache: dict[str, dict[str, str]] = {}
                async for data in self._iter_sse_raw_events(response):
                    if data.get("type") in ("response.created", "response.completed"):
                        nested = data.get("response", {})
                        self._previous_response_id = (
                            nested.get("id") or data.get("id") or None
                        )
                    events = self._normalize_responses_event(data, _tool_cache=tool_cache)
                    raw_event_obj = RawSseEvent(provider=self._model_config.provider, raw_event=data)
                    for item in _yield_events(events, raw_event_obj, raw_events):
                        yield item  # type: ignore[misc]
        except httpx.RequestError as e:
            raise ProviderApiError(
                0,
                f"Failed to connect to LLM at {self._model_config.base_url}: {e}",
            ) from e


class OpenAIResponsesClient(LLMClient):
    """OpenAI Responses API provider client wrapping the official openai SDK.

    Uses ``openai.responses.create()`` for non-streaming and
    ``client.responses.create(stream=True)`` for streaming.
    Reuses the canonical event normalization from ``OpenAICompatibleClient``.
    """

    def __init__(self, model_config: LanguageModel) -> None:
        self._model_config = model_config
        self._client: AsyncOpenAI | None = None
        self._previous_response_id: str | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            from openai import AsyncOpenAI

            api_key = self._model_config.api_key.get_secret_value() if self._model_config.api_key else None
            base_url = normalize_base_url(self._model_config.base_url, self._model_config.provider)
            self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        return self._client

    async def close(self) -> None:
        """Close the underlying OpenAI client and release resources."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    _RESPONSES_API_FIELDS: set[str] = {
        "temperature",
        "max_tokens",
        "top_p",
        "response_format",
        "tool_choice",
        "top_logprobs",
        "user",
    }

    _RESPONSES_API_UNSUPPORTED_FIELDS: dict[str, object] = {
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
        "stop": None,
        "seed": None,
        "logprobs": False,
    }

    def _build_request_kwargs(
        self,
        input_items: list[dict[str, Any]],
        tools: list[LLMToolSpec] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self._model_config.model_name,
            "input": input_items,
        }

        if self._previous_response_id:
            has_function_call_output = any(
                item.get("type") == "function_call_output"
                for item in input_items
            )
            if has_function_call_output:
                kwargs["previous_response_id"] = self._previous_response_id

        for field, default in self._RESPONSES_API_UNSUPPORTED_FIELDS.items():
            value = getattr(self._model_config, field, default)
            if value != default:
                raise ProviderApiError(
                    0,
                    f"'{field}' is not supported by the OpenAI Responses API "
                    f"(provider 'openai-responses'). Value was: {value!r}",
                )

        _FIELD_MAP = {
            "max_tokens": "max_output_tokens",
            "response_format": "text",
        }
        for field in self._RESPONSES_API_FIELDS:
            value = getattr(self._model_config, field, None)
            if value is not None:
                mapped = _FIELD_MAP.get(field, field)
                if mapped == "text":
                    kwargs[mapped] = {"format": value}
                else:
                    kwargs[mapped] = value

        if tools:
            kwargs["tools"] = OpenAICompatibleClient._translate_tools(tools)
            if "tool_choice" not in kwargs:
                kwargs["tool_choice"] = "auto"

        return kwargs

    @staticmethod
    def _normalize_non_streaming_response(data: dict[str, Any]) -> LLMResponse:
        content = None
        tool_calls: list[ToolCallDict] | None = None
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
                    ToolCallDict(
                        id=item.get("id", ""),
                        call_id=item.get("call_id", ""),
                        name=item.get("name", ""),
                        arguments=item.get("arguments", "{}"),
                    ),
                )

        usage_raw = data.get("usage")
        usage: TokenUsage | None = None
        if usage_raw:
            usage = TokenUsage(
                input_tokens=usage_raw.get("input_tokens"),
                output_tokens=usage_raw.get("output_tokens"),
                total_tokens=usage_raw.get("total_tokens"),
            )

        status: str = data.get("status", "completed")
        if status == "completed":
            finish_reason: str = "tool_calls" if tool_calls else "stop"
        elif status == "incomplete":
            finish_reason = "length"
        elif status == "failed":
            finish_reason = "error"
        else:
            finish_reason = "stop"

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
            model=data.get("model", ""),
        )

    async def _chat_impl(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        stream: bool = False,
        raw_events: bool = False,
    ) -> LLMResponse | AsyncIterator[LLMEvent] | AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]:
        if not stream:
            return await self._chat_sync(messages, tools)
        return self._chat_stream(messages, tools, raw_events=raw_events)

    async def _chat_sync(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None,
    ) -> LLMResponse:
        client = self._get_client()
        translated_input = OpenAICompatibleClient._translate_messages(messages)
        kwargs = self._build_request_kwargs(translated_input, tools)

        try:
            response = await client.responses.create(**kwargs)
        except Exception as e:
            error_str = str(e)
            if "auth" in error_str.lower() or "401" in error_str or "403" in error_str:
                raise ProviderAuthError(error_str) from e
            status_code = getattr(e, "status_code", 0)
            raise ProviderApiError(status_code, f"OpenAI API error: {e}") from e

        data = response.model_dump() if hasattr(response, "model_dump") else {}
        self._previous_response_id = data.get("id", None) or None
        data["model"] = data.get("model", self._model_config.model_name)
        return self._normalize_non_streaming_response(data)

    async def _chat_stream(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None,
        raw_events: bool = False,
    ) -> AsyncIterator[LLMEvent] | AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]:
        client = self._get_client()
        translated_input = OpenAICompatibleClient._translate_messages(messages)
        kwargs = self._build_request_kwargs(translated_input, tools)
        kwargs["stream"] = True

        try:
            stream = await client.responses.create(**kwargs)
        except Exception as e:
            error_str = str(e)
            if "auth" in error_str.lower() or "401" in error_str or "403" in error_str:
                raise ProviderAuthError(error_str) from e
            status_code = getattr(e, "status_code", 0)
            raise ProviderApiError(status_code, f"OpenAI API error: {e}") from e

        tool_cache: dict[str, dict[str, str]] = {}
        try:
            async for event in stream:
                data = event.model_dump() if hasattr(event, "model_dump") else {}
                if data.get("type") in ("response.created", "response.completed"):
                    nested = data.get("response", {})
                    self._previous_response_id = (
                        nested.get("id") or data.get("id") or None
                    )
                events = OpenAICompatibleClient._normalize_responses_event(data, _tool_cache=tool_cache)
                raw_event_obj = RawSseEvent(provider=self._model_config.provider, raw_event=event)
                for item in _yield_events(events, raw_event_obj, raw_events):
                    yield item  # type: ignore[misc]
        except Exception as e:
            error_str = str(e)
            if "auth" in error_str.lower() or "401" in error_str or "403" in error_str:
                raise ProviderAuthError(error_str) from e
            status_code = getattr(e, "status_code", 0)
            raise ProviderApiError(status_code, f"OpenAI API stream error: {e}") from e


__all__ = ["LLMClient", "OpenAICompatibleClient", "OpenAIResponsesClient"]
