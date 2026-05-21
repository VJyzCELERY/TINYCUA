# Tasks: OpenAI Responses File Attachment Translation

Implementation tasks for Phase 3 — translating canonical file attachments into OpenAI Responses multimodal input.

## TDD Phase (Tests First)

- [x] Add unit tests for `_translate_responses_content_part()` (async helper) — text ContentPart → `input_text`, file ContentPart → image/file input (awaits `_translate_responses_attachment()`) <!-- id: 0 -->
- [x] Add unit tests for `_translate_responses_attachment()` — data-backed image → `input_image` with data URL and `detail="auto"`, URL-backed image → `input_image` with URL and `detail="auto"`, `file_id`-backed → `input_file` with `file_id`, non-image data → `input_file` with `file_id` (upload-required per upload policy) <!-- id: 1 -->
- [x] Add unit tests for `_translate_responses_user_message()` (async helper) — string-only passthrough, string + attachments → text + file parts, `list[ContentPart]` → content list, `list[ContentPart]` + attachments → content parts then attachment parts, empty list raises `ValueError`, empty attachments same as omitted — must await helper in test <!-- id: 2 -->
- [x] Add unit tests for upload cache hit/miss — a non-image data-backed FileAttachment (e.g., `application/pdf` inline bytes) triggers `_ensure_uploaded_file_id()` through `_translate_responses_attachment()`, same attachment reuses cached `file_id`, new attachment uploads once, pre-existing `file_id` bypasses upload, cache key includes data/MIME/filename <!-- id: 3 -->
- [x] Add regression unit tests — string-only user messages unchanged, tool-result translation unchanged, `previous_response_id` behavior unchanged <!-- id: 4 -->
- [x] Add guarded integration test file `tests/integration/test_openai_responses_provider.py` — image attachment via `attachments`, image attachment via `ContentPart` <!-- id: 5 -->
- [x] Run unit tests — expect RED (attachment helpers not yet implemented) <!-- id: 6 -->

## Implementation Phase

- [x] Import `ContentPart` and `FileAttachment` in `open_ai_responses.py` <!-- id: 7 -->
- [x] Implement `_translate_responses_content_part(part)` (async) — text → `{"type": "input_text", ...}`, file → awaits `_translate_responses_attachment` <!-- id: 8 -->
- [x] Implement `_translate_responses_attachment(attachment)` — data-backed image → `input_image` with data URL and `detail="auto"`, URL-backed image → `input_image` with URL and `detail="auto"`, `file_id` → `input_file` reference, non-image data → call `_ensure_uploaded_file_id()`, then emit `input_file` with `file_id`, non-image url → reject with `ValueError` (deferred to Phase 5) <!-- id: 9 -->
- [x] Implement `_translate_responses_user_message(msg)` (async) — handles string-only, string + attachments, `list[ContentPart]`, `list[ContentPart]` + attachments, dict coercion for ContentPart items — awaits content-part and attachment translation <!-- id: 10 -->
- [x] Implement stable cache key generation — hash from source data + MIME type + filename (non-image data attachments only) <!-- id: 11 -->
- [x] Add `_file_id_cache: dict[str, str]` to `OpenAIResponsesClient.__init__` <!-- id: 12 -->
- [x] Implement `_ensure_uploaded_file_id(attachment)` async method — check cache, upload if miss, store and return `file_id` <!-- id: 13 -->
- [x] Modify `_chat_sync` — use instance-aware async translation (await `_translate_responses_user_message` and related helpers) with upload support <!-- id: 14 -->
- [x] Modify `_chat_stream` — use instance-aware async translation (await `_translate_responses_user_message` and related helpers) with upload support <!-- id: 15 -->
- [x] Ensure `_translate_messages()` still handles tool-result messages correctly and is used as fallback for non-user messages <!-- id: 16 -->

## Testing Phase

- [x] Run unit tests — expect GREEN (all pass) <!-- id: 17 -->
- [x] Run `cd src/tinycua-sdk && uv run pytest tests/unit/test_llm_client.py` — existing + new tests pass <!-- id: 18 -->
- [x] Run `cd src/tinycua-sdk && uv run pytest tests/unit/ -k "responses"` — focused Responses tests pass <!-- id: 19 -->
- [x] Run full test suite: `cd src/tinycua-sdk && uv run pytest` — no regressions <!-- id: 20 -->

## Verification Phase

- [x] Run `cd src/tinycua-sdk && uv run ruff check .` — lint passes <!-- id: 21 -->
- [x] Run `cd src/tinycua-sdk && uv run mypy tinycua_sdk/` — type checking passes <!-- id: 22 -->
- [x] Verify upload cache is scoped to `OpenAIResponsesClient` instance (no global state) <!-- id: 23 -->
- [x] Verify string-only Responses payloads are identical to pre-Phase-3 output <!-- id: 24 -->

## Documentation Phase

- [ ] Update SDK provider docs/examples to show `content: str` + `attachments` usage for Responses provider <!-- id: 25 -->
- [ ] Add SDK docs section for `list[ContentPart]` usage with Responses provider, including supported image/file sources <!-- id: 29 -->
- [ ] Document Responses-specific image `detail` parameter (defaults to `"auto"`) and supported MIME types <!-- id: 30 -->
- [ ] Document integration test configuration (requires `OPENAI_API_KEY` env var) in contributor guide <!-- id: 31 -->

## Review and Merge

- [ ] Create pull request (update existing PR #49) <!-- id: 26 -->
- [ ] Address review feedback <!-- id: 27 -->
- [ ] Merge to `feat/SDK-file-attachment-support` branch <!-- id: 28 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-21*
