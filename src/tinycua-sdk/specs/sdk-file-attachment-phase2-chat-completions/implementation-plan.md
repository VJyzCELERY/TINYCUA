# Implementation: OpenAI Chat Completions File Attachment Translation

Extend the existing `OpenAIChatCompletionsClient` message translation path so that canonical Phase 1 file attachment shapes (`ContentPart` and `FileAttachment`) are converted into Chat Completions multimodal message content. Callers can then send image attachments through `provider="openai-chat-completions"` with vision-capable models using SDK canonical types only.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1 — core SDK provider feature
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- **Required**: Local Chat Completions-compatible LLM server. See `src/tinycua-sdk/.env.example` for the expected local development config:
  - `TINYCUA_PROVIDER=openai-chat-completions`
  - `TINYCUA_MODEL=qwen/qwen3.5-9b`
  - `TINYCUA_BASE_URL=http://localhost:1234/v1`
- **Guarded tests** resolve these values via `resolve_integration_llm_config()` in `tests/integration/conftest.py` (which returns both the LLM config and API key), auto-skipping when the server is unreachable.
- **Unit tests** use explicit local config values (`provider="openai-chat-completions"`, `model_name="qwen/qwen3.5-9b"`) and do not require a running server.

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| None | — | — | — |

Integration tests that require a live LLM server are already gated behind environment configuration in `tests/integration/conftest.py` and will auto-skip when unreachable.

### Data / Fixtures

- **Test fixture image**: `tests/fixtures/test_image.png` — a minimal 1x1 PNG image used by the guarded integration test. Create with:
    ```bash
    mkdir -p tests/fixtures
    python -c "import struct; import zlib; open('tests/fixtures/test_image.png','wb').write(b'\\x89PNG\\r\\n\\x1a\\n' + struct.pack('>I',13) + b'IHDR' + struct.pack('>IIBBBBB',1,1,8,2,0,0,0) + struct.pack('>I',zlib.crc32(b'IHDR'+struct.pack('>IIBBBBB',1,1,8,2,0,0,0))&0xffffffff) + struct.pack('>I',len(zlib.compress(b'\\x00\\xff\\x00\\xff'))) + b'IDAT' + zlib.compress(b'\\x00\\xff\\x00\\xff') + struct.pack('>I',zlib.crc32(b'IDAT'+zlib.compress(b'\\x00\\xff\\x00\\xff'))&0xffffffff) + struct.pack('>I',0) + b'IEND' + struct.pack('>I',zlib.crc32(b'IEND')&0xffffffff))"
    ```

### Access / Permissions

- **None** — no special access required.

### Developer Tooling

- **Runtime**: Python 3.11+
- **Package manager**: uv (`cd src/tinycua-sdk && uv run pytest`)
- **Additional CLI tools**: None

---

## Success Criteria — Integration Tests (TDD First)

### Guarded Integration Acceptance Test (must be RED before any source change)

```python
# Test file: tests/integration/test_openai_chat_completions_provider.py

@pytest.mark.integration
def test_openai_chat_completions_attachment_sends_image():
    """A user message with an image FileAttachment is sent through the Chat
    Completions provider and receives a non-empty assistant response.

    This is the FR-011 acceptance test. It exercises the full provider request
    path (chat()) and is guarded by environment configuration so it auto-skips
    when no LLM server is reachable.
    """
    # Arrange — resolve LLM config and API key from environment
    config = resolve_integration_llm_config()
    client = OpenAIChatCompletionsClient(config, api_key=config.api_key)
    image_attachment = FileAttachment.from_path("tests/fixtures/test_image.png")
    message = UserMessage(
        role="user",
        content="Describe this image in one sentence.",
        attachments=[image_attachment],
    )

    # Act — send the actual provider request through chat()
    response = client.chat(messages=[message])

    # Assert — a non-empty assistant response was received
    assert response.content is not None
    assert len(response.content) > 0
    assert isinstance(response.content, str)
```

### Payload-Capture Unit Test (exercises chat() with a mocked client)

