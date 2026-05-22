# Implementation: OpenAI Responses File Attachment Translation

Extend the `OpenAIResponsesClient` message translation path so canonical Phase 1 file attachment shapes are converted into OpenAI Responses multimodal input. Adds Responses-specific content/attachment translation helpers, a per-session file upload cache, and wiring into the existing `_chat_sync`/`_chat_stream` request paths.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [x] **Provider-specific env vars** — each provider resolves `base_url` and `api_key` from its own env vars (`OPENAI_RESPONSES_*`, `OPENAI_CHAT_COMPLETIONS_*`) with `LLM_*` fallback
- [x] **`.env.example`** — documents `OPENAI_RESPONSES_BASE_URL`, `OPENAI_RESPONSES_API_KEY`, `OPENAI_RESPONSES_MODEL`, `OPENAI_CHAT_COMPLETIONS_BASE_URL`, `OPENAI_CHAT_COMPLETIONS_API_KEY`, `OPENAI_CHAT_COMPLETIONS_MODEL`
- [x] **`.env.test.example`** — sets provider-specific vars to localhost defaults for local-LLM testing

### Running Services

- **None** — no external services needed for unit tests

### Data / Fixtures

- **None** — no data or fixtures needed

### Access / Permissions

- [ ] **OpenAI API key** — required for integration tests only; guarded by `OPENAI_API_KEY` environment variable

### Developer Tooling

- [ ] **Runtime**: Python 3.12+
- [ ] **Package manager**: uv
- [ ] **Additional CLI tools**: None

---

## Success Criteria — Integration Tests (TDD First)

```python
# Test file: tests/integration/test_openai_responses_provider.py
"""Integration tests for OpenAI Responses file attachment translation."""

import base64
import os
import pytest
from tinycua_sdk.agent.events import UserMessage
from tinycua_sdk.models.attachment import FileAttachment, ContentPart
from tinycua_sdk.providers.open_ai_responses import OpenAIResponsesClient
from tinycua_sdk.agent.llm_model import LanguageModel

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set; skipping Responses integration tests",
)


@pytest.mark.asyncio
async def test_responses_image_attachment_returns_non_empty_response():
    """Sending an image attachment through the Responses provider yields a
    non-empty assistant response from a vision-capable model."""
    model = LanguageModel(
        model_name=os.getenv("OPENAI_RESPONSES_MODEL", "gpt-4o-mini"),
        provider="openai-responses",
    )
    client = OpenAIResponsesClient(model)
    try:
        attachment = FileAttachment.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            ),
            mime_type="image/png",
            filename="test_image.png",
        )
        messages: list[UserMessage] = [
            {"role": "user", "content": "Describe this image briefly.", "attachments": [attachment]},
        ]
        result = await client.chat(messages=messages)
        assert result["content"] is not None
        assert len(result["content"]) > 0
    finally:
        await client.close()
```

```python
# Test file: tests/integration/test_openai_responses_provider.py
"""Additional integration test for ContentPart-based image input."""

@pytest.mark.asyncio
async def test_responses_content_part_image_returns_non_empty_response():
    """Sending a ContentPart image through the Responses provider yields a
    non-empty assistant response."""
    model = LanguageModel(
        model_name=os.getenv("OPENAI_RESPONSES_MODEL", "gpt-4o-mini"),
        provider="openai-responses",
    )
    client = OpenAIResponsesClient(model)
    try:
        attachment = FileAttachment.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            ),
            mime_type="image/png",
            filename="test_image.png",
        )
        parts = [
            ContentPart(type="text", text="What do you see?"),
            ContentPart(type="file", file=attachment),
        ]
        messages: list[UserMessage] = [
            {"role": "user", "content": parts},
        ]
        result = await client.chat(messages=messages)
        assert result["content"] is not None
        assert len(result["content"]) > 0
    finally:
        await client.close()
```

### Key Test Scenarios

- **Scenario 1**: Basic attachment form (`content: str` + `attachments`) sends image through Responses provider and receives non-empty text response — proves end-to-end attachment path works
- **Scenario 2**: Explicit multipart form (`content: list[ContentPart]`) sends image through Responses provider and receives non-empty text response — proves ContentPart translation path works
- **Edge case**: Unsupported MIME type or missing source field fails with clear `ValueError` before any API call

## Verification Plan

### Automated Tests

- [x] Integration tests (defined above) — guarded by `OPENAI_RESPONSES_MODEL` / `LLM_MODEL`; configured via `OPENAI_RESPONSES_*` env vars
- [ ] Unit tests for `_translate_responses_user_message`, `_translate_responses_content_part`, `_translate_responses_attachment` — test all canonical-to-native mappings
- [ ] Unit tests for upload cache hit/miss behavior with mocked OpenAI upload endpoint
- [ ] Unit tests proving string-only messages, tool-result translation, and `previous_response_id` behavior are unchanged
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua-sdk && uv run pytest`

### Manual Verification

- [ ] Run `cd src/tinycua-sdk && uv run pytest tests/unit/test_llm_client.py` — all existing Responses tests pass
- [ ] Run `cd src/tinycua-sdk && uv run pytest tests/unit/ -k "responses"` — new attachment tests pass
- [x] Run integration tests with local LLM or API key:  
  `cd src/tinycua-sdk && OPENAI_RESPONSES_BASE_URL=http://localhost:1234/v1 OPENAI_RESPONSES_API_KEY=dummy OPENAI_RESPONSES_MODEL=qwen/qwen3.5-9b uv run pytest tests/integration/test_openai_responses_provider.py -v`

