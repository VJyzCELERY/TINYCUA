# Tasks: Phase 6 — Tool Result File Support

Implementation tasks for Phase 6 — Tool Result File Support. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests defined in `implementation-plan.md` for non-streaming and streaming tool-generated file handoff <!-- id: 1 -->
- [ ] Run integration tests — expect RED because tool results are currently stringified <!-- id: 2 -->
- [ ] Write loop unit tests for structured tool result normalization and legacy fallback <!-- id: 3 -->
- [ ] Write Chat Completions provider tests for tool-result `ContentPart` and `attachments` translation <!-- id: 4 -->
- [ ] Write Responses provider tests for tool-result `ContentPart` and `attachments` translation <!-- id: 5 -->
- [ ] Run focused unit tests — expect RED before implementation <!-- id: 6 -->

## Implementation Phase

- [ ] Add shared tool-result normalization in `tinycua_sdk/agent/loop.py` <!-- id: 7 -->
  - [ ] Preserve explicit `content: list[ContentPart]` results <!-- id: 7a -->
  - [ ] Preserve `content: str` plus `attachments: list[FileAttachment]` results <!-- id: 7b -->
  - [ ] Override tool-provided `role` and `call_id` with loop-owned values <!-- id: 7c -->
  - [ ] Reject empty `list[ContentPart]` with clear `ValueError` matching user-message behavior <!-- id: 7d -->
  - [ ] Fall back to `str(tool_result)` for unsupported legacy values <!-- id: 7e -->
- [ ] Wire normalization into non-streaming tool processing <!-- id: 8 -->
  - [ ] Replace direct `str(tool_result)` construction in `process_tool_calls()`
  - [ ] Confirm tool execution error messages remain string-only
- [ ] Wire normalization into streaming tool processing <!-- id: 9 -->
  - [ ] Replace direct `str(tool_result)` construction in `process_stream_tool_calls()`
  - [ ] Confirm max-tool-call and cancellation behavior is unchanged
- [ ] Implement Chat Completions structured tool-result translation <!-- id: 10 -->
  - [ ] Add helper mirroring `_translate_chat_user_message()` for `tool_result`
  - [ ] Preserve assistant `tool_calls` injection/order for tool-result batches
  - [ ] Reuse `_translate_chat_content_part()` and `_translate_chat_attachment()`
- [ ] Implement Responses structured tool-result translation <!-- id: 11 -->
  - [ ] Add async helper for `function_call_output`
  - [ ] Reuse `_translate_responses_content_part()` and `_translate_responses_attachment()`
  - [ ] Route tool results through the async `_translate_responses_input()` path
- [ ] Update canonical message documentation <!-- id: 12 -->
  - [ ] Confirm `ToolResultMessage` docs match runtime behavior for structured tool returns

## Testing Phase

- [ ] Run integration tests — expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/integration/test_tool_result_attachments.py` <!-- id: 13 -->
- [ ] Run loop unit tests — expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/unit/test_loop.py tests/unit/test_loop_custom.py` <!-- id: 14 -->
- [ ] Run provider unit tests — expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py tests/unit/test_llm_client.py` <!-- id: 15 -->
- [ ] Run upload/cache regression tests to confirm Phase 5 paths still work: `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py tests/unit/test_llm_client.py -k "cache or upload"` <!-- id: 16 -->
- [ ] Run full test suite: `cd src/tinycua-sdk && uv run pytest` <!-- id: 17 -->

## Verification Phase

- [ ] Verify provider-native payload shapes match documented API contract for multimodal tool messages: inspect payloads via `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py::test_chat_completions_translates_tool_result_attachments_to_tool_content_parts tests/unit/test_llm_client.py::test_responses_translates_tool_result_content_parts_to_function_call_output -vxs` <!-- id: 18 -->
- [ ] Verify legacy string/dict/exception tool results remain backward compatible: `cd src/tinycua-sdk && uv run pytest tests/unit/test_loop.py::test_normalize_legacy_falls_back_to_string -v` <!-- id: 19 -->
- [ ] Run cache reuse test: verify repeated tool-returned non-image files reuse existing upload cache: `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py::test_chat_completions_tool_result_cache_reuse -v` <!-- id: 20 -->
- [ ] Optional manual smoke test with a vision model and a tool-generated PNG <!-- id: 21 -->

## Documentation Phase

- [ ] Update tinycua-sdk docs or README to document tool-returned attachment support <!-- id: 22 -->
- [ ] Update issue #46 checklist after implementation passes review <!-- id: 23 -->

## Review and Merge

- [ ] Create pull request for Phase 6 implementation work <!-- id: 24 -->
- [ ] Address review feedback <!-- id: 25 -->
- [ ] Merge into parent feature branch after approval <!-- id: 26 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-26*
