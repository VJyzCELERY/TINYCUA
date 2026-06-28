# Tasks: Transcript, Usage, and Artifact Compatibility

Implementation tasks for Milestone 5.4 — Transcript, Usage, and Artifact Compatibility. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests in `tests/integration/test_artifact_writing.py` (defined in implementation-plan.md) <!-- id: 0 -->
- [x] Write unit tests in `tests/unit/test_transcript_conversion.py` for `_usage_int`, `_build_content_blocks`, `convert_working_messages_to_openclaw`, `write_usage_summary` <!-- id: 1 -->
- [x] Run tests — expect RED (failures) since no implementation yet <!-- id: 2 -->

## Implementation Phase

### Phase 1 — OpenClaw Transcript Conversion

- [x] Implement `_usage_int()` helper in `cli/transcript.py` <!-- id: 3 -->
  - [x] Coerce `None` → `0`, valid int → preserved, bool → `0`, string → `0`
- [x] Implement `_build_content_blocks()` in `cli/transcript.py` <!-- id: 4 -->
  - [x] No tool calls → return plain string content
  - [x] With tool calls → return list of content blocks (text + tool_use)
  - [x] Decode `function.arguments` from JSON string to dict
- [x] Implement `convert_working_messages_to_openclaw()` in `cli/transcript.py` <!-- id: 5 -->
  - [x] Skip system messages
  - [x] Map user messages to `{"type": "message", "message": {"role": "user", ...}}`
  - [x] Map assistant messages with tool_use content blocks and per-message usage
  - [x] Map tool_result messages to `{"type": "toolResult", "toolResult": {"callId": ..., "tool_call_id": ..., "content": ...}}`
  - [x] Zero-fill usage when `per_message_usage` is None
- [x] Implement `write_openclaw_jsonl()` in `cli/transcript.py` <!-- id: 6 -->
  - [x] Write records as JSONL to disk
  - [x] Create parent directories if needed

### Phase 2 — Usage Collection

- [x] Capture `response.usage` events in `loops/tinycua_loop.py` `_run_stream()` <!-- id: 7 -->
  - [x] Append `event` to `self._usage_events` when `event.get("type") == "response.usage"`
  - [x] Expose via `usage_events` property
  - [x] Initialize `_usage_events` in `__init__`
- [x] Implement `write_usage_summary()` in `cli/transcript.py` <!-- id: 8 -->
  - [x] Aggregate `input_tokens`, `output_tokens`, `total_tokens` across events
  - [x] Zero-fill when no events (never return `{}`)
  - [x] Write `usage.json` with all required fields

### Phase 3 — CLI Integration

- [x] Modify `cli/run.py` to wire usage capture <!-- id: 9 -->
  - [x] Collect `response.usage` events from streaming iterator
  - [x] Store in a list for passing to transcript converter
  - [x] Switch `cli/run.py` from `agent.run(prompt)` to streaming execution (`agent.run_stream(prompt)` or equivalent) to enable usage event collection <!-- id: 27 -->
- [x] Modify `cli/run.py` to use enhanced transcript writer <!-- id: 10 -->
  - [x] Call `convert_working_messages_to_openclaw()` with `per_message_usage`
  - [x] Call `write_openclaw_jsonl()` for primary `transcript.jsonl`
  - [x] Keep `write_transcript()` call for backward compatibility (raw format)
- [x] Modify `cli/run.py` to write `usage.json` <!-- id: 11 -->
  - [x] Call `write_usage_summary()` with captured usage events and elapsed time
- [x] Ensure `agent.log` continues to work unchanged <!-- id: 12 -->

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 13 -->
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 14 -->
- [x] Verify no regressions in existing tests <!-- id: 15 -->
- [x] Run linter: `cd src/tinycua && uv run ruff check .` <!-- id: 25 -->
- [x] Run type checker: `cd src/tinycua && uv run mypy tinycua/` <!-- id: 26 -->

## Verification Phase

- [ ] Run `tinycua run "Hello"` and verify `transcript.jsonl` is written with correct schema <!-- id: 16 -->
- [ ] Verify `usage.json` is written with all required fields (zero-filled if no usage data) <!-- id: 17 -->
- [ ] Verify `agent.log` continues to write structured JSONL <!-- id: 18 -->
- [ ] Verify `transcript.jsonl` is valid JSONL (each line parseable as JSON) <!-- id: 19 -->
- [ ] Verify streaming mode output matches non-streaming mode for CLI use case <!-- id: 24 -->
  - [ ] Run `tinycua run "Hello"` with streaming and verify transcript.jsonl content is identical
  - [ ] Confirm no performance regression for typical prompts

## Documentation Phase

- [ ] Update spec.md status tracker with completed items <!-- id: 20 -->

## Review and Merge

- [ ] Verify PR #135 body and title are up to date <!-- id: 21 -->
- [ ] Address review feedback <!-- id: 22 -->
- [ ] Merge to base branch <!-- id: 23 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-14*
