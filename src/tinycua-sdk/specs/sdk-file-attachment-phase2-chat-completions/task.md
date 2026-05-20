# Tasks: OpenAI Chat Completions File Attachment Translation

Implementation tasks for Phase 2 Chat Completions file attachment translation. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write unit tests for `_translate_chat_attachment()` — data-backed, URL-backed, file_id-only (ValueError), non-image MIME (ValueError) <!-- id: 0 -->
- [ ] Write unit tests for `_translate_chat_content_part()` — text part, file part delegation <!-- id: 1 -->
- [ ] Write unit tests for `_translate_chat_user_message()` — plain string (backward compat), string + attachments, list[ContentPart], empty attachments, multiple attachments with ordering <!-- id: 2 -->
- [ ] Write unit tests for `_translate_chat_messages()` end-to-end — multipart user message with system/assistant/tool_result messages, string-only messages for other roles unchanged <!-- id: 3 -->
- [ ] Run unit tests — expect RED (failures) since no implementation yet <!-- id: 4 -->

## Implementation Phase

- [ ] Import `ContentPart` and `FileAttachment` in `tinycua_sdk/providers/open_ai.py` <!-- id: 5 -->
- [ ] Implement `_translate_chat_attachment()` — data URL construction, URL pass-through, file_id ValueError, non-image MIME ValueError <!-- id: 6 -->
- [ ] Implement `_translate_chat_content_part()` — text → text part, file → delegate to `_translate_chat_attachment()` <!-- id: 7 -->
- [ ] Implement `_translate_chat_user_message()` — string-only passthrough, string + attachments → text + image parts, list[ContentPart] → translated parts, strip attachments key <!-- id: 8 -->
- [ ] Wire `_translate_chat_user_message()` into `OpenAIChatCompletionsClient._translate_chat_messages()` for user-role messages in the `else` branch <!-- id: 9 -->

## Testing Phase

- [ ] Run unit tests — expect GREEN (all pass) <!-- id: 10 -->
- [ ] Add guarded integration test for image attachment in `tests/integration/test_openai_chat_completions_provider.py` <!-- id: 11 -->
- [ ] Run full unit test suite: `cd src/tinycua-sdk && uv run pytest tests/unit/` <!-- id: 12 -->
- [ ] Run integration test suite (auto-skipped without server): `cd src/tinycua-sdk && uv run pytest tests/integration/` <!-- id: 13 -->

## Verification Phase

- [ ] Verify string-only Chat Completions payloads remain unchanged (existing tests cover this) <!-- id: 14 -->
- [ ] Verify tool-result injection logic still works (existing tests cover this) <!-- id: 15 -->
- [ ] Verify backward compatibility — no `attachments` key in translated output <!-- id: 16 -->

## Review and Merge

- [ ] Run `/review-report` on the branch <!-- id: 17 -->
- [ ] Address review feedback <!-- id: 18 -->
- [ ] Create pull request <!-- id: 19 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-20*