# Design Document: OpenAI Chat Completions File Attachment Translation

**Spec**: `./spec.md`
**Status**: Complete
**Last Updated**: 2026-05-20

---

## Overview

This design extends the existing `OpenAIChatCompletionsClient` message translation path so canonical Phase 1 file attachment shapes are converted into Chat Completions multimodal message content. The implementation remains isolated to `tinycua-sdk`: add small translation helpers near `_translate_chat_messages()`, reuse the existing `FileAttachment` and `ContentPart` models, preserve string-only payload behavior, and add tests that prove both canonical attachment forms become Chat Completions `text` and `image_url` content parts.

---

## Architecture

### Component Overview

```
Caller Code
    |
    v
UserMessage
  ├─ content: str
  │    └─ optional attachments: list[FileAttachment]
  └─ content: list[ContentPart]
    |
    v
OpenAIChatCompletionsClient._translate_chat_messages()
    |
    ├─ _translate_chat_message_content()
    │    ├─ text part -> {"type": "text", "text": ...}
    │    └─ file part -> {"type": "image_url", "image_url": {"url": ...}}
    |
    v
Chat Completions payload
  messages=[{"role": "user", "content": [text parts, image_url parts]}]
    |
    v
OpenAI Chat Completions API
```

The current Chat Completions provider already has a dedicated translation path and payload builder. This phase modifies only that path for user-message file content. Responses API translation remains unchanged until Phase 3.

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua_sdk/providers/open_ai.py` | Modified | Extend `OpenAIChatCompletionsClient._translate_chat_messages()` and add helper functions for content/attachment translation |
| `tinycua_sdk/models/attachment.py` | Reused | Existing `FileAttachment` and `ContentPart` models are consumed; no schema changes |
| `tinycua_sdk/agent/events.py` | Reused | Existing `UserMessage.content` union and `attachments` field are consumed; no schema changes |
| `tests/unit/test_openai_chat_client.py` | Modified | Add unit tests for Chat Completions file attachment payload translation |
| `tests/integration/test_openai_chat_completions_provider.py` | Modified | Add guarded image attachment integration test |

---

## Data Model

### New Entities

No new public entities are introduced. Phase 2 consumes these Phase 1 models:

```python
FileAttachment:
    data: str | None
    mime_type: str
    filename: str | None
    url: str | None
    file_id: str | None

ContentPart:
    type: Literal["text", "file"]
    text: str | None
    file: FileAttachment | None
```

### Schema Changes

- No changes to canonical message schemas.
- No changes to `LanguageModel`, `LLMResponse`, streaming events, or provider registry entries.
- Chat Completions provider request content changes only when a user message contains `list[ContentPart]` or non-empty `attachments`.
- Existing plain string messages remain translated as plain string `content` values.

### Provider-Native Content Shapes

```python
# Text content part
{"type": "text", "text": "What is in this image?"}

# Image content part backed by data URL
{
    "type": "image_url",
    "image_url": {"url": "data:image/png;base64,<encoded>"},
}

