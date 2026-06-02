"""OpenAI Chat Completions API provider client.

Owns the ``OpenAIChatCompletionsClient``, chunk-accumulation dataclasses,
and Chat Completions-specific attachment translation helpers.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field as dataclass_field
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.events import (
    ContentDeltaEvent,
    ContentDoneEvent,
    LLMEvent,
    LLMResponse,
    RawSseEvent,
    ReasoningDeltaEvent,
    ReasoningDoneEvent,
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
from tinycua_sdk.models.attachment import ContentPart, FileAttachment, StreamingFileAttachment
from tinycua_sdk.providers.constants import OPENAI_BASE_URL
from tinycua_sdk.providers.utility import (
    is_text_mime,
    materialize_streaming_image,
    materialize_streaming_text,
    normalize_base_url,
)

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
    reasoning_parts: list[str] = dataclass_field(default_factory=list)
    tool_calls: dict[int, ToolCallAccumulator] = dataclass_field(default_factory=dict)
    finish_reason: str | None = None
    content_done_emitted: bool = False
    reasoning_done_emitted: bool = False
    started_emitted: bool = False
    done_emitted: bool = False
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


async def _translate_chat_attachment(
    attachment: FileAttachment,
    *,
    _upload_fn: Callable[[FileAttachment], Awaitable[str]] | None = None,
) -> dict[str, Any]:
    """Translate a single FileAttachment to a Chat Completions content part.

    Image attachments (``image/*`` MIME type) produce ``image_url`` content
    parts (inline data URL or direct URL). Non-image attachments with
    ``data`` are uploaded via ``_upload_fn`` and produce ``file`` content
    parts with the returned ``file_id``. Attachments with a pre-existing
    ``file_id`` produce ``file`` content parts directly. Non-image URL
    attachments are downloaded and uploaded via ``/v1/files``, then
    referenced by ``file_id``.

    Args:
        attachment: A canonical ``FileAttachment``.
        _upload_fn: Optional async callable for file uploads. Required
            for non-image data-backed attachments.

    Returns:
        A dict with ``type`` and either ``image_url`` or ``file`` keys.

    Raises:
        ValueError: If no valid translation path exists (e.g., non-image
            URL attachment without download support).
    """
    is_image = attachment.mime_type.startswith("image/")

    # File with pre-existing file_id → file content part.
    if attachment.file_id is not None:
        return {"type": "file", "file": {"file_id": attachment.file_id}}

    # Image with inline data → image_url with data URL.
    if is_image and attachment.data is not None:
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{attachment.mime_type};base64,{attachment.data}",
            },
        }

    # Image with URL → image_url with URL reference.
    if is_image and attachment.url is not None:
        return {
            "type": "image_url",
            "image_url": {"url": attachment.url},
        }

    # Streaming image attachment → construct data URL inline from
    # base64 chunks to preserve existing image behavior (images are
    # never uploaded). Handles stream=True local file images that
    # have data=None and url=None.
    if isinstance(attachment, StreamingFileAttachment) and is_image:
        data_url = materialize_streaming_image(attachment)
        return {
            "type": "image_url",
            "image_url": {"url": data_url},
        }

    # Text-based content (plain text, markdown, code, JSON, CSV, HTML, XML) →
    # decode and send inline as a text part. No upload needed.
    if attachment.data is not None and is_text_mime(attachment.mime_type):
        import base64 as _base64
        text_content = _base64.b64decode(attachment.data).decode("utf-8", errors="replace")
        return {"type": "text", "text": text_content}

    # Streaming file attachment with text MIME → read and inline as text.
    # This must come before the generic streaming upload branch to
    # satisfy FR-001b (text-based MIME types must be inlined, not
    # uploaded).  Streaming attachments have data=None, so the
    # data-based text check above does not catch them.
    if isinstance(attachment, StreamingFileAttachment) and is_text_mime(attachment.mime_type):
        text_content = materialize_streaming_text(attachment)
        return {"type": "text", "text": text_content}

    # Streaming file attachment (non-image) → upload with streaming content.
    # Check before data/url checks since streaming attachments have
    # data=None and url=None (content is read from _file_path on demand).
    if isinstance(attachment, StreamingFileAttachment):
        if _upload_fn is None:
            raise ValueError(
                "Streaming file attachment requires upload, "
                "but no _upload_fn was provided"
            )
        file_id = await _upload_fn(attachment)
        return {"type": "file", "file": {"file_id": file_id}}

    # Non-image data-backed → upload required.
    if attachment.data is not None:
        if _upload_fn is None:
            raise ValueError(
                "Non-image data-backed attachment requires upload, "
                "but no _upload_fn was provided"
            )
        file_id = await _upload_fn(attachment)
        return {"type": "file", "file": {"file_id": file_id}}

    # Non-image URL → download + upload via _upload_fn (Phase 4).
    if attachment.url is not None:
        if _upload_fn is None:
            raise ValueError(
                "Non-image URL attachment requires download+upload, "
                "but no _upload_fn was provided"
            )
        file_id = await _upload_fn(attachment)
        return {"type": "file", "file": {"file_id": file_id}}

    raise ValueError(
        "Attachment has no usable source (data, url, or file_id required)"
    )


async def _translate_chat_content_part(
    part: ContentPart,
    *,
    _upload_fn: Callable[[FileAttachment], Awaitable[str]] | None = None,
) -> dict[str, Any]:
    """Translate a ``ContentPart`` to a Chat Completions content part dict.

    - Text part (``type="text"``) → ``{"type": "text", "text": ...}``
    - File part (``type="file"``) → delegates to
      :func:`_translate_chat_attachment`.

    Args:
        part: A canonical ``ContentPart``.
        _upload_fn: Optional async callable passed through to attachment
            translation.

    Returns:
        A dict with ``type`` and the appropriate content key.
    """
    if part.type == "text":
        return {"type": "text", "text": part.text}

    if part.type == "file":
        if part.file is None:
            raise ValueError("ContentPart with type='file' must have a non-None file")
        return await _translate_chat_attachment(
            part.file, _upload_fn=_upload_fn,
        )

    raise ValueError(f"Unknown ContentPart type: {part.type!r}")


async def _translate_chat_user_message(
    msg: dict[str, Any],
    *,
    _upload_fn: Callable[[FileAttachment], Awaitable[str]] | None = None,
) -> dict[str, Any]:
    """Translate a user message dict for the Chat Completions API.

    Handles three input shapes:

    1. Plain string content, no attachments → pass through unchanged
       (backward compatible).
    2. String content with non-empty ``attachments`` → text part followed
       by image/file parts.
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
        _upload_fn: Optional async callable passed through to attachment
            translation for non-image file uploads.

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
            parts.append(await _translate_chat_attachment(att, _upload_fn=_upload_fn))
        result["content"] = parts
        remaining = {k: v for k, v in msg.items() if k not in ("content", "attachments")}
        result.update(remaining)
        return result

    if isinstance(content, list):
        if not content:
            raise ValueError(
                "User message content list cannot be empty "
                "(at least one ContentPart is required)"
            )

        for item in content:
            if isinstance(item, ContentPart):
                parts.append(await _translate_chat_content_part(item, _upload_fn=_upload_fn))
            elif isinstance(item, dict):
                part = ContentPart(**item)
                parts.append(await _translate_chat_content_part(part, _upload_fn=_upload_fn))
            else:
                raise ValueError(
                    f"Unsupported content part type: expected ContentPart "
                    f"or dict, got {type(item).__name__}"
                )

        for att in attachments:
            parts.append(await _translate_chat_attachment(att, _upload_fn=_upload_fn))

        result["content"] = parts
        remaining = {k: v for k, v in msg.items() if k not in ("content", "attachments")}
        result.update(remaining)
        return result

    raise ValueError(
        f"Unsupported user message content type: expected str or list, "
        f"got {type(content).__name__}"
    )


async def _translate_chat_tool_result_batch(
    batch: list[dict[str, Any]],
    result: list[dict[str, Any]],
    *,
    _upload_fn: Callable[[FileAttachment], Awaitable[str]] | None = None,
) -> None:
    """Translate a batch of tool-result messages for Chat Completions.

    Emits all required ``role: "tool"`` messages first (one per
    ``call_id``, preserving the assistant tool-call batch), then appends
    one or more synthetic ``role: "user"`` messages containing the
    aggregated file/image parts and message-level ``attachments``.

    Args:
        batch: Contiguous tool-result message dicts.
        result: Output list (mutated in place).
        _upload_fn: Optional async upload callback for non-image files.
    """
    # Phase 1: Emit all tool messages first.
    user_msg_buffer: list[dict[str, Any]] = []
    for tool_msg in batch:
        tool_text, user_parts = _split_tool_result_content(tool_msg)

        # Text-only tool message.
        result.append({
            "role": "tool",
            "tool_call_id": tool_msg.get("call_id", ""),
            "content": tool_text,
        })

        # Collect file/image content parts for a deferred synthetic user message.
        attachments: list[FileAttachment] = tool_msg.get("attachments", []) or []
        if user_parts or attachments:
            user_msg: dict[str, Any] = {"role": "user"}
            user_msg["content"] = user_parts if user_parts else ""
            if attachments:
                user_msg["attachments"] = attachments
            user_msg_buffer.append(user_msg)

    # Phase 2: Emit deferred synthetic user messages after all tool messages.
    for user_msg in user_msg_buffer:
        translated_user = await _translate_chat_user_message(
            user_msg, _upload_fn=_upload_fn,
        )
        result.append(translated_user)


def _split_tool_result_content(
    tool_msg: dict[str, Any],
) -> tuple[str, list[ContentPart | dict[str, Any]]]:
    """Split tool-result content into text and file/image parts.

    Args:
        tool_msg: A canonical ``tool_result`` message dict.

    Returns:
        A tuple of ``(tool_text, user_content_parts)``.
    """
    content = tool_msg.get("content", "")
    tool_text = ""
    user_content_parts: list[ContentPart | dict[str, Any]] = []

    if isinstance(content, str):
        return content, user_content_parts

    if isinstance(content, list):
        for part in content:
            if isinstance(part, ContentPart):
                if part.type == "text" and part.text:
                    tool_text += ("\n" if tool_text else "") + part.text
                elif part.type == "file":
                    # Preserve the original ContentPart object so that
                    # StreamingFileAttachment internal state (e.g. _file_path)
                    # is not lost during serialization.
                    user_content_parts.append(part)
            elif isinstance(part, dict):
                if part.get("type") == "text":
                    t = part.get("text", "")
                    if t:
                        tool_text += ("\n" if tool_text else "") + t
                elif part.get("type") == "file":
                    user_content_parts.append(part)

    return tool_text, user_content_parts


class OpenAIChatCompletionsClient(LLMClient):
    """OpenAI Chat Completions API provider client.

    Uses ``client.chat.completions.create()`` for non-streaming and
    streaming. Translates Chat Completions delta chunks into the
    canonical event schema via ``ChoiceAccumulator`` /
    ``ToolCallAccumulator`` and ``_normalize_chat_chunk()``.

    Accepts an optional ``UploadSession`` for file upload deduplication
    and caching.
    """

    def __init__(
        self,
        model_config: LanguageModel,
        upload_session: Any | None = None,  # UploadSession from providers.upload
    ) -> None:
        self._model_config = model_config
        self._client: AsyncOpenAI | None = None
        self._prior_tool_calls: dict[str, dict[str, Any]] = {}
        # NOTE: _prior_tool_calls grows add-only across conversation turns.
        # Tool call IDs from the OpenAI API are unique per call, so there is
        # no collision risk, but long-running multi-turn agents will gradually
        # accumulate entries. This is acceptable for typical short agent runs
        # but may need pruning for very long sessions.

        if upload_session is not None:
            self._upload_session = upload_session
        else:
            from tinycua_sdk.providers.upload import UploadSession  # noqa: PLC0415

            # Resolve provider from model config for cache scoping.
            provider = self._model_config.provider

            # Resolve base URL following the same priority as _get_client:
            # explicit > OPENAI_CHAT_COMPLETIONS_BASE_URL > LLM_BASE_URL > OpenAI default.
            base_url = self._model_config.base_url
            if not base_url:
                base_url = (
                    os.environ.get("OPENAI_CHAT_COMPLETIONS_BASE_URL")
                    or os.environ.get("LLM_BASE_URL")
                    or OPENAI_BASE_URL
                )
            base_url = normalize_base_url(base_url)

            self._upload_session = UploadSession(
                provider=provider,
                base_url=base_url,
                cache_dir=os.environ.get("TINYCUA_CACHE_DIR"),
            )

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            from openai import AsyncOpenAI

            # Resolve API key: explicit > OPENAI_CHAT_COMPLETIONS_API_KEY
            api_key = self._model_config.api_key.get_secret_value() if self._model_config.api_key else None
            if not api_key:
                api_key = os.environ.get("OPENAI_CHAT_COMPLETIONS_API_KEY")

            # Resolve base URL: explicit > OPENAI_CHAT_COMPLETIONS_BASE_URL > LLM_BASE_URL > OpenAI default
            base_url = self._model_config.base_url
            if not base_url:
                base_url = (
                    os.environ.get("OPENAI_CHAT_COMPLETIONS_BASE_URL")
                    or os.environ.get("LLM_BASE_URL")
                    or OPENAI_BASE_URL
                )
            base_url = normalize_base_url(base_url)

            # Pass empty string (not None) to prevent the OpenAI SDK from
            # falling back to the generic OPENAI_API_KEY environment variable.
            # This enforces the provider-specific API-key contract.
            self._client = AsyncOpenAI(api_key=api_key or "", base_url=base_url)
        return self._client

    async def close(self) -> None:
        """Close the underlying OpenAI client and release resources."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        if hasattr(self, "_upload_session"):
            await self._upload_session.close()

    async def _translate_chat_messages(
        self,
        messages: list[LLMMessage],
        *,
        _upload_fn: Callable[[FileAttachment], Awaitable[str]] | None = None,
    ) -> list[dict[str, Any]]:
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

                # Compute current batch call IDs preserving order.
                batch_call_ids = [
                    m["call_id"]
                    for m in batch
                    if m.get("call_id")
                ]
                # Verify preceding assistant actually declares all those IDs.
                previous_call_ids: set[str] = set()
                if result and result[-1].get("role") == "assistant":
                    for tc in result[-1].get("tool_calls", []):
                        if isinstance(tc, dict) and tc.get("id"):
                            previous_call_ids.add(tc["id"])
                last_has_matching_tc = bool(
                    batch_call_ids
                    and set(batch_call_ids).issubset(previous_call_ids),
                )
                if not last_has_matching_tc:
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

                await _translate_chat_tool_result_batch(
                    batch, result, _upload_fn=_upload_fn,
                )
            else:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    result.append(await _translate_chat_user_message(msg, _upload_fn=_upload_fn))  # type: ignore[arg-type]
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

    async def _build_chat_payload(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
    ) -> dict[str, Any]:
        """Build a Chat Completions API request payload.

        Uses ``messages`` (not ``input``), ``max_tokens`` (not
        ``max_output_tokens``), and passes ``response_format`` directly
        (not wrapped in ``text.format``).
        """
        translated = await self._translate_chat_messages(
            messages,
            _upload_fn=self._ensure_uploaded_file_id,
        )
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

    async def _ensure_uploaded_file_id(self, attachment: FileAttachment) -> str:
        """Upload a file and return its provider ``file_id``.

        Delegates to :class:`UploadSession.ensure_file_id` for cache
        lookup, persistent cache integration, and concurrent upload
        deduplication.

        Args:
            attachment: A ``FileAttachment`` to upload.

        Returns:
            The provider ``file_id`` string.
        """
        return await self._upload_session.ensure_file_id(
            self._get_client(), attachment,
        )

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
        """Normalize content and reasoning deltas within a streaming chunk.

        Handles both ``delta.content`` (visible text) and
        ``delta.reasoning_content`` (chain-of-thought tokens from
        Qwen-compatible servers).
        """
        # Reasoning content (checked before visible content for correct event ordering)
        reasoning = delta.get("reasoning_content")
        if reasoning:
            acc.reasoning_parts.append(reasoning)
            events.append(
                ReasoningDeltaEvent(
                    type="response.reasoning.delta",
                    delta=reasoning,
                ),
            )

        # Visible content (unchanged behavior)
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
        """Finalize chunk: tool call completion, reasoning done, content done, usage, lifecycle."""
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

        # Reasoning done — must come BEFORE content done for correct event ordering
        if finish_reason and acc.reasoning_parts and not acc.reasoning_done_emitted:
            acc.reasoning_done_emitted = True
            events.append(
                ReasoningDoneEvent(type="response.reasoning.done"),
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
        reasoning_content = None
        tool_calls: list[ToolCallDict] | None = None

        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content") or None
            reasoning_content = message.get("reasoning_content") or None

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
            reasoning_content=reasoning_content,
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
        try:
            payload = await self._build_chat_payload(messages, tools)
            payload["stream"] = False
            client = self._get_client()
            response = await client.chat.completions.create(**payload)
        except (ValueError, ProviderApiError, ProviderAuthError):
            raise
        except Exception as e:
            self._handle_provider_error(e)

        if hasattr(response, "model_dump"):
            data = response.model_dump()
        elif hasattr(response, "dict"):
            data = response.dict()
        else:
            raise RuntimeError(
                f"Unexpected OpenAI SDK response type {type(response)}: "
                "expected model_dump() or dict() method"
            )
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
        try:
            payload = await self._build_chat_payload(messages, tools)
            payload["stream"] = True
            payload["stream_options"] = {"include_usage": True}
            client = self._get_client()
            stream = await client.chat.completions.create(**payload)
        except (ValueError, ProviderApiError, ProviderAuthError):
            raise
        except Exception as e:
            self._handle_provider_error(e)

        acc = ChoiceAccumulator(index=0)
        try:
            async for chunk in stream:
                data = chunk.model_dump() if hasattr(chunk, "model_dump") else chunk.dict() if hasattr(chunk, "dict") else {}
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
