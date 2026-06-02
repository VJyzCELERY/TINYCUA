# Tasks: Chat Completions Reasoning Content Normalization

Implementation tasks for Chat Completions Reasoning Content Normalization. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write unit tests for streaming reasoning content normalization in `test_openai_chat_client.py` <!-- id: 0 -->
- [x] Write unit tests for non-streaming reasoning content normalization in `test_openai_chat_client.py` <!-- id: 1 -->
- [x] Run tests — expect RED (failures) since no implementation yet <!-- id: 2 -->

## Implementation Phase

- [x] Add `reasoning_content: str | None` field to `LLMResponse` in `events.py` <!-- id: 3 -->
- [x] Add `ReasoningDeltaEvent` and `ReasoningDoneEvent` to imports in `open_ai_chat_completions.py` <!-- id: 4 -->
- [x] Add `reasoning_parts` and `reasoning_done_emitted` fields to `ChoiceAccumulator` <!-- id: 5 -->
- [x] Extend `_normalize_chunk_content` to inspect `reasoning_content` and emit `ReasoningDeltaEvent` <!-- id: 6 -->
- [x] Extend `_normalize_chunk_finalize` to emit `ReasoningDoneEvent` before `ContentDoneEvent` <!-- id: 7 -->
- [x] Extend `_normalize_non_streaming_response` to extract `reasoning_content` from message <!-- id: 8 -->

## Testing Phase

- [x] Run tests — expect GREEN (all pass) <!-- id: 9 -->
- [x] Run full test suite: `cd src/tinycua-sdk && uv run pytest` <!-- id: 10 -->

## Verification Phase

- [x] Verify backward compatibility — existing streaming and non-streaming tests pass <!-- id: 11 -->

## Review and Merge

- [ ] Create pull request <!-- id: 12 -->
- [ ] Address review feedback <!-- id: 13 -->
- [ ] Merge to main branch <!-- id: 14 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-02*
