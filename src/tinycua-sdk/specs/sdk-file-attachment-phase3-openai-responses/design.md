# Design Document: OpenAI Responses File Attachment Translation

**Spec**: `./spec.md`
**Status**: Complete
**Last Updated**: 2026-05-21

---

## Overview

This design extends the existing `OpenAIResponsesClient` message translation path so canonical Phase 1 file attachment shapes are converted into OpenAI Responses multimodal input. The implementation stays isolated to `tinycua-sdk`: add Responses-specific content and attachment translation helpers near `_translate_messages()`, reuse the existing `FileAttachment` and `ContentPart` models, preserve string-only and tool-result payload behavior, and add a small provider-client scoped upload cache so repeated attachments can reuse OpenAI `file_id` values within a session.

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
OpenAIResponsesClient._build_request_kwargs()
    |
    v
OpenAIResponsesClient._translate_messages()
    |
    ├─ _translate_responses_user_message(msg)
    │    ├─ string-only content -> pass through unchanged
    │    ├─ _translate_responses_content_part(part) for each ContentPart
    │    │    ├─ text part -> {"type": "input_text", "text": ...}
    │    │    └─ file part -> _translate_responses_attachment(attachment)
    │    └─ _translate_responses_attachment(attachment) for message attachments
    │         ├─ image data/URL -> image input part
    │         ├─ file_id -> file input reference
    │         └─ upload-required data -> upload once, cache file_id, return file input reference
    |
    v
Responses payload
  input=[{"role": "user", "content": [text parts, image/file parts]}]
    |
    v
OpenAI Responses API
```

The current Responses provider has a module-level `_translate_messages()` helper. Because upload/cache behavior needs provider-client state, this phase should move message translation behind the `OpenAIResponsesClient` instance or pass a small upload/cache adapter into the helper. Keeping translation instance-aware is preferred because it avoids global state and naturally scopes cache lifetime to the provider-client session.

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua_sdk/providers/open_ai_responses.py` | Modified | Extend user-message translation for `ContentPart` and `attachments`; add upload/cache helpers |
| `tinycua_sdk/models/attachment.py` | Reused | Existing `FileAttachment` and `ContentPart` models are consumed; no schema changes |
| `tinycua_sdk/agent/events.py` | Reused | Existing `UserMessage.content` union and `attachments` field are consumed; no schema changes |
| `tests/unit/test_llm_client.py` | Modified | Add unit tests for Responses file attachment payload translation and cache behavior |
| `tests/integration/test_openai_responses_provider.py` | New or Modified | Add guarded image attachment integration test for the Responses provider |

---

## Data Model

### New Entities

No new public entities are introduced. Phase 3 consumes these Phase 1 models:

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

Private provider-client state is added for upload reuse:

```python
OpenAIResponsesClient:
    _file_id_cache: dict[str, str]
```

The cache key is a stable provider-local hash derived from the attachment source and MIME metadata. For inline data, use the base64 payload plus MIME type. For URL-backed attachments that require upload, use URL plus MIME type. Attachments that already carry `file_id` bypass the cache.

### Schema Changes

- No changes to canonical message schemas.
- No changes to `LanguageModel`, `LLMResponse`, streaming events, or provider registry entries.
- Responses provider request content changes only when a user message contains `list[ContentPart]` or non-empty `attachments`.
- Existing plain string messages remain translated as plain string `content` values.

### Provider-Native Content Shapes

```python
# Text content part
{"type": "input_text", "text": "What is in this image?"}

# Image content part backed by URL or data URL
{
    "type": "input_image",
    "image_url": "data:image/png;base64,<encoded>",
    "detail": "auto",
}

# File content part backed by provider file ID
{
    "type": "input_file",
    "file_id": "file_abc123",
}

# File content part backed by inline file data when supported
{
    "type": "input_file",
    "filename": "document.pdf",
    "file_data": "data:application/pdf;base64,<encoded>",
}
```

The implementation should prefer the provider-native shape accepted by the installed OpenAI SDK version. If inline `input_file.file_data` is supported for the target MIME/source, it can be used directly. If a file must be uploaded first, the provider upload endpoint should return a `file_id`, which then becomes the content part reference.

