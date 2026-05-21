# Tasks: OpenAI Chat Completions File Attachment Translation

Implementation tasks for Phase 2 Chat Completions file attachment translation. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write unit tests for `_translate_chat_attachment()` — data-backed, URL-backed, file_id-only (ValueError), non-image MIME (ValueError) <!-- id: 0 -->
- [x] Write unit tests for `_translate_chat_content_part()` — text part, file part delegation <!-- id: 1 -->
- [x] Write unit tests for `_translate_chat_user_message()` — plain string (backward compat), string + attachments, list[ContentPart], list[ContentPart] + attachments (content parts first, attachment parts appended), empty attachments, multiple attachments with ordering, empty list[ContentPart] raises ValueError <!-- id: 2 -->
- [x] Write unit tests for `_translate_chat_messages()` end-to-end — multipart user message with system/assistant/tool_result messages, string-only messages for other roles unchanged <!-- id: 3 -->
- [x] Create test fixture `tests/fixtures/test_image.png` — a minimal 4x4 valid multi-color PNG file for the guarded integration test <!-- id: 4 -->
- [x] Add guarded integration test (FR-011) in `tests/integration/test_openai_chat_completions_provider.py` that exercises `chat()` with a vision-capable model, gated by `resolve_integration_llm_config()` and `@pytest.mark.integration` — this MUST be RED before any source code change <!-- id: 5 -->
- [x] Run unit tests and integration test — expect RED (failures) since no implementation yet <!-- id: 6 -->

## Implementation Phase

- [x] Import `ContentPart` and `FileAttachment` in `tinycua_sdk/providers/open_ai_chat_completions.py` <!-- id: 7 -->
- [x] Implement `_translate_chat_attachment()` — data URL construction, URL pass-through, file_id ValueError, non-image MIME ValueError <!-- id: 8 -->
- [x] Implement `_translate_chat_content_part()` — text → text part, file → delegate to `_translate_chat_attachment()` <!-- id: 9 -->
- [x] Implement `_translate_chat_user_message()` — string-only passthrough, string + attachments → text + image parts, list[ContentPart] → translated parts, strip attachments key <!-- id: 10 -->
- [x] Wire `_translate_chat_user_message()` into `OpenAIChatCompletionsClient._translate_chat_messages()` for user-role messages in the `else` branch <!-- id: 11 -->

## Testing Phase

- [x] Run unit tests — expect GREEN (all pass) <!-- id: 12 -->
- [x] Run full unit test suite: `cd src/tinycua-sdk && uv run pytest tests/unit/` <!-- id: 13 -->
- [x] Run integration test suite (auto-skipped without server): `cd src/tinycua-sdk && uv run pytest tests/integration/` <!-- id: 14 -->

## Verification Phase

- [x] Verify string-only Chat Completions payloads remain unchanged (existing tests cover this) <!-- id: 15 -->
- [x] Verify tool-result injection logic still works (existing tests cover this) <!-- id: 16 -->
- [x] Verify backward compatibility — no `attachments` key in translated output <!-- id: 17 -->

## Review and Merge

- [ ] Run `/review-report` on the branch <!-- id: 18 -->
- [ ] Address review feedback <!-- id: 19 -->
- [ ] Create pull request <!-- id: 20 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-20*