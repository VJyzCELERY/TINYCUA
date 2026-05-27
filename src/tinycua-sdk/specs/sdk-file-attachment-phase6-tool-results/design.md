# Design Document: Phase 6 — Tool Result File Support

**Spec**: `./spec.md`
**Status**: Complete
**Last Updated**: 2026-05-26

---

## Overview

This design completes SDK-wide file attachment support by carrying canonical file attachment shapes through tool execution and into the next provider request. The key decision is to introduce a small shared normalization path for tool return values, then reuse the existing user-message attachment translation helpers for tool-result content in both OpenAI Chat Completions and OpenAI Responses providers. The affected subproject is `tinycua-sdk`, primarily `agent/loop.py` and the two OpenAI provider translators.

---

## Architecture

### Component Overview

```
Tool implementation
  ├─ returns "plain text"                         → legacy string tool result
  ├─ returns {"content": "text", "attachments": [FileAttachment(...)]}
  └─ returns {"content": [ContentPart(...), ...]}

BaseLoop.process_tool_calls()
BaseLoop.process_stream_tool_calls()
  └─ normalize_tool_result(call_id, tool_result)
       └─ canonical ToolResultMessage

working messages
  └─ {"role": "tool_result", "call_id": ..., "content": ..., "attachments"?: ...}

Provider translation for next turn
  ├─ Chat Completions: assistant tool_calls + text-only tool message + synthetic user message with attachments
  └─ Responses: function_call_output carrying translated multimodal output content
```

The normalization step is intentionally small: it detects the canonical shapes already promised by `ToolResultMessage`, validates enough to avoid accidental data loss, and falls back to the existing `str(tool_result)` behavior for all legacy values.

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua_sdk/agent/loop.py` | Modified | Add shared tool-result normalization and use it from sync and streaming tool-call paths |
| `tinycua_sdk/agent/events.py` | Not Modified | Existing contracts already support structured tool results |
| `tinycua_sdk/providers/open_ai_chat_completions.py` | Modified | Translate tool-result `ContentPart` and `attachments` into text-only tool message + synthetic user message (Chat Completions requires text-only tool content parts) |
| `tinycua_sdk/providers/open_ai_responses.py` | Modified | Translate tool-result `ContentPart` and `attachments` into function-call output content |
| `tests/unit/test_loop.py` | Modified | Add normalization tests for non-streaming tool results |
| `tests/unit/test_loop_custom.py` | Not Modified | Existing contracts already support structured tool results |
| `tests/unit/test_openai_chat_client.py` | Modified | Add Chat Completions tool-result attachment translation tests |
| `tests/unit/test_llm_client.py` | Modified | Add Responses tool-result attachment translation tests |
| `tests/integration/test_tool_result_attachments.py` | New | End-to-end mocked integration for tool-generated file handoff |

---

## Data Model

No new public entities are required. Phase 6 relies on the existing canonical message and attachment types. However, the runtime behavior of `ToolResultMessage` changes — its `content: str | list[ContentPart]` union is now fully honored by the agent loop and provider translators, activating structured fields that were previously documented but not enforced at runtime.

### Modified Tool Result Shape

```python
ToolResultMessage:
    role: Literal["tool_result"]
    call_id: str
    content: str | list[ContentPart]
    attachments: NotRequired[list[FileAttachment]]
```

### Accepted Tool Return Shapes

```python
# Legacy — unchanged
"created image successfully"

# Basic message + attachments
{
    "content": "The tool generated this image.",
    "attachments": [FileAttachment.from_path("chart.png")],
}

# Explicit multipart content
{
    "content": [
        ContentPart(type="text", text="The tool generated this image."),
        ContentPart(type="file", file=FileAttachment.from_path("chart.png")),
    ],
}

# Fully canonical tool result; call_id may be overwritten by the loop
{
    "role": "tool_result",
    "call_id": "call_abc",
    "content": "The tool generated this image.",
    "attachments": [FileAttachment.from_path("chart.png")],
}
```

Schema compatibility (detection rules, evaluated in order):

1. If `content` is a non-empty list (of dicts or ContentParts), treat as structured multipart content (attachments optional).
2. If `content` is a string AND `attachments` is a list-like attachment value, treat as structured with message-level attachments.
3. If `role == "tool_result"`, treat as a pre-formed canonical message. This rule is evaluated after empty-content-list rejection — an empty content list raises ``ValueError`` regardless of role, including for ``role == "tool_result"``.
4. If the tool result is not a recognized structured shape (including non-dict values like ``None``, ``list``, or custom objects), it remains legacy and is converted to ``str(tool_result)``.
5. The loop owns ``role`` and ``call_id``; tool-provided ``role``/``call_id`` values are ignored or overwritten to preserve the actual tool-call linkage.

**Empty list rejection**: Any tool result whose ``content`` is an empty list (``[]`` or ``list()``) raises a ``ValueError`` with a message identifying the empty content part list as invalid. This rejection is evaluated before any detection rules — empty lists raise ``ValueError`` regardless of whether ``role == "tool_result"`` or any other structured field is present.

---

## API / Interface Contracts

### Tool Result Normalization

```python
# Import note: ContentPart and FileAttachment are canonical types from tinycua_sdk.models.
# The content union accepts raw dicts in addition to ContentPart instances so that tools
# may return plain dicts matching the ContentPart shape without importing the model module.