# Image content part backed by URL
{
    "type": "image_url",
    "image_url": {"url": "https://example.com/image.png"},
}
```

---

## API / Interface Contracts

### Modified Message Translation

```python
class OpenAIChatCompletionsClient(LLMClient):
    def _translate_chat_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Translate canonical messages to Chat Completions messages.

        Existing behavior:
        - system/user/assistant string messages pass through
        - assistant messages with tool_calls pass through
        - tool_result messages become role="tool"
        - assistant tool_calls are injected before tool_result batches when needed

        New Phase 2 behavior:
        - user messages with list[ContentPart] become multimodal content lists
        - user messages with content: str and attachments become text + image_url content lists
        """
```

### Translation Helper Contracts

```python
def _translate_chat_user_message(msg: dict[str, Any]) -> dict[str, Any]:
    """Return a Chat Completions user message.

    Plain string content without attachments remains unchanged.
    Structured content and/or attachments are normalized to a provider-native
    content list. When both list[ContentPart] content and non-empty attachments
    are present, message-level attachments are appended after the explicit
    content parts in caller order.
    """


def _translate_chat_content_part(part: ContentPart) -> dict[str, Any]:
    """Map one canonical ContentPart to one Chat Completions content part."""


def _translate_chat_attachment(attachment: FileAttachment) -> dict[str, Any]:
    """Map an image FileAttachment to an image_url content part."""
```

These helpers may live as private module-level functions or private static methods on `OpenAIChatCompletionsClient`. Module-level helpers are preferred if they are testable without client state.

### Normalization Rules

| Canonical input | Provider output |
|-----------------|-----------------|
| `{"role": "user", "content": "hello"}` | `{"role": "user", "content": "hello"}` |
| `{"role": "user", "content": "describe", "attachments": [img]}` | `{"role": "user", "content": [{"type": "text", "text": "describe"}, image_part]}` |
| `{"role": "user", "content": [ContentPart(type="text", ...), ContentPart(type="file", ...)]}` | `{"role": "user", "content": [text_part, image_part]}` |
| `{"role": "user", "content": [ContentPart(type="text", ...)], "attachments": [img]}` | `{"role": "user", "content": [text_part, image_part]}` — message-level attachments append after explicit content parts |
| `FileAttachment(data=..., mime_type="image/png")` | `{"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}` |
| `FileAttachment(url="https://...", mime_type="image/jpeg")` | `{"type": "image_url", "image_url": {"url": "https://..."}}` |

For `content: str` plus attachments, the translated text part is omitted only when the string is empty. Attachments still translate in order.

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| `FileAttachment.file_id` without `data` or `url` | `ValueError` | Chat Completions Phase 2 has no upload/cache mapping |
| Non-image MIME type | `ValueError` | Reject before provider request; arbitrary file support is deferred |
| Malformed `ContentPart` | Existing Pydantic validation error | Model construction should normally catch this before translation |
| Missing file on disk | Existing `FileNotFoundError` | Raised by `FileAttachment.from_path()` before translation |
| OpenAI rejects multimodal payload | Existing provider error translation | `_handle_provider_error()` wraps SDK errors as before |

---

## Implementation Phases

### Phase 1 — Tests First

- [ ] Add unit tests for explicit `list[ContentPart]` translation to Chat Completions `text` and `image_url` parts.
- [ ] Add unit tests for `content: str` plus `attachments` translation.
- [ ] Add unit tests for inline data URL construction and URL-backed attachment pass-through.
- [ ] Add unit tests for multiple attachments and ordering.
- [ ] Add unit tests for unsupported MIME types and `file_id`-only attachments.
- [ ] Add or update a guarded integration test for sending an image attachment through the Chat Completions provider.

### Phase 2 — Translation Helpers

- [ ] Import or reference `ContentPart` and `FileAttachment` in `tinycua_sdk/providers/open_ai.py`.
- [ ] Implement a private attachment-to-image-content helper.
- [ ] Implement a private content-part translation helper.
- [ ] Implement a private user-message translation helper that combines string content and message-level attachments.

### Phase 3 — Wire Into Chat Completions Client

- [ ] Call the new user-message translation helper from `_translate_chat_messages()` for `role="user"` messages.
- [ ] Preserve existing assistant `tool_calls` pass-through and tool-result injection behavior.
- [ ] Preserve existing string-only payload output for messages without attachments.

### Phase 4 — Verification

- [ ] Run Chat Completions unit tests.
- [ ] Run relevant integration tests with network tests skipped by default.
- [ ] Run the broader tinycua-sdk test suite if practical.

---

## Technical Decisions

1. **Decision**: Translate image attachments to Chat Completions `image_url` content parts.
   - **Reason**: Chat Completions expects multimodal user message content as typed content parts, with images represented by `image_url` entries. This matches both URL-backed files and base64 data URLs.
   - **Alternatives Considered**: Pass canonical `FileAttachment` objects through unchanged — rejected because the provider API does not understand SDK canonical models.

2. **Decision**: Keep string-only user messages as plain strings when there are no attachments.
   - **Reason**: This minimizes payload changes and protects existing tests and callers from unnecessary request shape changes.
   - **Alternatives Considered**: Convert every user message to `[{"type": "text", ...}]` — rejected because it changes the payload shape for no functional gain.

3. **Decision**: For `content: str` plus attachments, emit the text part first, then image parts in attachment order.
   - **Reason**: The basic message shape represents text plus a separate attachment list. Placing text first preserves the natural prompt-before-evidence ordering.
   - **Alternatives Considered**: Place attachments first or interleave by filename — rejected because message-level attachments do not carry ordering relative to substrings.

4. **Decision**: Reject `file_id`-only attachments in Chat Completions Phase 2.
   - **Reason**: The Chat Completions image input path does not use the Responses upload/file ID flow planned for Phase 3 and Phase 5. Failing clearly prevents silent data loss.
   - **Alternatives Considered**: Ignore `file_id` or attempt provider upload — rejected because ignoring is unsafe and upload/cache behavior belongs to later phases.

5. **Decision**: Reject non-image MIME types for this Chat Completions phase.
   - **Reason**: The scoped provider-native mapping is `image_url`. Sending PDFs, audio, or video through an image slot would produce confusing provider errors.
   - **Alternatives Considered**: Let the provider reject all unsupported files — rejected because SDK-side validation can produce clearer errors and protect tests from network-dependent failures.

6. **Decision**: Keep translation helpers private to the OpenAI provider module.
   - **Reason**: The mapping is provider-specific. A shared canonical-to-provider adapter would be premature before Responses translation and other providers establish common patterns.
   - **Alternatives Considered**: Add a reusable multimodal translation abstraction now — rejected as overengineering for one provider path.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing string-only Chat Completions payloads change unexpectedly | Low | High | Preserve the exact string-content path when no attachments are present; add regression tests |
| Chat Completions accepts only image inputs while canonical model supports broader files | High | Medium | Reject non-image MIME types clearly and document broader support as provider-permitting future work |
| Data URLs become large payloads | Medium | Medium | Phase 2 accepts existing inline data behavior; file upload/cache and streaming remain Phase 5 work |
| Tool-result injection logic regresses while modifying message translation | Medium | High | Keep tool-result branch structure intact and retain existing unit tests |
| Integration tests depend on external API credentials | High | Low | Guard network tests behind environment configuration and keep unit tests comprehensive |

---

## Open Questions

*(No open questions — the provider format, error boundaries, and phase scope are decided for implementation.)*

---

## References

- Spec: `./spec.md`
- Phase 1 Spec: `../sdk-file-attachment-phase1/spec.md`
- Phase 1 Design: `../sdk-file-attachment-phase1/design.md`
- Chat Completions Provider Spec: `../openai-chat-completions/spec.md`
- Chat Completions Provider Design: `../openai-chat-completions/design.md`
- Issue #46: SDK-wide File Attachment Support (https://github.com/VJyzCELERY/TINYCUA/issues/46)
