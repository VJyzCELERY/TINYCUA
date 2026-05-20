# Implementation: OpenAI Chat Completions File Attachment Translation

Extend the existing `OpenAIChatCompletionsClient` message translation path so that canonical Phase 1 file attachment shapes (`ContentPart` and `FileAttachment`) are converted into Chat Completions multimodal message content. Callers can then send image attachments through `provider="openai-chat-completions"` with vision-capable models using SDK canonical types only.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1 — core SDK provider feature
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- **None** — this feature has no configuration dependencies. All changes are in existing subproject code with existing test infrastructure.

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| None | — | — | — |

Integration tests that require a live LLM server are already gated behind environment configuration in `tests/integration/conftest.py` and will auto-skip when unreachable.

### Data / Fixtures

- **None** — no database or seed data needed.

### Access / Permissions

- **None** — no special access required.

### Developer Tooling

- **Runtime**: Python 3.11+
- **Package manager**: uv (`cd src/tinycua-sdk && uv run pytest`)
- **Additional CLI tools**: None

---

## Success Criteria — Integration Tests (TDD First)

```python
# Test file: tests/integration/test_openai_chat_completions_provider.py

def test_openai_chat_completions_attachment_translates_image():
    """A user message with an image FileAttachment is translated into a Chat
    Completions payload containing an image_url content part."""
    # Arrange
    client = OpenAIChatCompletionsClient(LanguageModel(provider="openai-chat-completions", model_name="gpt-4o-mini"))
    image_data = base64.b64encode(b"\x89PNG\r\n\x1a\n...").decode("ascii")
    attachment = FileAttachment(data=image_data, mime_type="image/png")
    message = UserMessage(role="user", content="Describe this image", attachments=[attachment])

    # Act
    messages = client._translate_chat_messages([message])

    # Assert — translated payload is a list with one user message dict
    assert len(messages) == 1
    user_msg = messages[0]
    assert user_msg["role"] == "user"
    content = user_msg["content"]
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "Describe this image"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_openai_chat_completions_url_attachment_remains_url():
    """A URL-backed FileAttachment passes the URL through without download."""
    # Arrange
    client = OpenAIChatCompletionsClient(LanguageModel(model_name="gpt-4o-mini"))
    attachment = FileAttachment.from_url("https://example.com/photo.jpg", mime_type="image/jpeg")
    message = UserMessage(role="user", content="What is this?", attachments=[attachment])

    # Act
    messages = client._translate_chat_messages([message])

    # Assert
    assert messages[0]["content"][1]["image_url"]["url"] == "https://example.com/photo.jpg"
```

### Key Test Scenarios

- **Scenario 1**: Explicit multipart `content: list[ContentPart]` with text + image translates to provider-native text + image_url parts — proves `ContentPart` translation works
- **Scenario 2**: Basic `content: str` + `attachments` translates to text + image_url parts — proves message-level attachment appending works
- **Scenario 3**: Base64-backed attachment becomes a data URL with correct MIME type — proves inline image encoding
- **Scenario 4**: URL-backed attachment passes through as-is — proves no unnecessary download
- **Scenario 5**: String-only user messages remain plain strings — proves backward compatibility
- **Scenario 6**: `file_id`-only attachment and non-image MIME types raise `ValueError` — proves clear rejection of unsupported inputs
- **Scenario 7**: Multiple attachments and multipart content preserve caller-specified order — proves ordering invariants
- **Scenario 8**: Tool-result and system/assistant messages remain unchanged — proves no regression

## Verification Plan

### Automated Tests

- [ ] Unit tests for Chat Completions attachment translation (in `tests/unit/test_openai_chat_client.py`) — must all pass
- [ ] Integration test for image attachment with Chat Completions provider (in `tests/integration/test_openai_chat_completions_provider.py`) — guarded by environment config
- [ ] Existing unit test suite — confirm no regressions: `cd src/tinycua-sdk && uv run pytest tests/unit/`
- [ ] Existing integration test suite — confirm no regressions: `cd src/tinycua-sdk && uv run pytest tests/integration/`

### Manual Verification

- [ ] Run Chat Completions provider against a real OpenAI vision-capable model with `FileAttachment.from_bytes()` and `FileAttachment.from_url()`
- [ ] Confirm existing text-only and tool-call Chat Completions workflows still pass

### Performance Considerations

- [ ] Large base64 payloads increase request size — acceptable for Phase 2; file upload/cache remains Phase 5 work
- [ ] No streaming changes — translation is synchronous and fast

## Proposed Changes

### Translation Helpers

#### [NEW] Private helper functions in `tinycua_sdk/providers/open_ai.py`

- **`_translate_chat_attachment(attachment: FileAttachment) -> dict[str, Any]`**: Maps a single image `FileAttachment` to a Chat Completions `image_url` content part dict.
  - If `attachment.data` is set: returns `{"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{data}"}}`
  - If `attachment.url` is set: returns `{"type": "image_url", "image_url": {"url": attachment.url}}`
  - If only `attachment.file_id` is set: raises `ValueError` — Chat Completions Phase 2 has no upload/cache mapping
  - Validates MIME type starts with `image/`; raises `ValueError` for non-image types