---

## API / Interface Contracts

### Modified Responses Translation

```python
class OpenAIResponsesClient(LLMClient):
    def _translate_messages(self, messages: list[LLMMessage]) -> list[dict[str, Any]]:
        """Translate canonical messages to Responses input items.

        Existing behavior:
        - system/user/assistant string messages pass through
        - tool_result messages become function_call_output items

        New Phase 3 behavior:
        - user messages with list[ContentPart] become multimodal content lists
        - user messages with content: str and attachments become text + file content lists
        - upload-required attachments can be converted to cached file_id references
        """
```

The existing module-level `_translate_messages()` can remain as a pure helper for no-upload cases, but the client request path must use the instance-aware translation that has access to `_file_id_cache` and the OpenAI SDK client.

### Translation Helper Contracts

```python
def _translate_responses_user_message(msg: dict[str, Any]) -> dict[str, Any]:
    """Return a Responses user input message.

    Plain string content without attachments remains unchanged. Structured
    content and/or attachments are normalized to a provider-native content
    list. When both list[ContentPart] content and non-empty attachments are
    present, message-level attachments are appended after explicit content
    parts in caller order.
    """


def _translate_responses_content_part(part: ContentPart) -> dict[str, Any]:
    """Map one canonical ContentPart to one Responses content part."""


async def _translate_responses_attachment(attachment: FileAttachment) -> dict[str, Any]:
    """Map a FileAttachment to a Responses image/file content part.

    Image attachments always include ``detail`` (default ``"auto"``) per the
    Responses API contract. May upload the attachment and return a cached
    file_id reference when the Responses API requires file upload for the
    attachment source/type.
    """


async def _ensure_uploaded_file_id(attachment: FileAttachment) -> str:
    """Return an existing or newly uploaded OpenAI file_id for attachment."""
```

If the OpenAI SDK upload method is async, translation helpers that can upload must also be async. That means `_build_payload()` can stay synchronous only for no-upload unit helpers, while the actual `chat()` request path should build kwargs through an async instance method before calling `client.responses.create()`.

### Normalization Rules

| Canonical input | Provider output |
|-----------------|-----------------|
| `{"role": "user", "content": "hello"}` | `{"role": "user", "content": "hello"}` |
| `{"role": "user", "content": "describe", "attachments": [img]}` | `{"role": "user", "content": [{"type": "input_text", "text": "describe"}, image_or_file_part]}` |
| `{"role": "user", "content": [ContentPart(type="text", ...), ContentPart(type="file", ...)]}` | `{"role": "user", "content": [text_part, image_or_file_part]}` |
| `{"role": "user", "content": [ContentPart(type="text", ...)], "attachments": [file]}` | `{"role": "user", "content": [text_part, file_part]}` — message-level attachments append after explicit content parts |
| `FileAttachment(data=..., mime_type="image/png")` | `input_image` with data URL and `detail="auto"`, or uploaded `input_file` reference if required by provider behavior |
| `FileAttachment(url="https://...", mime_type="image/jpeg")` | `input_image` with URL and `detail="auto"` |
| `FileAttachment(data=..., mime_type="application/pdf", filename="doc.pdf")` | `input_file` with uploaded `file_id` reference — file is uploaded once through the provider, returned `file_id` is cached per session |
| `FileAttachment(file_id="file_abc", mime_type="application/pdf")` | `input_file` with `file_id="file_abc"` |

For `content: str` plus attachments, the translated text part is omitted only when the string is empty. Attachments still translate in order.

### Upload Cache Contract

| Operation | Behavior |
|-----------|----------|
| Attachment already has `file_id` | Return the `file_id` directly and do not cache or upload |
| Attachment cache key exists | Return cached `file_id` and do not upload |
| Attachment cache key missing | Upload through OpenAI, cache returned `file_id`, and return it |
| Upload fails | Raise the existing provider error wrapper or a clear `ValueError` before request creation when validation fails |

### Upload Policy

