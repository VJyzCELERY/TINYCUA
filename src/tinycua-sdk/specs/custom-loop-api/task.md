# Tasks: Custom Loop Creation API Simplification

Implementation tasks for the Custom Loop Creation API Simplification feature. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for custom loop using public helpers (defined in `implementation-plan.md`) <!-- id: 0 -->
- [ ] Run integration tests — expect SKIP (skipped due to no LLM server) or RED (failures) since implementation not yet updated <!-- id: 1 -->

## Implementation Phase — Phase 1: Promote Private Methods to Public

- [ ] Rename `_build_system_message` → `build_system_message` in `loop.py` <!-- id: 2 -->
  - [ ] Update all internal references in `loop.py` (`_run_sync`, `_run_stream`)
  - [ ] Update test references in `tests/unit/test_loop.py` (`TestBaseLoopBuildSystemMessage`)
- [ ] Rename `_last_assistant_content` → `last_assistant_content` in `loop.py` <!-- id: 3 -->
  - [ ] Update all internal references in `loop.py` (`_run_sync`)
  - [ ] Ensure `last_assistant_content` remains a `@staticmethod`
- [ ] Run sync tests after rename — all pass <!-- id: 4 -->

## Implementation Phase — Phase 2: Extract Sync Tool Processing

- [ ] Extract `async process_tool_calls()` from inline loop in `_run_sync()` <!-- id: 5 -->
  - [ ] Move tool call iteration, JSON parsing, tool lookup, `ToolExecutor.execute()`, max_tool_calls guard, and message appending into new public method
  - [ ] New signature: `async process_tool_calls(agent, tools, tool_calls, working_messages, tool_call_count) -> tuple[int, bool]`
  - [ ] Returns `(updated_tool_call_count, max_tool_calls_reached)` for the caller
- [ ] Restructure `_run_sync()` to ~40 lines as thin orchestrator <!-- id: 6 -->
  - [ ] Body: build system message → iteration loop → guard checks → `_call_llm` → delegate to `process_tool_calls()` | return content
- [ ] Run sync tests — all pass (including `test_run_multiple_tool_calls_in_one_response`, `test_run_max_tool_calls_in_single_response`, `test_run_max_tool_calls_break`) <!-- id: 7 -->

## Implementation Phase — Phase 3: Extract Stream Processing

- [ ] Create `process_stream_iteration()` async generator method <!-- id: 8 -->
  - [ ] Combine `_yield_first_chunk_events` + `_yield_stream_body_events` logic into single public method
  - [ ] Signature: `process_stream_iteration(llm_stream, agent, content_parts, tool_calls_buffer, cumulative_usage, usage_settled_ids) -> AsyncIterator[dict]`
  - [ ] Yields raw SSE events plus synthetic lifecycle events (`response.created`, `response.in_progress`, `response.cancelled`, etc.)
  - [ ] No `_IterStreamState` dependency — use local variables
- [ ] Create `async process_stream_tool_calls()` method <!-- id: 9 -->
  - [ ] Cleaned-up version of `_execute_tools_stream()`
  - [ ] Signature: `async process_stream_tool_calls(agent, tools, tool_calls_list, working_messages, tool_call_count) -> tuple[int, bool]`
  - [ ] Returns `(tool_call_count, max_tool_calls_reached)` — simpler than current triple return
  - [ ] Appends `function_call` and `function_call_output` messages to `working_messages`
- [ ] Remove `_IterStreamState` dataclass <!-- id: 10 -->
- [ ] Remove `_yield_first_chunk_events()` method <!-- id: 11 -->
- [ ] Remove `_yield_stream_body_events()` method <!-- id: 12 -->
- [ ] Remove `_execute_tools_stream()` method <!-- id: 13 -->
- [ ] Restructure `_run_stream()` to ~55 lines as thin orchestrator <!-- id: 14 -->
  - [ ] Body: build system message → init state → try/except → iteration loop → `_call_llm`(stream=True) → delegate to `process_stream_iteration()` → handle tool calls via `process_stream_tool_calls()` | return content → yield usage + completion events
  - [ ] Track `cancelled`, `provider_failed`, `completed_by_provider` as local booleans
- [ ] Run stream tests — all pass (all `TestBaseLoopRunStream`, `TestBaseLoopRunStreamInProgress`) <!-- id: 15 -->

## Implementation Phase — Phase 4: New Unit Tests

- [ ] Write unit test: custom loop subclass calls `build_system_message()` directly <!-- id: 16 -->
- [ ] Write unit test: custom loop subclass calls `process_tool_calls()` with fake LLM response <!-- id: 17 -->
- [ ] Write unit test: custom loop subclass calls `process_stream_iteration()` with fake async LLM stream, covering lifecycle event ordering, content accumulation, tool-call buffering, cancellation, provider failure, and usage settlement behavior <!-- id: 18 -->
- [ ] Write unit test: custom loop subclass calls `process_stream_tool_calls()` with fake tool calls <!-- id: 19 -->
- [ ] Write unit test: custom loop subclass calls `last_assistant_content()` directly <!-- id: 20 -->

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass with real LLM) or SKIP (no LLM server) <!-- id: 21 -->
- [ ] Run full test suite: `cd src/tinycua-sdk && uv run pytest` <!-- id: 22 -->
- [ ] Verify line count: `_run_sync()` ≤ 45 lines <!-- id: 23 -->
- [ ] Verify line count: `_run_stream()` ≤ 60 lines <!-- id: 24 -->
- [ ] Verify no private `_` helpers called from tests (except truly internal `_accumulate_chunk`, `_read_stream_chunk`, `_iter_llm_events`, `_call_llm`) <!-- id: 25 -->

## Verification Phase

- [ ] Confirm all existing tests in `test_loop.py`, `test_loop_custom.py` pass without modifications (only intentional renames) <!-- id: 26 -->
- [ ] Confirm `Agent` class API unchanged — no new public methods on `Agent` <!-- id: 27 -->
- [ ] Confirm `BaseLoop.run()` signature unchanged — backward compatible <!-- id: 28 -->
- [ ] Run ruff linting: `cd src/tinycua-sdk && uv run ruff check tinycua_sdk/ tests/` <!-- id: 29 -->

## Documentation Phase

- [ ] Update docstrings on new public helper methods with Args/Returns sections <!-- id: 30 -->
- [ ] Ensure `__all__` in `loop.py` is updated if needed <!-- id: 31 -->

## Review and Merge

- [ ] Create pull request with summary of changes <!-- id: 32 -->
- [ ] Address review feedback <!-- id: 33 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-17*