- **`_translate_chat_content_part(part: ContentPart) -> dict[str, Any]`**: Maps a canonical `ContentPart` to a Chat Completions content part dict.
  - Text part → `{"type": "text", "text": part.text}`
  - File part → delegates to `_translate_chat_attachment(part.file)`
- **`_translate_chat_user_message(msg: dict[str, Any]) -> dict[str, Any]`**: Returns a Chat Completions user message dict.
  - If `msg["content"]` is a string and `attachments` is absent or empty: returns `msg` unchanged (backward compatible)
  - If `msg["content"]` is a string and `attachments` is non-empty: returns `{"role": "user", "content": [text_part, ...attachment_parts]}`
  - If `msg["content"]` is a list of `ContentPart`: returns `{"role": "user", "content": [...translated_parts]}`
  - Strips `attachments` key from the translated output (not a valid Chat Completions field)

### Chat Completions Client

#### [MODIFY] `tinycua_sdk/providers/open_ai.py` — `OpenAIChatCompletionsClient._translate_chat_messages()`

- **Wire user-message translation**: After the existing `else: result.append(msg)` branch for non-special messages, check if `msg` has `role == "user"` and call `_translate_chat_user_message()` to handle `content: list[ContentPart]` and `attachments`. Plain string user messages without attachments pass through unchanged.
- **Import `ContentPart` and `FileAttachment`**: Add imports from `tinycua_sdk.models` and `tinycua_sdk.agent.events`.
- **Preserve existing assistant `tool_calls` pass-through and tool-result injection**: No changes to those branches.

### Tests

#### [MODIFY] `tests/unit/test_openai_chat_client.py`

- Add `TestChatCompletionsAttachmentTranslation` test class covering:
  - Test `_translate_chat_attachment()` with `data`-backed attachment (image/png)
  - Test `_translate_chat_attachment()` with `url`-backed attachment (image/jpeg)
  - Test `_translate_chat_attachment()` with `file_id`-only raises `ValueError`
  - Test `_translate_chat_attachment()` with non-image MIME type raises `ValueError`
  - Test `_translate_chat_content_part()` with text part
  - Test `_translate_chat_content_part()` with file part (delegates to attachment)
  - Test `_translate_chat_user_message()` with plain string (no attachments) — backward compatible
  - Test `_translate_chat_user_message()` with string + attachments — text part then image parts
  - Test `_translate_chat_user_message()` with `list[ContentPart]` — preserves order
  - Test `_translate_chat_user_message()` with empty attachments list — same as no attachments
  - Test `_translate_chat_user_message()` with multiple attachments — order preserved
  - Test `_translate_chat_messages()` integration: multipart user message with system and assistant messages
  - Test string-only messages for other roles remain unchanged

#### [MODIFY] `tests/integration/test_openai_chat_completions_provider.py`

- Add a guarded integration test that creates a `UserMessage` with an image `FileAttachment` and sends it through the Chat Completions provider, asserting a non-empty assistant response. This test is marked `@pytest.mark.integration` and auto-skip when no LLM server is reachable.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua_sdk/providers/open_ai.py` | Modify | Add 3 private translation helpers; modify `_translate_chat_messages()` to call them for user messages |
| `tests/unit/test_openai_chat_client.py` | Modify | Add `TestChatCompletionsAttachmentTranslation` class with unit tests |
| `tests/integration/test_openai_chat_completions_provider.py` | Modify | Add guarded image attachment integration test |

## Data Model Changes

No new public entities. Phase 2 consumes existing Phase 1 models:

```python
# Existing — consumed but not modified
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

## API Changes

No new public API endpoints. The change is internal to `OpenAIChatCompletionsClient._translate_chat_messages()` — callers pass the same canonical `UserMessage` types, and the provider translates them correctly.

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pydantic | existing | `ContentPart` and `FileAttachment` validation (already in use) |

### Internal Dependencies

- [x] Depends on Phase 1 `FileAttachment` and `ContentPart` models — already merged
- [ ] Blocks Phase 3 (Responses API attachment translation), Phase 4 (`Agent.run()` convenience parameters), Phase 6 (tool-result file attachments)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Existing string-only Chat Completions payloads change unexpectedly | High | Preserve exact string-content path when no attachments; add regression tests that assert identical output |
| Chat Completions accepts only image inputs while canonical model supports broader files | Medium | Reject non-image MIME types with clear `ValueError`; document broader support as provider-permitting future work |
| Data URLs become large payloads | Medium | Accept inline data behavior for Phase 2; file upload/cache and streaming remain Phase 5 work |
| Tool-result injection logic regresses | High | Keep tool-result branch structure intact; retain all existing unit tests for that path |
| Integration tests depend on external API credentials | Low | Guard network tests behind `@pytest.mark.integration` and existing conftest probes |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-20*