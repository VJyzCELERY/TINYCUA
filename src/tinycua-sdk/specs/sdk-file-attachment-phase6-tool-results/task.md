# Tasks: Phase 6 — Tool Result File Support

Implementation tasks for Phase 6 — Tool Result File Support. Check off items as completed.

## Pre-Implementation Verification

- [x] Verify Responses API contract for `function_call_output.output`: confirm the API accepts ``output`` as a list of content parts (``input_text``, ``input_image``, ``input_file``) for tool function-call output messages. **Validation evidence**: Checked against the OpenAI Responses API reference documentation (Create a Response endpoint, source: https://platform.openai.com/docs/api-reference/responses/create) on 2026-05-26 — the ``function_call_output.output`` field description lists ``input_text``, ``input_image``, and ``input_file`` as accepted content part types for the ``output`` array. <!-- id: 0 -->

## TDD Phase (Tests First)

- [x] Write integration tests defined in `implementation-plan.md` for non-streaming and streaming tool-generated file handoff <!-- id: 1 -->
- [x] Run integration tests — expect RED because tool results are currently stringified <!-- id: 2 -->
- [x] Write loop unit tests for structured tool result normalization and legacy fallback <!-- id: 3 -->
- [x] Write Chat Completions provider tests for tool-result `ContentPart` and `attachments` translation <!-- id: 4 -->
- [x] Write Responses provider tests for tool-result `ContentPart` and `attachments` translation <!-- id: 5 -->
- [x] Run focused unit tests — expect RED before implementation <!-- id: 6 -->

## Implementation Phase

- [x] Add shared tool-result normalization in `tinycua_sdk/agent/loop.py` <!-- id: 7 -->
  - [x] Preserve explicit `content: list[ContentPart]` results <!-- id: 7a -->
  - [x] Preserve `content: str` plus `attachments: list[FileAttachment]` results <!-- id: 7b -->
  - [x] Override tool-provided `role` and `call_id` with loop-owned values <!-- id: 7c -->
  - [x] Reject empty `list[ContentPart]` with clear `ValueError` matching user-message behavior <!-- id: 7d -->
  - [x] Fall back to `str(tool_result)` for unsupported legacy values <!-- id: 7e -->
- [x] Wire normalization into non-streaming tool processing <!-- id: 8 -->
  - [x] Replace direct `str(tool_result)` construction in `process_tool_calls()`
  - [x] Confirm tool execution error messages remain string-only
- [x] Wire normalization into streaming tool processing <!-- id: 9 -->
  - [x] Replace direct `str(tool_result)` construction in `process_stream_tool_calls()`
  - [x] Confirm max-tool-call and cancellation behavior is unchanged
- [x] Implement Chat Completions structured tool-result translation <!-- id: 10 -->
  - [x] Emit two-message sequence: text-only `role: "tool"` + synthetic `role: "user"` for file/image parts
  - [x] Preserve assistant `tool_calls` injection/order for tool-result batches
  - [x] Chat Completions only supports `text` content parts in tool messages — file/image parts must go in a user message
  - [x] Reuse `_translate_chat_content_part()` and `_translate_chat_attachment()`
- [x] Implement Responses structured tool-result translation <!-- id: 11 -->
  - [x] Add async helper for `function_call_output`
  - [x] Reuse `_translate_responses_content_part()` and `_translate_responses_attachment()`
  - [x] Route tool results through the async `_translate_responses_input()` path
- [x] Update canonical message documentation <!-- id: 12 -->
  - [x] Confirm `ToolResultMessage` docs match runtime behavior for structured tool returns

## Testing Phase

- [x] Run integration tests — expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/integration/test_tool_result_attachments.py` <!-- id: 13 -->
- [x] Run loop unit tests — expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/unit/test_loop.py tests/unit/test_loop_custom.py` <!-- id: 14 -->
- [x] Run provider unit tests — expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py tests/unit/test_llm_client.py` <!-- id: 15 -->
- [x] Run upload/cache regression tests to confirm Phase 5 paths still work: `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py tests/unit/test_llm_client.py -k "cache or upload"` <!-- id: 16 -->
- [x] Run full test suite: `cd src/tinycua-sdk && uv run pytest` <!-- id: 17 -->

## Verification Phase

- [x] Verify provider-native payload shapes match documented API contract for multimodal tool messages: inspect payloads via `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py::test_chat_completions_translates_tool_result_attachments_to_two_message_sequence tests/unit/test_llm_client.py::test_responses_translates_tool_result_content_parts_to_function_call_output -vxs` <!-- id: 18 -->
- [x] Verify legacy string/dict/exception tool results remain backward compatible: `cd src/tinycua-sdk && uv run pytest tests/unit/test_loop.py::test_normalize_legacy_falls_back_to_string -v` <!-- id: 19 -->
- [x] Run cache reuse test: verify repeated tool-returned non-image files reuse existing upload cache: `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py::test_chat_completions_tool_result_cache_reuse -v` <!-- id: 20 -->
- [ ] Optional manual smoke test with a vision model and a tool-generated PNG <!-- id: 21 -->

## Documentation Phase

- [x] Update tinycua-sdk docs or README to document tool-returned attachment support <!-- id: 22 -->
- [ ] Update issue #46 checklist after implementation passes review <!-- id: 23 -->

## Review and Merge

- [ ] Create pull request for Phase 6 implementation work <!-- id: 24 -->
- [ ] Address review feedback <!-- id: 25 -->
- [ ] Merge into parent feature branch after approval <!-- id: 26 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-26*
