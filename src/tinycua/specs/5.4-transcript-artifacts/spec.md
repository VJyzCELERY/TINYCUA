# Feature Specification: Transcript, Usage, and Artifact Compatibility

**Status**: Draft
**Created**: 2026-06-14
**Last Updated**: 2026-06-14
**Subproject(s) Affected**: tinycua
**Milestone**: 5.4 — Transcript, Usage, and Artifact Compatibility
**Tracking Issue**: https://github.com/VJyzCELERY/TINYCUA/issues/87

---

## Problem Statement _(mandatory)_

- **Goals**: Produce WildClawBench-compatible transcript, usage, and task-output artifacts from TinyCUA agent runs so that WildClawBench grading can consume them and benchmark scores can be collected.
- **Gaps**: The current CLI writes `agent.log` (structured JSONL) and `transcript.jsonl` (raw working messages), but the transcript format does not match WildClawBench's OpenClaw-compatible JSONL schema — it lacks tool-use content blocks, per-message usage fields, and `toolResult` records. There is no usage tracking (token counts, request count, cost) in the CLI. `TranscriptRecord` is defined but not wired into the execution pipeline. Working messages from BaseLoop are not converted to OpenClaw-compatible format.
- **Non-Goals**:
  - WildClawBench adapter implementation (Milestone 5.2).
  - Docker image creation (Milestone 5.3).
  - Full benchmark runs (Milestones 5.5–5.7).
  - Production-quality CLI/TUI UX or HITL interrupt/resume.
  - Modifying `tinycua-sdk` public APIs.
- **Constraints**:
  - Must use the existing `create_tinycua_agent()` factory and `TinyCUALoop` without SDK API modifications.
  - Transcript format MUST be OpenClaw-compatible JSONL (per `specs/wildclawbench-adapter/adapter-contract.md`).
  - Usage fields MUST be numeric (never `null`) — WildClawBench sums `message.usage` across assistant records.
  - Tool-use content blocks MUST be preserved in the transcript for safety grading.
  - Must support local OpenAI-compatible model endpoints.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer or benchmark runner invokes the TinyCUA CLI with a task prompt. The CLI runs the agent, then produces three artifacts in the output directory:
1. `agent.log` — structured JSONL log with timestamps, events, and metadata.
2. `transcript.jsonl` — OpenClaw-compatible JSONL transcript with tool-use content blocks, per-message usage, and tool-result records.
3. `usage.json` — summary usage JSON with request count, token counts, and cost.

A WildClawBench grading script can then load `transcript.jsonl` via its `transcript_loader.py` and sum `message.usage` across assistant records to produce usage totals.

### Acceptance Scenarios

1. **Given** a completed TinyCUA agent run, **When** `transcript.jsonl` is written, **Then** each line is a valid JSON object with `"type": "message"` or `"type": "toolResult"` records matching the OpenClaw-compatible schema.
2. **Given** a completed run with tool calls, **When** the transcript is inspected, **Then** assistant messages with tool calls contain `"type": "tool_use"` content blocks with `id`, `name`, and decoded `input` fields (not raw JSON strings).
3. **Given** a completed run, **When** the transcript is inspected, **Then** tool-result records include both `callId` and `tool_call_id` fields pointing to the originating tool-use call ID.
4. **Given** a completed run, **When** assistant message records are inspected, **Then** each contains a `usage` object with numeric `input`, `output`, `totalTokens` fields (never `null`) and a `cost.total` field.
5. **Given** a completed run, **When** `usage.json` is written, **Then** it contains `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `total_tokens`, `cost_usd`, `request_count`, and `elapsed_time` fields.
6. **Given** a completed run with zero usage data available, **When** `usage.json` is written, **Then** it contains zero-filled values (never an empty dict).
7. **Given** a completed run, **When** `agent.log` is written, **Then** each line is a JSON object with `timestamp`, `event`, `level`, and `data` fields.
8. **Given** a completed run, **When** the run completes, **Then** all working messages from BaseLoop are captured and available for transcript serialization (not lost as uncollected yields).
9. **Given** a transcript file, **When** loaded by WildClawBench's `transcript_loader.py`, **Then** it parses successfully as JSONL and returns a list of message records.

### Edge Cases

- What happens when the agent produces no tool calls? The transcript contains only text-content assistant messages with zeroed usage.
- What happens when the agent produces tool calls but no tool results? The transcript includes `tool_use` content blocks but no `toolResult` records — downstream grading handles missing results.
- What happens when token counts are `None` from the SDK? They are coerced to `0` (never written as `null`).
- What happens when the output directory is not writable? The CLI fails fast before agent execution.
- What happens when the agent crashes mid-execution? Partial transcript and usage data are preserved up to the crash point.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST write `agent.log` as structured JSONL with `timestamp`, `event`, `level`, and `data` fields for each entry.
- **FR-002**: System MUST write `transcript.jsonl` in OpenClaw-compatible JSONL format with `{"type": "message", "message": {...}}` records.
- **FR-003**: Assistant message records in `transcript.jsonl` MUST include tool-use content blocks (`"type": "tool_use"`) with decoded `input` fields when the assistant made tool calls.
- **FR-004**: `transcript.jsonl` MUST include `toolResult` records with both `callId` and `tool_call_id` fields for each tool execution result.
- **FR-005**: Assistant message records MUST include a `usage` object with numeric `input`, `output`, `totalTokens` fields (coerced from nullable to non-negative int) and `cost.total` (float).
- **FR-006**: System MUST NOT embed cumulative usage totals in every assistant message — each message MUST receive only its per-response usage.
- **FR-007**: System MUST write `usage.json` with fields: `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `total_tokens`, `cost_usd`, `request_count`, `elapsed_time`.
- **FR-008**: `usage.json` MUST never be an empty dict — when usage data is unavailable, zero-filled values MUST be returned.
- **FR-009**: System MUST capture working messages from BaseLoop for transcript serialization rather than letting them go uncollected.
- **FR-010**: System MUST coerce nullable token counts from the SDK to non-negative integers before writing to transcript or usage files.
- **FR-011**: System MUST support configurable output directory via CLI `--output-dir` flag (default: `/tmp_workspace/results`).
- **FR-012**: System MUST preserve user messages, assistant messages, and tool-result messages in the transcript — system messages are excluded.
- **FR-013**: `transcript.jsonl` path MUST be configurable and default to `transcript.jsonl` in the output directory.