### Performance Considerations

- [ ] Upload cache must not grow unbounded within a session — scoped to client instance lifetime only

## Proposed Changes

### Responses Provider Translation

#### MODIFY `tinycua_sdk/providers/open_ai_responses.py`

- **Add Responses content/attachment translation helpers**: `_translate_responses_user_message()`, `_translate_responses_content_part()`, `_translate_responses_attachment()` — mirror the Chat Completions pattern but emit Responses-native shapes (`input_text`, `input_image` with `detail="auto"`, `input_file`)
- **Add `_file_id_cache` to `OpenAIResponsesClient.__init__`**: `dict[str, str]` mapping stable content hashes to OpenAI file IDs
- **Add `_ensure_uploaded_file_id()` async method**: Uploads a file if needed, caches and returns the `file_id`
- **Modify `_chat_sync` and `_chat_stream`**: Use the new instance-aware translation that supports async upload
- **Import `ContentPart` and `FileAttachment`**: From `tinycua_sdk.models.attachment`
- **Rationale**: The existing module-level `_translate_messages()` only handles tool-result translation; Phase 3 needs instance-aware translation for upload/cache state

### Test Files

#### NEW `tests/integration/test_openai_responses_provider.py`

- **Guarded integration tests**: Image attachment via both canonical forms, skipped without `OPENAI_API_KEY`
- **Dependencies**: `OpenAIResponsesClient`, `FileAttachment`, `ContentPart`, `LanguageModel`

#### MODIFY `tests/unit/test_llm_client.py`

- **Add unit tests for Responses attachment translation**: Test all `_translate_responses_*` helpers, cache behavior, ordering, backward compatibility
- **Add regression tests**: String-only messages, tool-result, `previous_response_id` still work unchanged
- **Rationale**: Existing test file already covers `OpenAIResponsesClient`; new tests belong alongside them

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `OpenAIResponsesClient` | Modify | Add `_file_id_cache`, instance-aware message translation, upload helper |
| `_translate_messages()` | Modify | Extend to handle `UserMessage` with `ContentPart` or `attachments` |
| `normalize_base_url()` utility | Refactor | Pure URL normalizer — strip trailing slash only; env resolution moved to per-provider `_get_client()` |
| `OpenAIResponsesClient._get_client()` | Modify | Resolve `base_url`/`api_key` from `OPENAI_RESPONSES_*` env vars with `LLM_*` fallback |
| `OpenAIChatCompletionsClient._get_client()` | Modify | Match pattern — resolve from `OPENAI_CHAT_COMPLETIONS_*` env vars |
| `_translate_responses_user_message()` | New (async) | Normalize user messages with attachments/ContentPart to Responses content list — awaits attachment translation |
| `_translate_responses_content_part()` | New (async) | Map `ContentPart` to Responses-native content part — awaits attachment translation for file parts |
| `_translate_responses_attachment()` | New (async) | Map `FileAttachment` to Responses image/file input; image parts include `detail="auto"` per API contract, may upload |
| `_ensure_uploaded_file_id()` | New (async) | Upload file if not cached, return `file_id` |
| `tests/unit/test_llm_client.py` | Modify | Add Phase 3 attachment translation unit tests |
| `tests/integration/test_openai_responses_provider.py` | New | Guarded integration tests for image attachment |

## Data Model Changes

```python
# Private instance state added to OpenAIResponsesClient
OpenAIResponsesClient:
    _file_id_cache: dict[str, str]  # stable hash -> OpenAI file_id
```

No changes to public canonical models (`FileAttachment`, `ContentPart`, `UserMessage`).

## Upload Policy

The upload trigger is deterministic for Phase 3: images always use inline `input_image` shapes (no upload); non-image file attachments with `data` sources always upload through the provider upload endpoint, with the returned `file_id` cached per session and reused via `input_file` references; non-image URL attachments are rejected with a clear `ValueError` (URL download/fetch support is deferred to Phase 5). Pre-existing `file_id` attachments bypass upload entirely. This policy ensures the `_ensure_uploaded_file_id()` helper is exercised by any non-image data-backed attachment, making FR-009 and FR-010 acceptance deterministic and testable.

## API Changes

No new public endpoints. Internal provider translation is extended.

## Dependencies

### External Dependencies

No new external dependencies.

### Internal Dependencies

- [x] Depends on Phase 1 (`FileAttachment`, `ContentPart` models — already implemented)
- [x] Depends on Phase 2 (`_translate_chat_*` pattern — reference only, no code dependency)
- [ ] Blocks Phase 4 (Agent loop integration with run API expansion)
- [ ] Blocks Phase 5 (Persistent cache, streaming upload)
- [ ] Blocks Phase 6 (Tool-result file flow)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Existing string-only Responses payloads change unexpectedly | High | Preserve exact string-content path when no attachments; add regression tests |
| Responses content-part names differ across OpenAI SDK/API versions | Medium | Keep provider shapes centralized in small helpers; cover with focused unit tests |
| Upload helper introduces async request-building complexity | Medium | Route request creation through async instance method; keep pure no-upload helpers testable |
| File cache key accidentally collides or misses reuse | Medium | Include source payload, MIME type, and filename in stable hash; unit test hit/miss |
| Tool-result continuation regresses while modifying translation | High | Add regression tests for `function_call_output` and `previous_response_id` behavior |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-21*
