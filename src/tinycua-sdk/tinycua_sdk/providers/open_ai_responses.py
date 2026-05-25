"""OpenAI Responses API provider client.

Owns the ``OpenAIResponsesClient``, Responses event normalization helpers,
and Responses-specific field mapping utilities.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from tinycua_sdk.models.attachment import ContentPart, FileAttachment, StreamingFileAttachment

from tinycua_sdk.agent.events import (
    ContentDeltaEvent,
    ContentDoneEvent,
    LLMEvent,
    LLMResponse,
    RawSseEvent,
    ReasoningDeltaEvent,
    ReasoningDoneEvent,
    ResponseCancelledEvent,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseFailedEvent,
    ResponseInProgressEvent,
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
from tinycua_sdk.providers.constants import OPENAI_BASE_URL
from tinycua_sdk.providers.utility import is_text_mime, normalize_base_url

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from openai import AsyncOpenAI

    from tinycua_sdk.agent.events import LLMMessage, LLMToolSpec
    from tinycua_sdk.agent.llm_model import LanguageModel


# ── Responses API field mapping ───────────────────────────────────────────────

_SUPPORTED_FIELDS: set[str] = {
    "temperature",
    "max_tokens",
    "top_p",
    "response_format",
    "tool_choice",
    "top_logprobs",
    "user",
}

_FIELD_MAP: dict[str, str] = {
    "max_tokens": "max_output_tokens",
    "response_format": "text",
}


# ── Responses API translation helpers ─────────────────────────────────────────


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


# ── Responses API attachment translation helpers (Phase 3) ────────────────────


async def _translate_responses_attachment(
    attachment: FileAttachment,
    *,
    _upload_fn: Callable[[FileAttachment], Awaitable[str]] | None = None,
    _download_fn: Callable[[str], Awaitable[bytes]] | None = None,
) -> dict[str, Any]:
    """Translate a single ``FileAttachment`` to a Responses content part.

    Image attachments (``image/*`` MIME type) produce ``input_image``
    content parts with ``detail="auto"``.  Non-image ``file_id``
    attachments produce ``input_file`` references.  Non-image data-backed
    attachments require upload (via ``_upload_fn``) and then produce
    ``input_file`` with the returned file ID.  Non-image URL attachments
    download content via ``_download_fn`` (or the default
    ``_download_url_content``) and send it inline via ``file_data``.

    Args:
        attachment: A canonical ``FileAttachment``.
        _upload_fn: Optional async callable that uploads the file and
            returns a provider ``file_id``. Required for non-image
            data-backed attachments without a pre-existing ``file_id``.
        _download_fn: Optional async callable that downloads URL content
            and returns raw bytes. When provided, the caller controls
            the timeout. When ``None``, the default
            ``_download_url_content`` is used with its built-in timeout.

    Returns:
        A dict with provider-native content part keys.

    Raises:
        ValueError: If the attachment source/MIME combination is unsupported.
    """
    is_image = attachment.mime_type.startswith("image/")

    # File with pre-existing file_id — use directly, no upload.
    if attachment.file_id is not None:
        if is_image:
            return {
                "type": "input_image",
                "file_id": attachment.file_id,
                "detail": "auto",
            }
        return {"type": "input_file", "file_id": attachment.file_id}

    # Image with inline data → input_image with data URL.
    if is_image and attachment.data is not None:
        return {
            "type": "input_image",
            "image_url": f"data:{attachment.mime_type};base64,{attachment.data}",
            "detail": "auto",
        }

    # Image with URL → input_image with URL reference.
    if is_image and attachment.url is not None:
        return {
            "type": "input_image",
            "image_url": attachment.url,
            "detail": "auto",
        }

    # Streaming image attachment → construct data URL inline from
    # base64 chunks to preserve existing image behavior (images are
    # never uploaded). Handles stream=True local file images that
    # have data=None and url=None.
    if isinstance(attachment, StreamingFileAttachment) and is_image:
        data_chunks: list[str] = []
        for chunk in attachment.iter_base64_chunks():
            data_chunks.append(chunk)
        data = "".join(data_chunks)
        return {
            "type": "input_image",
            "image_url": f"data:{attachment.mime_type};base64,{data}",
            "detail": "auto",
        }

    # Streaming file attachment with text MIME → read and inline as
    # input_text.  This must come before the generic streaming upload
    # branch to satisfy FR-001b (text-based MIME types must be inlined).
    if isinstance(attachment, StreamingFileAttachment) and is_text_mime(attachment.mime_type):
        text_content = b"".join(attachment.iter_raw_chunks()).decode("utf-8", errors="replace")
        return {"type": "input_text", "text": text_content}

    # Streaming attachment (non-image) → upload via _upload_fn.
    if isinstance(attachment, StreamingFileAttachment):
        if _upload_fn is None:
            raise ValueError(
                "StreamingFileAttachment requires _upload_fn "
                "to upload file content to the provider"
            )
        file_id = await _upload_fn(attachment)
        return {
            "type": "input_file",
            "file_id": file_id,
        }

    # Text-based content (plain text, markdown, code, JSON, CSV, HTML, XML) →
    # decode and send inline as input_text. No upload needed.
    # Also works via input_file + file_data, but input_text preserves raw
    # text content for any OpenAI-compatible provider.
    if attachment.data is not None and is_text_mime(attachment.mime_type):
        import base64 as _base64
        text_content = _base64.b64decode(attachment.data).decode("utf-8", errors="replace")
        return {"type": "input_text", "text": text_content}

    # Non-image data-backed → send inline via file_data as a data URL.
    # The Responses API input_file supports inline base64 content:
    #   {"type": "input_file", "filename": "doc.pdf",
    #    "file_data": "data:application/pdf;base64,<base64>"}
    if attachment.data is not None:
        return {
            "type": "input_file",
            "filename": attachment.filename or "file",
            "file_data": f"data:{attachment.mime_type};base64,{attachment.data}",
        }

    # Non-image URL → download content, send inline via file_data.
    # The Responses API supports inline base64 content via input_file
    # + file_data, so we avoid requiring /v1/files for URL-backed
    # attachments.  This enables OpenAI-compatible local servers
    # (e.g. LM Studio, Ollama) that support Responses but lack a
    # /v1/files endpoint.
    if attachment.url is not None:
        import base64 as _base64  # noqa: PLC0415

        if _download_fn is not None:
            content = await _download_fn(attachment.url)
        else:
            from tinycua_sdk.providers.upload import (  # noqa: PLC0415
                _download_url_content,
            )

            content = await _download_url_content(attachment.url)
        b64_content = _base64.b64encode(content).decode("ascii")
        return {
            "type": "input_file",
            "filename": attachment.filename or "downloaded_file",
            "file_data": (
                f"data:{attachment.mime_type};base64,{b64_content}"
            ),
        }

    raise ValueError(
        "Attachment has no usable source (data, url, or file_id required)"
    )


async def _translate_responses_content_part(
    part: ContentPart,
    *,
    _upload_fn: Callable[[FileAttachment], Awaitable[str]] | None = None,
    _download_fn: Callable[[str], Awaitable[bytes]] | None = None,
) -> dict[str, Any]:
    """Translate a ``ContentPart`` to a Responses content part dict.

    - Text part (``type="text"``) → ``{"type": "input_text", "text": ...}``
    - File part (``type="file"``) → delegates to
      :func:`_translate_responses_attachment`.

    Args:
        part: A canonical ``ContentPart``.
        _upload_fn: Optional async callable for uploads (passed through to
            attachment translation).
        _download_fn: Optional async callable for URL downloads (passed
            through to attachment translation).

    Returns:
        A dict with ``type`` and the appropriate content key.
    """
    if part.type == "text":
        return {"type": "input_text", "text": part.text}

    if part.type == "file":
        if part.file is None:
            raise ValueError("ContentPart with type='file' must have a non-None file")
        return await _translate_responses_attachment(
            part.file, _upload_fn=_upload_fn, _download_fn=_download_fn,
        )

    raise ValueError(f"Unknown ContentPart type: {part.type!r}")


async def _translate_responses_user_message(
    msg: dict[str, Any],
    *,
    _upload_fn: Callable[[FileAttachment], Awaitable[str]] | None = None,
    _download_fn: Callable[[str], Awaitable[bytes]] | None = None,
) -> dict[str, Any]:
    """Translate a user message dict for the OpenAI Responses API.

    Handles three input shapes:

    1. Plain string content, no attachments → pass through unchanged
       (backward compatible).
    2. String content with non-empty ``attachments`` → text part followed
       by file/image parts.
    3. ``content: list[ContentPart | dict]`` (with or without
       attachments) → translated parts, with message-level attachments
       appended after explicit content parts, preserving caller order
       within each group.

    The ``attachments`` key is always stripped from the output (not a
    valid Responses API field).

    Args:
        msg: A message dict with ``role``, ``content``, and optionally
            ``attachments``.
        _upload_fn: Optional async callable for uploads (passed through to
            attachment translation).
        _download_fn: Optional async callable for URL downloads (passed
            through to attachment translation).

    Returns:
        A translated message dict suitable for the Responses API.

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
            parts.append({"type": "input_text", "text": content})
        for att in attachments:
            parts.append(
                await _translate_responses_attachment(
                    att, _upload_fn=_upload_fn, _download_fn=_download_fn,
                ),
            )
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
                parts.append(
                    await _translate_responses_content_part(
                        item, _upload_fn=_upload_fn, _download_fn=_download_fn,
                    ),
                )
            elif isinstance(item, dict):
                coerced = ContentPart(**item)
                parts.append(
                    await _translate_responses_content_part(
                        coerced, _upload_fn=_upload_fn, _download_fn=_download_fn,
                    ),
                )
            else:
                raise ValueError(
                    f"Unsupported content part type: expected ContentPart "
                    f"or dict, got {type(item).__name__}"
                )

        for att in attachments:
            parts.append(
                await _translate_responses_attachment(
                    att, _upload_fn=_upload_fn, _download_fn=_download_fn,
                ),
            )

        result["content"] = parts
        remaining = {k: v for k, v in msg.items() if k not in ("content", "attachments")}
        result.update(remaining)
        return result

    raise ValueError(
        f"Unsupported user message content type: expected str or list, "
        f"got {type(content).__name__}"
    )



# ── Responses event normalization ─────────────────────────────────────────────


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


def _normalize_reasoning_event(event: dict[str, Any]) -> list[LLMEvent]:
    """Normalize a reasoning-related stream event into canonical events.

    Handles these raw event types from the OpenAI Responses API:

    * ``response.reasoning.delta`` — streaming chain-of-thought tokens
      (OpenAI standard, e.g. o-series models).
    * ``response.reasoning.summary`` — end-of-reasoning marker (OpenAI).
    * ``response.reasoning_text.delta`` — alternative token event used by
      LiteLLM / proxy servers that wrap Chat Completions reasoning into
      the Responses API format.
    * ``response.reasoning_text.done`` — end-of-reasoning marker for the
      ``reasoning_text`` variant.

    All delta variants produce ``ReasoningDeltaEvent``; all done/summary
    variants produce ``ReasoningDoneEvent``.

    Args:
        event: Raw Responses API stream event dict.

    Returns:
        List of canonical SDK stream events.
    """
    event_type = event.get("type", "")
    if event_type in ("response.reasoning.delta", "response.reasoning_text.delta"):
        return [
            ReasoningDeltaEvent(
                type="response.reasoning.delta",
                delta=event.get("delta", ""),
            ),
        ]
    if event_type in ("response.reasoning.summary", "response.reasoning_text.done"):
        return [ReasoningDoneEvent(type="response.reasoning.done")]
    return []


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


def _normalize_lifecycle_event(event: dict[str, Any]) -> list[LLMEvent]:
    """Normalize a lifecycle-related stream event into canonical events.

    Handles ``response.created``, ``response.in_progress``,
    ``response.completed``, ``response.failed``, ``response.cancelled``,
    and ``response.usage``. The completed event may also embed a nested
    usage object that gets emitted as a separate ``response.usage``
    event before the completion event.

    Args:
        event: Raw Responses API stream event dict.

    Returns:
        List of canonical SDK stream events.
    """
    event_type = event.get("type", "")

    if event_type == "response.created":
        return [ResponseCreatedEvent(type="response.created")]

    if event_type == "response.in_progress":
        return [ResponseInProgressEvent(type="response.in_progress")]

    if event_type == "response.cancelled":
        return [ResponseCancelledEvent(type="response.cancelled")]

    if event_type == "response.completed":
        finish_reason = event.get("finish_reason")
        if not finish_reason:
            status = event.get("response", {}).get("status", "completed")
            _FINISH_REASON_MAP = {"completed": "stop", "incomplete": "length", "failed": "error"}
            finish_reason = _FINISH_REASON_MAP.get(status, "stop")
            if status == "completed":
                output = event.get("response", {}).get("output", [])
                if any(
                    isinstance(item, dict) and item.get("type") == "function_call"
                    for item in output
                ):
                    finish_reason = "tool_calls"
        result: list[LLMEvent] = [ResponseCompletedEvent(type="response.completed", finish_reason=finish_reason)]
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

    if event_type in ("response.output_text.delta", "response.output_text.done"):
        return _normalize_content_event(event)

    if event_type in (
        "response.output_item.added",
        "response.function_call_arguments.delta",
        "response.function_call_arguments.done",
    ):
        return _normalize_tool_event(event, _tool_cache)

    if event_type in (
        "response.created",
        "response.in_progress",
        "response.completed",
        "response.failed",
        "response.usage",
        "response.cancelled",
    ):
        return _normalize_lifecycle_event(event)

    if event_type in (
        "response.reasoning.delta",
        "response.reasoning.summary",
        "response.reasoning_text.delta",
        "response.reasoning_text.done",
    ):
        return _normalize_reasoning_event(event)

    return []


class OpenAIResponsesClient(LLMClient):
    """OpenAI Responses API provider client wrapping the official openai SDK.

    Uses ``openai.responses.create()`` for non-streaming and
    ``client.responses.create(stream=True)`` for streaming.
    Uses shared module-level functions for event normalization.

    Accepts an optional ``UploadSession`` for file upload deduplication
    and persistent caching.
    """

    def __init__(
        self,
        model_config: LanguageModel,
        upload_session: Any | None = None,  # UploadSession from providers.upload
    ) -> None:
        self._model_config = model_config
        self._client: AsyncOpenAI | None = None
        self._previous_response_id: str | None = None

        if upload_session is not None:
            self._upload_session = upload_session
        else:
            from tinycua_sdk.providers.upload import UploadSession  # noqa: PLC0415

            self._upload_session = UploadSession()

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            from openai import AsyncOpenAI

            # Resolve API key: explicit > OPENAI_RESPONSES_API_KEY
            api_key = self._model_config.api_key.get_secret_value() if self._model_config.api_key else None
            if not api_key:
                api_key = os.environ.get("OPENAI_RESPONSES_API_KEY")

            # Resolve base URL: explicit > OPENAI_RESPONSES_BASE_URL > LLM_BASE_URL > OpenAI default
            base_url = self._model_config.base_url
            if not base_url:
                base_url = (
                    os.environ.get("OPENAI_RESPONSES_BASE_URL")
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

        for field in _SUPPORTED_FIELDS:
            value = getattr(self._model_config, field, None)
            if value is not None:
                mapped = _FIELD_MAP.get(field, field)
                if mapped == "text":
                    kwargs[mapped] = {"format": value}
                else:
                    kwargs[mapped] = value

        if tools:
            kwargs["tools"] = _translate_tools(tools)
            if "tool_choice" not in kwargs:
                kwargs["tool_choice"] = "auto"

        return kwargs

    async def _ensure_uploaded_file_id(self, attachment: FileAttachment) -> str:
        """Upload a file through the OpenAI API and return its ``file_id``.

        Delegates to :class:`UploadSession.ensure_file_id` for cache
        lookup, persistent cache integration, and concurrent upload
        deduplication.

        Args:
            attachment: A data-backed ``FileAttachment``.

        Returns:
            The OpenAI ``file_id`` string.

        Raises:
            ValueError: If the attachment has no ``data`` source.
        """
        return await self._upload_session.ensure_file_id(
            self._get_client(), attachment,
        )

    async def _translate_responses_input(
        self,
        messages: list[LLMMessage],
    ) -> list[dict[str, Any]]:
        """Translate canonical messages to Responses API ``input`` items.

        Uses :func:`_translate_responses_user_message` for user messages
        that may carry attachments or ``ContentPart`` content, and the
        module-level :func:`_translate_messages` for all other message
        types (system, assistant, tool_result). This method is async
        because attachment translation may involve file uploads.

        Args:
            messages: Canonical message list.

        Returns:
            Provider-native input items for the Responses API ``input`` array.
        """
        # URL download wrapper that threads the configured upload_timeout
        # into URL-based attachment translation (FR-014).
        async def _download_url(url: str) -> bytes:
            from tinycua_sdk.providers.upload import (  # noqa: PLC0415
                _download_url_content,
            )

            return await _download_url_content(
                url, timeout=self._upload_session.upload_timeout,
            )

        result: list[dict[str, Any]] = []
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "user":
                translated = await _translate_responses_user_message(
                    msg,  # type: ignore[arg-type]
                    _upload_fn=self._ensure_uploaded_file_id,
                    # _upload_session is always created in __init__
                    _download_fn=_download_url,
                )
                result.append(translated)
            else:
                result.extend(_translate_messages([msg]))
        return result

    @staticmethod
    def _handle_provider_error(e: Exception, context: str = "OpenAI API") -> None:
        status_code = getattr(e, "status_code", 0)
        if status_code in (401, 403):
            raise ProviderAuthError(str(e)) from e
        if "auth" in str(e).lower() or "credential" in str(e).lower():
            raise ProviderAuthError(str(e)) from e
        raise ProviderApiError(status_code, f"{context} error: {e}") from e

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
        try:
            translated_input = await self._translate_responses_input(messages)
            kwargs = self._build_request_kwargs(translated_input, tools)
            client = self._get_client()
            response = await client.responses.create(**kwargs)
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
        self._previous_response_id = data.get("id", None) or None
        data["model"] = data.get("model", self._model_config.model_name)
        return self._normalize_non_streaming_response(data)

    async def _chat_stream(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None,
        raw_events: bool = False,
    ) -> AsyncIterator[LLMEvent] | AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]:
        try:
            translated_input = await self._translate_responses_input(messages)
            kwargs = self._build_request_kwargs(translated_input, tools)
            kwargs["stream"] = True
            client = self._get_client()
            stream = await client.responses.create(**kwargs)
        except (ValueError, ProviderApiError, ProviderAuthError):
            raise
        except Exception as e:
            self._handle_provider_error(e)

        tool_cache: dict[str, dict[str, str]] = {}
        try:
            async for event in stream:
                data = event.model_dump() if hasattr(event, "model_dump") else event.dict() if hasattr(event, "dict") else {}
                if data.get("type") in ("response.created", "response.completed"):
                    nested = data.get("response", {})
                    self._previous_response_id = (
                        nested.get("id") or data.get("id") or None
                    )
                events = _normalize_responses_event(data, _tool_cache=tool_cache)
                raw_event_obj = RawSseEvent(provider=self._model_config.provider, raw_event=event)
                for item in _yield_events(events, raw_event_obj, raw_events):
                    yield item  # type: ignore[misc]
        except Exception as e:
            self._handle_provider_error(e, context="OpenAI API stream")


__all__ = [
    "OpenAIResponsesClient",
]