class NormalizedToolResult(TypedDict):
    role: Literal["tool_result"]
    call_id: str
    content: str | list[ContentPart | dict[str, Any]]
    attachments: NotRequired[list[FileAttachment]]


def normalize_tool_result(call_id: str, tool_result: Any) -> NormalizedToolResult:
    """
    Convert a tool return value into a canonical ToolResultMessage.

    Supported structured inputs:
    - {"content": list[ContentPart | dict]}  # explicit multipart, no attachments
    - {"content": str | list[ContentPart | dict], "attachments": list[FileAttachment]}
    - {"role": "tool_result", "content": ..., "attachments"?: ...}

    Fallback:
    - Any unsupported value returns {"role": "tool_result", "call_id": call_id,
      "content": str(tool_result)}.
    """
```

The function is exported from the agent loop module (no underscore prefix) to support direct unit testing of normalization logic. Public `BaseLoop.process_tool_calls()` and `BaseLoop.process_stream_tool_calls()` remain the supported extension points for custom loop subclasses.

### Chat Completions Tool Result Translation

```python
# Internal to open_ai_chat_completions.py — called from _translate_chat_messages()
# when processing tool_result messages. Because the Chat Completions API only
# supports `text` content parts in `role: "tool"` messages, this translator
# emits a two-message sequence:
#
#   1. A text-only `role: "tool"` message carrying text content parts and the
#      required `tool_call_id`.
#   2. A follow-up synthetic `role: "user"` message carrying file/image content
#      parts translated from ContentPart file items and message-level attachments.
#
# If the tool result has no file/image parts, only the text-only tool message is
# emitted. The assistant `tool_calls` message ordering is preserved throughout.

async def _translate_chat_tool_result_batch(
    msgs: list[dict[str, Any]],
    *,
    _upload_fn: Callable[[FileAttachment], Awaitable[str]] | None = None,
) -> list[dict[str, Any]]:
    """
    Translate canonical ToolResultMessages to Chat Completions message sequence.

    Plain string content, no attachments:
        [{"role": "tool", "tool_call_id": call_id, "content": content}]

    Text ContentPart only, no file attachments:
        [{"role": "tool", "tool_call_id": call_id, "content": [{"type": "text", "text": ...}]}]

    Mixed text + file content or message-level attachments:
        [{"role": "tool", "tool_call_id": call_id, "content": [{"type": "text", "text": ...}]},
         {"role": "user", "content": [{"type": "image_url", "image_url": ...}, ...]}]
    """
```

Rationale: The OpenAI Chat Completions API schema explicitly states "For tool messages, only type `text` is supported" in the `ChatCompletionRequestToolMessage.content` field. Placing file/image content parts in a user message is the provider-compatible way to make generated attachments available for the next model turn while preserving required `assistant tool_calls` → `tool` response ordering.

### Responses Tool Result Translation

```python
async def _translate_responses_tool_result_message(
    msg: dict[str, Any],
    *,
    _upload_fn: Callable[[FileAttachment], Awaitable[str]] | None = None,
    _download_fn: Callable[[str], Awaitable[bytes]] | None = None,
) -> dict[str, Any]:
    """
    Translate canonical ToolResultMessage to Responses function_call_output.

    Plain string content, no attachments:
        {"type": "function_call_output", "call_id": call_id, "output": content}

    Structured content or attachments:
        {"type": "function_call_output", "call_id": call_id, "output": [
            provider content parts — Verified Responses API contract: the Responses
            API accepts ``function_call_output.output`` as a list of content parts
            (``input_text``, ``input_image``, ``input_file``), matching the same
            multimodal output shapes used for user messages (see Phase 5).
        ]}
    """