### Key Entities _(include if feature involves data)_

- **TranscriptRecord**: Wraps a stream event with run-level metadata (`run_id`, `session_id`, `sequence`) for JSONL serialization. Used as a side channel for lifecycle event logging; the primary transcript uses the OpenClaw format from `convert_working_messages_to_openclaw()`. Already defined in `config/types.py`.
- **UsageSummary**: Aggregate usage data for `usage.json` output — token counts, request count, cost, elapsed time.
- **OpenClaw Transcript Record**: A JSON object with `"type"` field (`"message"` or `"toolResult"`) and corresponding payload. Schema defined in `specs/wildclawbench-adapter/adapter-contract.md`.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Transcript is OpenClaw-compatible**: `transcript.jsonl` can be loaded by WildClawBench's `transcript_loader.py` without errors.
- [ ] **Tool-use blocks preserved**: Assistant messages with tool calls contain `tool_use` content blocks with decoded inputs.
- [ ] **Tool-result records present**: Each tool execution produces a `toolResult` record with both `callId` and `tool_call_id`.
- [ ] **Usage is numeric**: All `usage` fields in assistant messages are non-negative integers (never `null`).
- [ ] **Usage summary written**: `usage.json` contains all required fields with zero-filled fallback.
- [ ] **agent.log written**: Structured JSONL log with timestamp/event/level/data fields.
- [ ] **Working messages captured**: Working messages from BaseLoop are collected for transcript serialization.
- [ ] **Tests pass**: Unit and integration tests for transcript conversion, usage collection, and artifact writing.

---

## Testing Plan _(mandatory)_

### Unit Tests

- [ ] Test OpenClaw transcript conversion: working messages → JSONL records with correct schema.
- [ ] Test tool-use content block generation: assistant messages with `tool_calls` produce `tool_use` blocks with decoded input.
- [ ] Test `toolResult` record generation: tool-result messages produce records with `callId` and `tool_call_id`.
- [ ] Test usage coercion: `None` token counts → `0`, valid counts → preserved.
- [ ] Test usage summary: correct aggregation from per-message usage.
- [ ] Test usage fallback: zero-filled dict when no usage data available.
- [ ] Test `agent.log` writing: structured JSONL with correct fields.
- [ ] Test system message exclusion: system messages are not written to transcript.

### Integration Tests

- [ ] Test end-to-end transcript writing: agent run → `transcript.jsonl` → parseable by JSONL loader.
- [ ] Test end-to-end usage writing: agent run → `usage.json` with correct fields.
- [ ] Test working message capture: working messages from BaseLoop are collected and serializable.

### Manual Tests _(if applicable)_

- [ ] Verify `transcript.jsonl` loads in WildClawBench's `transcript_loader.py` (if test harness available).

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| `agent.log` writing | Done | `cli/logging.py` — `write_log_entry()` |
| `transcript.jsonl` basic writing | Done | `cli/transcript.py` — `write_transcript()` |
| OpenClaw-compatible format | TODO | Need tool_use blocks, toolResult records, usage |
| Per-message usage in transcript | TODO | Need to capture `response.usage` events |
| `usage.json` writing | TODO | New — aggregate usage summary |
| Working message capture | TODO | Wire working messages from BaseLoop into transcript conversion |
| Usage coercion | TODO | `_usage_int()` helper for nullable tokens |

---

## Open Questions _(optional)_

1. **Should `TranscriptRecord` be used for the primary transcript or as a side channel?**
   - **Owner**: @VJyzCELERY
   - **Status**: Resolved
   - **Resolution**: Use `TranscriptRecord` as a side channel for lifecycle events; the primary transcript uses the OpenClaw format from `convert_working_messages_to_openclaw()` enhanced with tool-use blocks and usage.

2. **Should usage be captured from `_run_stream()` `response.usage` events or from the SDK's `cumulative_usage`?**
   - **Owner**: @VJyzCELERY
   - **Status**: Resolved
   - **Resolution**: Capture from `_run_stream()` `response.usage` stream events for per-response granularity; aggregate into `usage.json` at the end.

---

## Review Checklist

- [x] No implementation details beyond what the design docs specify
- [x] All mandatory sections completed
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
- [x] Exit criteria match Milestone 5.4 from the roadmap issue
