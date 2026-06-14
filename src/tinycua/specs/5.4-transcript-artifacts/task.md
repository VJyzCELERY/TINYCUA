# Tasks: Transcript, Usage, and Artifact Compatibility

Implementation tasks for Milestone 5.4 — Transcript, Usage, and Artifact Compatibility. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests in `tests/integration/test_artifact_writing.py` (defined in implementation-plan.md) <!-- id: 0 -->
- [ ] Write unit tests in `tests/unit/test_transcript_conversion.py` for `_usage_int`, `_build_content_blocks`, `convert_working_messages_to_openclaw`, `write_usage_summary` <!-- id: 1 -->
- [ ] Run tests — expect RED (failures) since no implementation yet <!-- id: 2 -->

## Implementation Phase

### Phase 1 — OpenClaw Transcript Conversion

- [ ] Implement `_usage_int()` helper in `cli/transcript.py` <!-- id: 3 -->
  - [ ] Coerce `None` → `0`, valid int → preserved, bool → `0`, string → `0`
- [ ] Implement `_build_content_blocks()` in `cli/transcript.py` <!-- id: 4 -->
  - [ ] No tool calls → return plain string content
  - [ ] With tool calls → return list of content blocks (text + tool_use)
  - [ ] Decode `function.arguments` from JSON string to dict
- [ ] Implement `convert_working_messages_to_openclaw()` in `cli/transcript.py` <!-- id: 5 -->
  - [ ] Skip system messages
  - [ ] Map user messages to `{"type": "message", "message": {"role": "user", ...}}`
  - [ ] Map assistant messages with tool_use content blocks and per-message usage
  - [ ] Map tool_result messages to `{"type": "toolResult", "toolResult": {"callId": ..., "tool_call_id": ..., "content": ...}}`
  - [ ] Zero-fill usage when `per_message_usage` is None
- [ ] Implement `write_openclaw_jsonl()` in `cli/transcript.py` <!-- id: 6 -->
  - [ ] Write records as JSONL to disk
  - [ ] Create parent directories if needed

### Phase 2 — Usage Collection

- [ ] Capture `response.usage` events in `loops/tinycua_loop.py` `_run_stream()` <!-- id: 7 -->
  - [ ] Append `event` to `self._usage_events` when `event.get("type") == "response.usage"`
  - [ ] Expose via `usage_events` property
  - [ ] Initialize `_usage_events` in `__init__`
- [ ] Implement `write_usage_summary()` in `cli/transcript.py` <!-- id: 8 -->
  - [ ] Aggregate `input_tokens`, `output_tokens`, `total_tokens` across events
  - [ ] Zero-fill when no events (never return `{}`)
  - [ ] Write `usage.json` with all required fields

### Phase 3 — CLI Integration

- [ ] Modify `cli/run.py` to wire usage capture <!-- id: 9 -->
  - [ ] Collect `response.usage` events from streaming iterator
  - [ ] Store in a list for passing to transcript converter
- [ ] Modify `cli/run.py` to use enhanced transcript writer <!-- id: 10 -->
  - [ ] Call `convert_working_messages_to_openclaw()` with `per_message_usage`
  - [ ] Call `write_openclaw_jsonl()` for primary `transcript.jsonl`
  - [ ] Keep `write_transcript()` call for backward compatibility (raw format)
- [ ] Modify `cli/run.py` to write `usage.json` <!-- id: 11 -->
  - [ ] Call `write_usage_summary()` with captured usage events and elapsed time
- [ ] Ensure `agent.log` continues to work unchanged <!-- id: 12 -->

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 13 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 14 -->
- [ ] Verify no regressions in existing tests <!-- id: 15 -->

## Verification Phase

- [ ] Run `tinycua run "Hello"` and verify `transcript.jsonl` is written with correct schema <!-- id: 16 -->
- [ ] Verify `usage.json` is written with all required fields (zero-filled if no usage data) <!-- id: 17 -->
- [ ] Verify `agent.log` continues to write structured JSONL <!-- id: 18 -->
- [ ] Verify `transcript.jsonl` is valid JSONL (each line parseable as JSON) <!-- id: 19 -->

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