```

This helper reuses `_translate_responses_content_part()` and `_translate_responses_attachment()` so Phase 5 text, file, URL, streaming, and cache behavior remains centralized.

Note on parameter asymmetry: Chat Completions translation only requires `_upload_fn` because file content is converted to base64 data URIs or uploaded via the files API for `file_id` references. Responses translation additionally requires `_download_fn` for non-image URL attachments that become inline `input_file.file_data`. image URLs remain URL references (passed through as `input_image.image_url`) and do NOT require download; data-backed image/file attachments reuse existing inline paths from Phase 5, preserving the established behavior where only non-image URL content is downloaded for embedding.

### Error Handling

| Error Case | Exception / Behavior | Notes |
|------------|---------------------|-------|
| Tool raises before returning | Existing string error result | Backward compatible |
| Tool returns unsupported value | `str(tool_result)` fallback | Backward compatible |
| Tool returns invalid structured content part | Existing `ValueError` from content-part validation | Prevents silent file loss |
| Tool returns empty `list[ContentPart]` | `ValueError` with clear message | Reject with ValueError identifying the empty content part list as invalid |
| Attachment upload/download fails | Existing provider errors | Reuses Phase 5 paths |
| Provider rejects multimodal tool outputs | Provider API error surfaces unchanged | Capability-specific failure |

---

## Implementation Stages

### Stage 1 — Tests First

- [ ] Add failing integration test for non-streaming tool-generated image handoff.
- [ ] Add failing integration test for streaming tool-generated image handoff.
- [ ] Add failing unit tests for loop normalization of both canonical attachment forms.
- [ ] Add failing provider translation tests for Chat Completions and Responses tool-result attachments.

### Stage 2 — Agent Loop Normalization

- [ ] Add internal tool-result normalization helper.
- [ ] Update `process_tool_calls()` to append normalized structured tool results.
- [ ] Update `process_stream_tool_calls()` to append normalized structured tool results.
- [ ] Preserve legacy string behavior for non-structured tool returns and errors.

### Stage 3 — Provider Translation

- [ ] Add Chat Completions helper for translating structured tool-result content.
- [ ] Wire helper into `_translate_chat_messages()` for each tool-result message in a batch.
- [ ] Add Responses helper for translating structured tool-result content.
- [ ] Wire helper into `_translate_responses_input()` / `_translate_messages()` path without duplicating attachment logic.

### Stage 4 — Verification and Docs

- [ ] Run focused unit and integration tests — all must pass.
- [ ] Run full tinycua-sdk test suite.
- [ ] Run Phase 5 upload/cache regression tests to confirm existing paths still work.
- [ ] Update public docs or README snippets to document tool-returned attachment support.
- [ ] Optional real-provider smoke test with a vision-capable model.

---

## Technical Decisions

1. **Decision**: Normalize structured tool returns in the agent loop rather than inside each provider.
   - **Reason**: The loop is the only place that knows the true `call_id` and whether a tool result came from successful execution or an execution error. Normalizing once prevents provider-specific divergence.
   - **Alternatives Considered**: Let tools return provider-native payloads — rejected because it breaks the canonical SDK abstraction and duplicates provider knowledge in tools.

2. **Decision**: Reuse user-message attachment translation helpers for tool-result content.
   - **Reason**: Phase 1–5 already centralized MIME mapping, URL download, upload, cache, streaming, and `file_id` behavior. Reusing those helpers keeps Phase 6 small and avoids new attachment semantics.
   - **Alternatives Considered**: Build separate tool-result-only attachment mappers — rejected as duplication with higher regression risk.

3. **Decision**: Preserve legacy fallback for unsupported tool return values.
   - **Reason**: Existing tools may return arbitrary dicts, lists, numbers, or objects that callers expect to be stringified. Only explicitly supported canonical shapes should become structured messages.
   - **Alternatives Considered**: Treat all dicts as structured — rejected because it would change behavior for common dict-returning tools.

4. **Decision**: Keep `call_id` controlled by the loop.
   - **Reason**: Provider APIs require tool outputs to match the actual previous tool call. Allowing a tool-returned `call_id` to override the loop's call ID could corrupt message ordering.
   - **Alternatives Considered**: Trust tool-provided `call_id` — rejected because it is unsafe and unnecessary.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Provider APIs do not support multimodal tool outputs uniformly | Medium | High | Tests should validate current provider-native payload shape; unsupported provider errors surface clearly. |
| Dict-returning legacy tools are mistakenly treated as structured | Medium | Medium | Structured detection requires explicit `content` plus valid attachment/content-part shape; otherwise fallback to string. |
| Chat Completions tool message content arrays do not support image/file parts | High | Medium | Use two-message approach: text-only tool message + synthetic user message for attachments; model errors surface as provider API errors. |
| Responses `function_call_output.output` may require string-only output for some servers | — | — | Resolved — Verified Responses API contract confirms ``output`` supports a list of content parts (``input_text``, ``input_image``, ``input_file``) for ``function_call_output`` messages, matching the multimodal output shapes already used for user messages. No fallback needed. **Validation evidence**: Checked against the OpenAI Responses API reference documentation (Create a Response endpoint — source: https://platform.openai.com/docs/api-reference/responses/create, ``function_call_output.output`` field description) on 2026-05-26. The API reference explicitly lists ``input_text``, ``input_image``, and ``input_file`` as valid content part types for the ``output`` array. This was validated before implementation per the pre-implementation contract check added to task.md. |
| Streaming loop diverges from sync loop | Low | High | Share the same normalization helper and test both paths. |
| Upload cache regressions | Low | Medium | Reuse existing attachment translation and run Phase 5 cache tests. |

---

## References

- Spec: `./spec.md`
- Issue #46: SDK-wide File Attachment Support (https://github.com/VJyzCELERY/TINYCUA/issues/46)
- Phase 1 Spec: `../sdk-file-attachment-phase1/spec.md`
- Phase 2 Chat Completions Spec: `../sdk-file-attachment-phase2-chat-completions/spec.md`
- Phase 3 Responses Spec: `../sdk-file-attachment-phase3-openai-responses/spec.md`
- Phase 4 Agent Integration Design: `../stage-4-agent-loop-integration/design.md`
- Phase 5 Cache/Streaming Design: `../sdk-file-attachment-phase5-cache-streaming/design.md`