The following policy defines when a file attachment triggers an upload through the provider upload endpoint. The upload trigger is deterministic: images always use inline `input_image` shapes, while non-image file attachments with `data` or `url` sources always upload through the provider, with the returned `file_id` cached per session for reuse.

| Attachment Source | MIME Type | Action |
|-------------------|-----------|--------|
| `file_id` | Any | Skip upload — use `input_file` with `file_id` directly |
| `data` (base64) | `image/*` | No upload — use `input_image` with data URL and `detail="auto"` |
| `url` | `image/*` | No upload — use `input_image` with URL and `detail="auto"` |
| `data` (base64) | Non-image (e.g., `application/pdf`) | **Upload required** — upload once through provider, cache `file_id`, then use `input_file` with the cached `file_id` |
| `url` | Non-image (e.g., `application/pdf`) | **Upload required** — upload once through provider, cache `file_id`, then use `input_file` with the cached `file_id` |

This policy results in the following translation outcomes:

- **`_translate_responses_attachment()`** for images: produces `input_image` content parts (inline, no upload).
- **`_translate_responses_attachment()`** for non-image `data`/`url` attachments: calls `_ensure_uploaded_file_id()` and produces `input_file` content parts with the returned `file_id`.
- **`_ensure_uploaded_file_id()`** is invoked only for non-image attachments with `data` or `url` sources. It checks the cache key first, uploads on miss, and returns the `file_id`.

This makes FR-009 and FR-010 acceptance deterministic: a unit test that creates a non-image data-backed `FileAttachment` (e.g., `application/pdf` inline bytes) and passes it through translation twice will verify one upload call and reuse of the cached `file_id`.

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Empty `content: list[ContentPart]` | `ValueError` | At least one content part is required for a meaningful user message |
| Unsupported content item type | `ValueError` | Expected `ContentPart` or serializable dict |
| File part without a file | `ValueError` | Defensive guard; model validation normally catches this |
| Attachment has no usable source | Existing Pydantic validation error or `ValueError` | `FileAttachment` should require one source |
| Provider cannot accept MIME/source combination | `ValueError` | Fail clearly before invalid request when detectable |
| Upload endpoint fails | Existing provider error translation | Preserve `ProviderApiError` / `ProviderAuthError` handling style |
| OpenAI rejects multimodal payload | Existing provider error translation | Keep current `_handle_provider_error()` behavior |

---

## Implementation Phases

### Phase 1 — Tests First

- [ ] Add unit tests for explicit `list[ContentPart]` translation to Responses text and image/file parts.
- [ ] Add unit tests for `content: str` plus `attachments` translation.
- [ ] Add unit tests for inline image data, image URLs, non-image file inputs, and `file_id` references.
- [ ] Add unit tests for multiple attachments and ordering.
- [ ] Add unit tests for cache hit/miss behavior using a mocked OpenAI upload endpoint.
- [ ] Add unit tests proving string-only messages, tool-result translation, and `previous_response_id` behavior are unchanged.
- [ ] Add or update a guarded integration test for sending an image attachment through the Responses provider.

### Phase 2 — Translation Helpers

- [ ] Import or reference `ContentPart` and `FileAttachment` in `tinycua_sdk/providers/open_ai_responses.py`.
- [ ] Implement private Responses content-part translation helpers.
- [ ] Implement private attachment translation for image URLs, data URLs, inline file data, and `file_id` references.
- [ ] Implement stable cache-key generation for upload-required attachments.

### Phase 3 — Upload and Cache Integration

- [ ] Add provider-client scoped `_file_id_cache` initialization.
- [ ] Implement upload helper that calls the OpenAI upload/file endpoint and stores returned `file_id` values.
- [ ] Ensure repeated upload-required attachments reuse the cached `file_id`.
- [ ] Ensure pre-existing `FileAttachment.file_id` values bypass upload.

### Phase 4 — Wire Into Responses Client

- [ ] Use the new instance-aware translation path when building request kwargs for non-streaming and streaming `responses.create()` calls.
- [ ] Preserve existing supported-field mapping in `_build_payload()` / request kwargs.
- [ ] Preserve existing tool-result conversion and `previous_response_id` logic.
- [ ] Preserve existing event normalization and raw event behavior.