```python
# Test file: tests/unit/test_openai_chat_client.py

def test_openai_chat_completions_attachment_produces_multimodal_payload():
    """A user message with image attachments produces a multimodal Chat
    Completions request payload through chat()."""
    # Arrange — mock the underlying OpenAI client to capture the payload
    client = OpenAIChatCompletionsClient(
        LanguageModel(provider="openai-chat-completions", model_name="qwen/qwen3.5-9b"),
        api_key="test-key",
    )
    image_data = base64.b64encode(b"\x89PNG\r\n\x1a\n...").decode("ascii")
    attachment = FileAttachment(data=image_data, mime_type="image/png")
    message = UserMessage(
        role="user",
        content="Describe this image",
        attachments=[attachment],
    )
    captured_payload = None

    def capture_create(**kwargs):
        nonlocal captured_payload
        captured_payload = kwargs
        return mock_chat_completion_response()

    with mock.patch.object(client.client.chat.completions, "create", capture_create):
        client.chat(messages=[message])

    # Assert — the provider payload contains multimodal content
    assert captured_payload is not None
    user_msg_content = captured_payload["messages"][0]["content"]
    assert isinstance(user_msg_content, list)
    assert user_msg_content[0] == {"type": "text", "text": "Describe this image"}
    assert user_msg_content[1]["type"] == "image_url"
    assert user_msg_content[1]["image_url"]["url"].startswith("data:image/png;base64,")
```

The guarded integration test must be written and expected to run RED (failures) **before any source code changes begin**. The payload-capture unit test may serve as TDD guidance but the primary acceptance gate is the integration test exercising `chat()`.

### Key Test Scenarios

- **Scenario 1**: Explicit multipart `content: list[ContentPart]` with text + image translates to provider-native text + image_url parts — proves `ContentPart` translation works
- **Scenario 2**: Basic `content: str` + `attachments` translates to text + image_url parts — proves message-level attachment appending works
- **Scenario 3**: Base64-backed attachment becomes a data URL with correct MIME type — proves inline image encoding
- **Scenario 4**: URL-backed attachment passes through as-is — proves no unnecessary download
- **Scenario 5**: String-only user messages remain plain strings — proves backward compatibility
- **Scenario 6**: `file_id`-only attachment and non-image MIME types raise `ValueError` — proves clear rejection of unsupported inputs
- **Scenario 7**: Multiple attachments and multipart content preserve caller-specified order — proves ordering invariants
- **Scenario 8**: Combined `content: list[ContentPart]` with non-empty `attachments` appends message-level attachments after explicit content parts in caller order — proves mixed-input ordering contract
- **Scenario 9**: Tool-result and system/assistant messages remain unchanged — proves no regression
- **Scenario 10**: Empty `list[ContentPart]` raises `ValueError` — proves early rejection of empty content before translation

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

#### [NEW] Private helper functions in `tinycua_sdk/providers/open_ai_chat_completions.py`

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
  - If `msg["content"]` is an empty list: raises `ValueError` — at least one content part is required
  - If `msg["content"]` is a non-empty list of `ContentPart` and `attachments` is absent or empty: returns `{"role": "user", "content": [...translated_parts]}`
  - If `msg["content"]` is a list of `ContentPart` and `attachments` is non-empty: appends message-level attachment parts after the translated content parts, preserving caller order within each group
  - Strips `attachments` key from the translated output (not a valid Chat Completions field)

### Chat Completions Client

#### [MODIFY] `tinycua_sdk/providers/open_ai_chat_completions.py` — `OpenAIChatCompletionsClient._translate_chat_messages()`

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
  - Test `_translate_chat_user_message()` with `list[ContentPart]` plus non-empty `attachments` — content parts first, then attachment parts, caller order preserved within each group
  - Test `_translate_chat_messages()` integration: multipart user message with system and assistant messages
  - Test string-only messages for other roles remain unchanged

#### [MODIFY] `tests/integration/test_openai_chat_completions_provider.py`

- Add a guarded integration test that creates a `UserMessage` with an image `FileAttachment` and sends it through the Chat Completions provider, asserting a non-empty assistant response. This test is marked `@pytest.mark.integration` and auto-skip when no LLM server is reachable.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua_sdk/providers/open_ai_chat_completions.py` | Modify | Add 3 private translation helpers; modify `_translate_chat_messages()` to call them for user messages |
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