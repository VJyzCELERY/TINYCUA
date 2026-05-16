# Tasks: Custom Loop Creation API Simplification

Implementation tasks for the Custom Loop Creation API Simplification feature. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests for custom loop using public helpers (defined in `implementation-plan.md`) <!-- id: 0 -->
- [x] Run integration tests — expect SKIP (skipped due to no LLM server) or RED (failures) since implementation not yet updated <!-- id: 1 -->
- [x] Write unit test: custom loop subclass calls `build_system_message()` directly <!-- id: 16 -->
- [x] Write unit test: custom loop subclass calls `process_tool_calls()` with fake LLM response <!-- id: 17 -->
- [x] Write unit test: custom loop subclass calls `process_stream_iteration()` with fake async LLM stream, covering lifecycle event ordering, content accumulation, tool-call buffering, cancellation, provider failure, and usage settlement behavior <!-- id: 18 -->
- [x] Write unit test: custom loop subclass calls `process_stream_tool_calls()` with fake tool calls <!-- id: 19 -->
- [x] Write unit test: custom loop subclass calls `last_assistant_content()` directly <!-- id: 20 -->
- [x] Run unit tests — expect RED since implementation not yet updated <!-- id: 33 -->

## Implementation Phase — Phase 1: Promote Private Methods to Public

- [x] Rename `_build_system_message` → `build_system_message` in `loop.py` <!-- id: 2 -->
  - [x] Update all internal references in `loop.py` (`_run_sync`, `_run_stream`)
  - [x] Update test references in `tests/unit/test_loop.py` (`TestBaseLoopBuildSystemMessage`)
- [x] Rename `_last_assistant_content` → `last_assistant_content` in `loop.py` <!-- id: 3 -->
  - [x] Update all internal references in `loop.py` (`_run_sync`)
  - [x] Ensure `last_assistant_content` remains a `@staticmethod`
- [x] Run sync tests after rename — all pass <!-- id: 4 -->

## Implementation Phase — Phase 2: Extract Sync Tool Processing

- [x] Extract `async process_tool_calls()` from inline loop in `_run_sync()` <!-- id: 5 -->
  - [x] Move tool call iteration, JSON parsing, tool lookup, `ToolExecutor.execute()`, max_tool_calls guard, and message appending into new public method
  - [x] New signature: `async process_tool_calls(agent, tools, tool_calls, working_messages, tool_call_count, assistant_content="") -> tuple[int, bool]`
  - [x] Appends an assistant message before `function_call` / `function_call_output` messages whenever tool calls are executed; the message uses `assistant_content` and is still appended even when the assistant content is empty, preserving current ordering
  - [x] Returns `(updated_tool_call_count, max_tool_calls_reached)` for the caller
- [x] Restructure `_run_sync()` to ~40 lines as thin orchestrator <!-- id: 6 -->
  - [x] Body: build system message → iteration loop → guard checks → `_call_llm` → delegate to `process_tool_calls()` | return content
- [x] Run sync tests — all pass (including `test_run_multiple_tool_calls_in_one_response`, `test_run_max_tool_calls_in_single_response`, `test_run_max_tool_calls_break`) <!-- id: 7 -->

## Implementation Phase — Phase 3: Extract Stream Processing

- [x] Create `process_stream_iteration()` async generator method <!-- id: 8 -->
  - [x] Combine `_yield_first_chunk_events` + `_yield_stream_body_events` logic into single public method
  - [x] Signature: `process_stream_iteration(llm_stream, agent, content_parts, tool_calls_buffer, cumulative_usage, usage_settled_ids) -> AsyncIterator[dict]`
  - [x] Yields raw SSE events plus synthetic lifecycle events (`response.created`, `response.in_progress`, `response.cancelled`, etc.)
  - [x] No `_IterStreamState` dependency — use local variables
- [x] Create `async process_stream_tool_calls()` method <!-- id: 9 -->
  - [x] Cleaned-up version of `_execute_tools_stream()`
  - [x] Signature: `async process_stream_tool_calls(agent, tools, tool_calls_list, working_messages, tool_call_count, combined_content="") -> tuple[int, bool]`
  - [x] Accepts `combined_content` (accumulated stream text) and appends assistant message to `working_messages` before function-call messages, preserving correct ordering
  - [x] Returns `(tool_call_count, max_tool_calls_reached)` — simpler than current triple return
  - [x] Appends an assistant message using `combined_content` before `function_call` and `function_call_output` messages whenever stream tool calls are executed; the message is still appended when `combined_content` is empty, preserving current ordering.
- [x] Remove `_IterStreamState` dataclass <!-- id: 10 -->
- [x] Remove `_yield_first_chunk_events()` method <!-- id: 11 -->
- [x] Remove `_yield_stream_body_events()` method <!-- id: 12 -->
- [x] Remove `_execute_tools_stream()` method <!-- id: 13 -->
- [x] Restructure `_run_stream()` to ~55 lines as thin orchestrator <!-- id: 14 -->
  - [x] Body: build system message → init state → try/except → iteration loop → `_call_llm`(stream=True) → delegate to `process_stream_iteration()` → handle tool calls via `process_stream_tool_calls()` | return content → yield usage + completion events
  - [x] Track `cancelled`, `provider_failed`, `completed_by_provider` as local booleans
- [x] Run stream tests — all pass (all `TestBaseLoopRunStream`, `TestBaseLoopRunStreamInProgress`) <!-- id: 15 -->

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass with real LLM) or SKIP (no LLM server) <!-- id: 21 -->
- [x] Run full test suite: `cd src/tinycua-sdk && uv run pytest` <!-- id: 22 -->
- [x] Verify line count: `_run_sync()` ≤ 45 lines <!-- id: 23 -->
- [x] Verify line count: `_run_stream()` ≤ 60 lines <!-- id: 24 -->
- [x] Verify no private `_` helpers called from tests (except truly internal `_accumulate_chunk`, `_read_stream_chunk`, `_iter_llm_events`, `_call_llm`) <!-- id: 25 -->

## Verification Phase

- [x] Confirm all existing tests in `test_loop.py`, `test_loop_custom.py` pass without modifications (only intentional renames) <!-- id: 26 -->
- [x] Confirm `Agent` class API unchanged — no new public methods on `Agent` <!-- id: 27 -->
- [x] Confirm `BaseLoop.run()` signature unchanged — backward compatible <!-- id: 28 -->
- [x] Run ruff linting: `cd src/tinycua-sdk && uv run ruff check tinycua_sdk/ tests/` <!-- id: 29 -->

## Documentation Phase

- [x] Update docstrings on new public helper methods with Args/Returns sections <!-- id: 30 -->
- [x] Ensure `__all__` in `loop.py` is updated if needed <!-- id: 31 -->

## Review and Merge

- [x] Create pull request with summary of changes — PR #38 already exists <!-- id: 32 -->
- [ ] Address review feedback <!-- id: 34 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-17*
