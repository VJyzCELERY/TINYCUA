"""OpenAI Chat Completions API provider client.

Owns the ``OpenAIChatCompletionsClient``, chunk-accumulation dataclasses,
and Chat Completions-specific attachment translation helpers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field as dataclass_field
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.events import (
    ContentDeltaEvent,
    ContentDoneEvent,
    LLMEvent,
    LLMResponse,
    RawSseEvent,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseUsageEvent,
    TokenUsage,
    ToolCallArgumentsDeltaEvent,
    ToolCallArgumentsDoneEvent,
    ToolCallDict,
    ToolCallReadyEvent,
    ToolCallStartedEvent,
)
from tinycua_sdk.agent.llm_client import LLMClient, _yield_events
from tinycua_sdk.core.exceptions import ProviderApiError, ProviderAuthError
from tinycua_sdk.models.attachment import ContentPart, FileAttachment
from tinycua_sdk.providers.constants import OPENAI_BASE_URL
from tinycua_sdk.providers.utility import normalize_base_url

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from openai import AsyncOpenAI

    from tinycua_sdk.agent.events import LLMMessage, LLMToolSpec
    from tinycua_sdk.agent.llm_model import LanguageModel


# ── Chat Completions accumulators ─────────────────────────────────────────────


@dataclass
class ToolCallAccumulator:
    """Tracks streamed tool-call identity and argument fragments by tool-call index."""

    index: int
    id: str | None = None
    name: str | None = None
    arguments_parts: list[str] = dataclass_field(default_factory=list)
    started_emitted: bool = False
    done_emitted: bool = False
    ready_emitted: bool = False


def _accumulator_to_chat_tool_calls(acc: ChoiceAccumulator) -> list[dict[str, Any]] | None:
    if not acc.tool_calls:
        return None
    result: list[dict[str, Any]] = []
    for tca in sorted(acc.tool_calls.values(), key=lambda x: x.index):
        full_args = "".join(tca.arguments_parts) if tca.arguments_parts else "{}"
        result.append({
            "id": tca.id or "",
            "type": "function",
            "function": {"name": tca.name or "", "arguments": full_args},
        })
    return result if result else None


@dataclass
class ChoiceAccumulator:
    """Tracks content, tool calls, finish reason, and usage for a single choice."""

    index: int
    content_parts: list[str] = dataclass_field(default_factory=list)
    tool_calls: dict[int, ToolCallAccumulator] = dataclass_field(default_factory=dict)
    finish_reason: str | None = None
    usage: dict | None = None
    content_done_emitted: bool = False
    started_emitted: bool = False
    done_emitted: bool = False
    ready_emitted: bool = False
    completion_deferred: bool = False


# ── Chat Completions supported fields ─────────────────────────────────────────

_CHAT_SUPPORTED_FIELDS: set[str] = {
    "temperature",
    "max_tokens",
    "top_p",
    "response_format",
    "tool_choice",
    "top_logprobs",
    "user",
    "frequency_penalty",
    "presence_penalty",
    "stop",
    "seed",
    "logprobs",
}


def _translate_chat_attachment(attachment: FileAttachment) -> dict[str, Any]:
    """Translate a single FileAttachment to a Chat Completions content part.

    Produces an ``image_url`` content part with either a data URL
    (base64-encoded inline data) or a direct URL, depending on which
    source field is set on the attachment.

    Args:
        attachment: A canonical ``FileAttachment``.

    Returns:
        A dict with ``type`` and ``image_url`` keys.

    Raises:
        ValueError: If the MIME type does not start with ``image/``, or if
            only ``file_id`` is set (no upload/cache mapping in Phase 2).
    """
    if not attachment.mime_type.startswith("image/"):
        raise ValueError(
            f"Chat Completions provider only supports image attachments, "
            f"got mime_type={attachment.mime_type!r}"
        )

    if attachment.data is not None:
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{attachment.mime_type};base64,{attachment.data}",
            },
        }

    if attachment.url is not None:
        return {
            "type": "image_url",
            "image_url": {"url": attachment.url},
        }

    raise ValueError(
        "Chat Completions provider does not support file_id-only "
        "attachments (no upload/cache mapping in Phase 2)"
    )


def _translate_chat_content_part(part: ContentPart) -> dict[str, Any]:
    """Translate a ``ContentPart`` to a Chat Completions content part dict.

    - Text part (``type="text"``) → ``{"type": "text", "text": ...}``
    - File part (``type="file"``) → delegates to
      :func:`_translate_chat_attachment`.

    Args:
        part: A canonical ``ContentPart``.

    Returns:
        A dict with ``type`` and the appropriate content key.
    """
    if part.type == "text":
        return {"type": "text", "text": part.text}

    if part.type == "file":
        if part.file is None:
            raise ValueError("ContentPart with type='file' must have a non-None file")
        return _translate_chat_attachment(part.file)

    raise ValueError(f"Unknown ContentPart type: {part.type!r}")


def _translate_chat_user_message(msg: dict[str, Any]) -> dict[str, Any]:
    """Translate a user message dict for the Chat Completions API.

    Handles three input shapes:

    1. Plain string content, no attachments → pass through unchanged
       (backward compatible).
    2. String content with non-empty ``attachments`` → text part followed
       by image parts.
    3. ``content: list[ContentPart | dict]`` (with or without
       attachments) → translated parts, with message-level attachments
       appended after explicit content parts, preserving caller order
       within each group.  Dict items are coerced to ``ContentPart``
       via keyword unpacking.

    The ``attachments`` key is always stripped from the output (not a
    valid Chat Completions field).

    Args:
        msg: A message dict with ``role``, ``content``, and optionally
            ``attachments``.

    Returns:
        A translated message dict suitable for the Chat Completions API.

    Raises:
        ValueError: If ``content`` is an empty list (at least one content
            part is required).
    """
    content = msg.get("content")
    attachments: list[FileAttachment] = msg.get("attachments", []) or []

    result: dict[str, Any] = {"role": "user"}
    parts: list[dict[str, Any]] = []

    if isinstance(content, str):
        if not attachments:
            result = {k: v for k, v in msg.items() if k != "attachments"}
            return result

        if content:
            parts.append({"type": "text", "text": content})
        for att in attachments:
            parts.append(_translate_chat_attachment(att))
        result["content"] = parts
        return result

    if isinstance(content, list):
        if not content:
            raise ValueError(
                "User message content list cannot be empty "
                "(at least one ContentPart is required)"
            )

        for item in content:
            if isinstance(item, ContentPart):
                parts.append(_translate_chat_content_part(item))
            elif isinstance(item, dict):
                part = ContentPart(**item)
                parts.append(_translate_chat_content_part(part))
            else:
                raise ValueError(
                    f"Unsupported content part type: expected ContentPart "
                    f"or dict, got {type(item).__name__}"
                )

        for att in attachments:
            parts.append(_translate_chat_attachment(att))

        result["content"] = parts
        return result

    raise ValueError(
        f"Unsupported user message content type: expected str or list, "
        f"got {type(content).__name__}"
    )


class OpenAIChatCompletionsClient(LLMClient):
    """OpenAI Chat Completions API provider client.

    Uses ``client.chat.completions.create()`` for non-streaming and
    streaming. Translates Chat Completions delta chunks into the
    canonical event schema via ``ChoiceAccumulator`` /
    ``ToolCallAccumulator`` and ``_normalize_chat_chunk()``.
    """

    def __init__(self, model_config: LanguageModel) -> None:
        self._model_config = model_config
        self._client: AsyncOpenAI | None = None
        self._prior_tool_calls: dict[str, dict[str, Any]] = {}

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            from openai import AsyncOpenAI

            # Resolve API key: explicit > OPENAI_CHAT_COMPLETIONS_API_KEY > LLM_API_KEY
            api_key = self._model_config.api_key.get_secret_value() if self._model_config.api_key else None
            if not api_key:
                api_key = os.environ.get("OPENAI_CHAT_COMPLETIONS_API_KEY") or os.environ.get("LLM_API_KEY")

            # Resolve base URL: explicit > OPENAI_CHAT_COMPLETIONS_BASE_URL > TINYCUA_BASE_URL > LLM_BASE_URL > OpenAI default
            base_url = self._model_config.base_url
            if not base_url:
                base_url = (
                    os.environ.get("OPENAI_CHAT_COMPLETIONS_BASE_URL")
                    or os.environ.get("TINYCUA_BASE_URL")
                    or os.environ.get("LLM_BASE_URL")
                    or OPENAI_BASE_URL
                )
            base_url = normalize_base_url(base_url)

            self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        return self._client

    async def close(self) -> None:
        """Close the underlying OpenAI client and release resources."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    def _translate_chat_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Translate canonical messages to Chat Completions ``messages``.

        - ``SystemMessage`` and ``AssistantMessage`` pass through
          unchanged.  ``UserMessage`` may be translated to multimodal
          content when it carries ``list[ContentPart]`` content or
          ``attachments``.  Assistant messages that already carry
          ``tool_calls`` (embedded by the agent loop) are kept as-is.
        - ``ToolResultMessage`` is converted to ``{role: "tool",
          tool_call_id, content}``.
        - An assistant message with matching ``tool_calls`` is injected
          before each contiguous batch of ``tool_result`` messages whose
          ``call_id`` s are found in ``self._prior_tool_calls`` — but
          ONLY when the batch is NOT already preceded by an assistant
          message that already contains matching ``tool_calls``.

          This supports multi-turn tool conversations: the agent loop
          embeds ``tool_calls`` in the assistant messages it appends,
          so previously processed batches are self-contained and do not
          require injection.  Only new tool results (whose call_ids are
          still in the history from the most recent API response) get a
          fresh assistant ``tool_calls`` injected before them.
        """
        result: list[dict[str, Any]] = []
        i = 0
        while i < len(messages):
            msg = messages[i]

            if isinstance(msg, dict) and msg.get("role") == "assistant" and "tool_calls" in msg:
                result.append(msg)  # type: ignore[arg-type]
                i += 1
                continue

            if isinstance(msg, dict) and msg.get("role") == "tool_result":
                batch: list[dict] = []
                while i < len(messages):
                    m = messages[i]
                    if isinstance(m, dict) and m.get("role") == "tool_result":
                        batch.append(m)  # type: ignore[arg-type]
                        i += 1
                    else:
                        break

                last_has_matching_tc = (
                    result
                    and result[-1].get("role") == "assistant"
                    and "tool_calls" in result[-1]
                )
                if not last_has_matching_tc:
                    batch_call_ids = {
                        m.get("call_id", "") for m in batch
                        if m.get("call_id")
                    }
                    matched_calls = [
                        self._prior_tool_calls[cid]
                        for cid in batch_call_ids
                        if cid in self._prior_tool_calls
                    ]
                    if matched_calls:
                        result.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": matched_calls,
                        })

                for tool_msg in batch:
                    result.append({
                        "role": "tool",
                        "tool_call_id": tool_msg.get("call_id", ""),
                        "content": tool_msg.get("content", ""),
                    })
            else:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    result.append(_translate_chat_user_message(msg))  # type: ignore[arg-type]
                else:
                    result.append(msg)  # type: ignore[arg-type]
                i += 1

        return result

    @staticmethod
    def _translate_chat_tools(tools: list[LLMToolSpec]) -> list[dict[str, Any]]:
        """Translate canonical tool specs to Chat Completions tool format.

        Each spec is wrapped with ``type="function"`` and the name,
        description, and parameters are nested under ``function``.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", {"type": "object"}),
                },
            }
            for t in tools
        ]

    def _build_chat_payload(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
    ) -> dict[str, Any]:
        """Build a Chat Completions API request payload.

        Uses ``messages`` (not ``input``), ``max_tokens`` (not
        ``max_output_tokens``), and passes ``response_format`` directly
        (not wrapped in ``text.format``).
        """
        translated = self._translate_chat_messages(messages)
        payload: dict[str, Any] = {
            "model": self._model_config.model_name,
            "messages": translated,
        }

        for field in _CHAT_SUPPORTED_FIELDS:
            value = getattr(self._model_config, field)
            if value is not None:
                payload[field] = value

        if tools:
            payload["tools"] = self._translate_chat_tools(tools)
            if "tool_choice" not in payload:
                payload["tool_choice"] = "auto"

        return payload

    @staticmethod
    def _normalize_chunk_usage_only(
        chunk_data: dict[str, Any],
        acc: ChoiceAccumulator | None = None,
    ) -> list[LLMEvent]:
        """Normalize a usage-only chunk (no choices) into canonical events.

        If the accumulator has a deferred completion (set by
        ``_normalize_chunk_finalize``), emits ``response.usage`` first,
        then the deferred ``response.completed`` to preserve event order.
        """
        events: list[LLMEvent] = []
        usage_raw = chunk_data.get("usage")
        if usage_raw:
            events.append(
                ResponseUsageEvent(
                    type="response.usage",
                    usage=TokenUsage(
                        input_tokens=usage_raw.get("prompt_tokens"),
                        output_tokens=usage_raw.get("completion_tokens"),
                        total_tokens=usage_raw.get("total_tokens"),
                    ),
                ),
            )

        if acc is not None and acc.completion_deferred:
            acc.completion_deferred = False
            events.append(
                ResponseCompletedEvent(type="response.completed", finish_reason=acc.finish_reason or "stop"),
            )

        return events

    @staticmethod
    def _normalize_chunk_content(
        delta: dict[str, Any],
        acc: ChoiceAccumulator,
        events: list[LLMEvent],
    ) -> None:
        """Normalize content delta within a streaming chunk."""
        content = delta.get("content")
        if not content:
            return
        acc.content_parts.append(content)
        events.append(
            ContentDeltaEvent(
                type="response.output_text.delta",
                delta=content,
                index=acc.index,
            ),
        )

    @staticmethod
    def _normalize_chunk_tool_calls(
        delta: dict[str, Any],
        acc: ChoiceAccumulator,
        events: list[LLMEvent],
    ) -> None:
        """Normalize tool-call deltas within a streaming chunk."""
        raw_tool_calls = delta.get("tool_calls")
        if not raw_tool_calls:
            return
        for tc in raw_tool_calls:
            tc_index = tc.get("index", 0)
            if tc_index not in acc.tool_calls:
                acc.tool_calls[tc_index] = ToolCallAccumulator(index=tc_index)

            tca = acc.tool_calls[tc_index]

            tc_id = tc.get("id")
            if tc_id:
                tca.id = tc_id

            tc_function = tc.get("function", {})
            tc_name = tc_function.get("name")
            if tc_name:
                tca.name = tc_name

            tc_args = tc_function.get("arguments", "")
            if tc_args:
                tca.arguments_parts.append(tc_args)

            if not tca.started_emitted:
                tca.started_emitted = True
                events.append(
                    ToolCallStartedEvent(
                        type="response.output_item.added",
                        id=tca.id or "",
                        call_id=tca.id or "",
                        name=tca.name or "",
                    ),
                )

            if tc_args:
                events.append(
                    ToolCallArgumentsDeltaEvent(
                        type="response.function_call_arguments.delta",
                        id=tca.id or "",
                        arguments=tc_args,
                    ),
                )

    @staticmethod
    def _normalize_chunk_finalize(
        finish_reason: str | None,
        chunk_data: dict[str, Any],
        acc: ChoiceAccumulator,
        events: list[LLMEvent],
    ) -> None:
        """Finalize chunk: tool call completion, content done, usage, lifecycle."""
        if finish_reason == "tool_calls" and acc.tool_calls:
            for tca in acc.tool_calls.values():
                if not tca.done_emitted:
                    tca.done_emitted = True
                    full_args = "".join(tca.arguments_parts)
                    events.append(
                        ToolCallArgumentsDoneEvent(
                            type="response.function_call_arguments.done",
                            id=tca.id or "",
                            call_id=tca.id or "",
                            name=tca.name or "",
                            arguments=full_args,
                        ),
                    )

        if finish_reason and acc.content_parts and not acc.content_done_emitted:
            acc.content_done_emitted = True
            events.append(
                ContentDoneEvent(type="response.output_text.done", index=acc.index),
            )

        if finish_reason == "tool_calls":
            for tca in acc.tool_calls.values():
                if not tca.ready_emitted and tca.done_emitted:
                    tca.ready_emitted = True
                    full_args = "".join(tca.arguments_parts)
                    events.append(
                        ToolCallReadyEvent(
                            type="tool_call.ready",
                            id=tca.id or "",
                            call_id=tca.id or "",
                            name=tca.name or "",
                            arguments=full_args,
                        ),
                    )

        usage_raw = chunk_data.get("usage")
        if usage_raw:
            events.append(
                ResponseUsageEvent(
                    type="response.usage",
                    usage=TokenUsage(
                        input_tokens=usage_raw.get("prompt_tokens"),
                        output_tokens=usage_raw.get("completion_tokens"),
                        total_tokens=usage_raw.get("total_tokens"),
                    ),
                ),
            )

        if finish_reason:
            acc.finish_reason = finish_reason
            if not acc.done_emitted:
                acc.done_emitted = True
                acc.completion_deferred = True

    @staticmethod
    def _normalize_chat_chunk(
        chunk_data: dict[str, Any],
        acc: ChoiceAccumulator,
    ) -> list[LLMEvent]:
        """Normalize a single Chat Completions streaming chunk into canonical events.

        Accumulates content and tool-call deltas in ``acc`` and emits
        events only when state transitions occur (e.g. first delta,
        content done, tool-call ready).
        """
        choices = chunk_data.get("choices", [])
        if not choices:
            return OpenAIChatCompletionsClient._normalize_chunk_usage_only(chunk_data, acc)

        choice = choices[0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")

        events: list[LLMEvent] = []
        if not acc.started_emitted:
            acc.started_emitted = True
            events.append(ResponseCreatedEvent(type="response.created"))

        OpenAIChatCompletionsClient._normalize_chunk_content(delta, acc, events)
        OpenAIChatCompletionsClient._normalize_chunk_tool_calls(delta, acc, events)
        OpenAIChatCompletionsClient._normalize_chunk_finalize(finish_reason, chunk_data, acc, events)

        return events

    @staticmethod
    def _normalize_non_streaming_response(data: dict[str, Any]) -> LLMResponse:
        """Normalize a Chat Completions non-streaming response to ``LLMResponse``."""
        content = None
        tool_calls: list[ToolCallDict] | None = None

        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content") or None

            raw_tool_calls = message.get("tool_calls")
            if raw_tool_calls:
                tool_calls = []
                for tc in raw_tool_calls:
                    func = tc.get("function", {})
                    tool_calls.append(
                        ToolCallDict(
                            id=tc.get("id", ""),
                            call_id=tc.get("id", ""),
                            name=func.get("name", ""),
                            arguments=func.get("arguments", "{}"),
                        ),
                    )

            finish_reason = choices[0].get("finish_reason") or "stop"
        else:
            finish_reason = "stop"

        usage_raw = data.get("usage")
        usage: TokenUsage | None = None
        if usage_raw:
            usage = TokenUsage(
                input_tokens=usage_raw.get("prompt_tokens"),
                output_tokens=usage_raw.get("completion_tokens"),
                total_tokens=usage_raw.get("total_tokens"),
            )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
            model=data.get("model", ""),
        )

    @staticmethod
    def _handle_provider_error(e: Exception, context: str = "OpenAI Chat Completions API") -> None:
        status_code = getattr(e, "status_code", 0)
        if status_code in (401, 403):
            raise ProviderAuthError(str(e)) from e
        if "auth" in str(e).lower() or "credential" in str(e).lower():
            raise ProviderAuthError(str(e)) from e
        raise ProviderApiError(status_code, f"{context} error: {e}") from e

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
        payload = self._build_chat_payload(messages, tools)
        payload["stream"] = False

        try:
            client = self._get_client()
            response = await client.chat.completions.create(**payload)
        except Exception as e:
            self._handle_provider_error(e)

        data = response.model_dump() if hasattr(response, "model_dump") else {}
        self._capture_tool_calls(data)
        return self._normalize_non_streaming_response(data)

    def _capture_tool_calls(self, data: dict[str, Any]) -> None:
        choices = data.get("choices", [])
        if not choices:
            return
        message = choices[0].get("message", {})
        raw_tool_calls = message.get("tool_calls")
        if not raw_tool_calls:
            return
        for tc in raw_tool_calls:
            tid = tc.get("id", "")
            if tid:
                self._prior_tool_calls[tid] = {
                    "id": tid,
                    "type": "function",
                    "function": {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": tc.get("function", {}).get("arguments", "{}"),
                    },
                }

    async def _chat_stream(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None,
        raw_events: bool = False,
    ) -> AsyncIterator[LLMEvent] | AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]:
        payload = self._build_chat_payload(messages, tools)
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}

        try:
            client = self._get_client()
            stream = await client.chat.completions.create(**payload)
        except Exception as e:
            self._handle_provider_error(e)

        acc = ChoiceAccumulator(index=0)
        try:
            async for chunk in stream:
                data = chunk.model_dump() if hasattr(chunk, "model_dump") else {}
                events = self._normalize_chat_chunk(data, acc)
                raw_event_obj = RawSseEvent(provider=self._model_config.provider, raw_event=chunk)
                for item in _yield_events(events, raw_event_obj, raw_events):
                    yield item  # type: ignore[misc]

            if acc.completion_deferred:
                acc.completion_deferred = False
                completion_event = ResponseCompletedEvent(type="response.completed", finish_reason=acc.finish_reason or "stop")
                for item in _yield_events([completion_event], None, raw_events):
                    yield item  # type: ignore[misc]
            elif not acc.started_emitted:
                completion_event = ResponseCompletedEvent(type="response.completed", finish_reason="stop")
                for item in _yield_events([completion_event], None, raw_events):
                    yield item  # type: ignore[misc]
        except Exception as e:
            self._handle_provider_error(e, context="OpenAI Chat Completions API stream")
        finally:
            stream_tool_calls = _accumulator_to_chat_tool_calls(acc)
            if stream_tool_calls:
                for tc in stream_tool_calls:
                    tid = tc.get("id", "")
                    if tid:
                        self._prior_tool_calls[tid] = tc


__all__ = [
    "OpenAIChatCompletionsClient",
]