### Phase 5 — Verification

- [ ] Run Responses unit tests.
- [ ] Run relevant integration tests with network tests skipped by default.
- [ ] Run the broader tinycua-sdk test suite if practical.

---

## Technical Decisions

1. **Decision**: Keep attachment translation inside the OpenAI Responses provider module.
   **Reason**: The mapping is provider-specific and depends on OpenAI Responses input shapes and upload behavior.
   **Alternatives Considered**: A shared multimodal adapter across providers — rejected because Chat Completions and Responses already differ, and future providers may require different contracts.

2. **Decision**: Make the request path instance-aware for attachment translation.
   **Reason**: Upload/cache behavior needs provider-client state and the OpenAI SDK client; a pure module-level helper cannot safely own per-session cache state.
   **Alternatives Considered**: Global cache or passing cache dictionaries through pure helpers — rejected because it makes lifetime and concurrency semantics less clear.

3. **Decision**: Preserve plain string user messages as plain strings when there are no attachments.
   **Reason**: This minimizes payload changes and protects existing tests and callers from unnecessary request shape changes.
   **Alternatives Considered**: Convert every user message to `input_text` parts — rejected because it changes the payload shape for no functional gain.

4. **Decision**: For `content: str` plus attachments, emit the text part first, then attachment parts in caller order.
   **Reason**: The basic message shape represents text plus a separate attachment list. Placing text first preserves natural prompt-before-evidence ordering.
   **Alternatives Considered**: Place attachments first or sort by filename — rejected because message-level attachments do not carry ordering relative to substrings.

5. **Decision**: Use a provider-client scoped file ID cache.
   **Reason**: Issue #46 requires same-session file reuse without making cache persistence a prerequisite. Client-scoped state matches the existing provider-client lifetime.
   **Alternatives Considered**: Persistent per-agent cache — deferred to Phase 5 because persistence needs configuration, invalidation, and storage decisions.

6. **Decision**: Prefer direct provider-native URL/data input when supported, and upload only when needed.
   **Reason**: Avoids unnecessary uploads for inputs the Responses API can already consume directly, while still supporting file IDs for provider-required uploads and reuse.
   **Alternatives Considered**: Upload every attachment unconditionally — rejected because it adds latency, storage side effects, and unnecessary network calls.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing string-only Responses payloads change unexpectedly | Low | High | Preserve exact string-content path when no attachments are present; add regression tests |
| Responses content-part names differ across OpenAI SDK/API versions | Medium | Medium | Keep provider shapes centralized in small helpers and cover with focused unit tests |
| Upload helper introduces async request-building complexity | Medium | Medium | Keep pure no-upload helpers where possible, but route actual request creation through an async instance method |
| File cache key accidentally collides or misses reuse | Low | Medium | Include source payload, MIME type, and filename/source metadata in a stable hash; unit test hit/miss cases |
| Upload cache stores provider IDs longer than intended | Low | Low | Scope cache to `OpenAIResponsesClient` instance only and clear it when the client object is discarded |
| Integration tests depend on external API credentials | High | Low | Guard network tests behind environment configuration and keep unit tests comprehensive |
| Tool-result continuation regresses while modifying translation | Medium | High | Add regression tests for `function_call_output` and `previous_response_id` behavior |

---

## Open Questions

*(No open questions — provider format details should be validated during implementation against the installed OpenAI SDK and covered by tests.)*

---

## References

- Spec: `./spec.md`
- Phase 1 Spec: `../sdk-file-attachment-phase1/spec.md`
- Phase 1 Design: `../sdk-file-attachment-phase1/design.md`
- Phase 2 Chat Completions Spec: `../sdk-file-attachment-phase2-chat-completions/spec.md`
- Phase 2 Chat Completions Design: `../sdk-file-attachment-phase2-chat-completions/design.md`
- Issue #46: SDK-wide File Attachment Support (https://github.com/VJyzCELERY/TINYCUA/issues/46)
- Parent issue #45: SDK-wide File Attachment Support discussion (https://github.com/VJyzCELERY/TINYCUA/issues/45)
