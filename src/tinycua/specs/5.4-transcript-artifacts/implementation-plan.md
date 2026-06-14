# Implementation: Transcript, Usage, and Artifact Compatibility

Produce WildClawBench-compatible transcript, usage, and task-output artifacts from TinyCUA agent runs. Enhances the CLI `run` command to emit an OpenClaw-compatible JSONL transcript with tool-use content blocks, per-message usage, and tool-result records; a usage summary JSON; and structured agent logs.

## Context

- **Spec Reference**: `./spec.md` — Milestone 5.4
- **Design Reference**: `./design.md` — 4-phase implementation plan
- **Priority**: P1 (required for WildClawBench integration)
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [x] **None** — no configuration dependencies

### Running Services

- [x] **None** — no external services needed

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11+
- [x] **Package manager**: uv
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/integration/test_artifact_writing.py
"""Integration tests for transcript, usage, and log artifact writing."""


def test_end_to_end_transcript_writing(tmp_path: Path) -> None:
    """Agent working messages produce a parseable OpenClaw-compatible transcript.jsonl."""
    # Arrange
    working_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a file."},
        {
            "role": "assistant",
            "content": "I'll write that file.",
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path": "/tmp/test.txt", "content": "hello"}',
                    },
                }
            ],
        },
        {"role": "tool_result", "call_id": "call_abc123", "content": "File written."},
        {"role": "assistant", "content": "Done."},
    ]
    transcript_path = tmp_path / "transcript.jsonl"

    # Act
    from tinycua.cli.transcript import convert_working_messages_to_openclaw, write_openclaw_jsonl
    records = convert_working_messages_to_openclaw(working_messages)
    write_openclaw_jsonl(records, transcript_path)

    # Assert
    import json
    lines = transcript_path.read_text().strip().split("\n")
    parsed = [json.loads(line) for line in lines]
    # System messages excluded
    assert all(r["type"] in ("message", "toolResult") for r in parsed)
    # tool_use blocks preserved
    assistant_with_tools = [r for r in parsed if r["type"] == "message" and r["message"]["role"] == "assistant" and isinstance(r["message"]["content"], list)]
    assert len(assistant_with_tools) == 1
    tool_blocks = [b for b in assistant_with_tools[0]["message"]["content"] if b["type"] == "tool_use"]
    assert len(tool_blocks) == 1
    assert tool_blocks[0]["id"] == "call_abc123"
    assert tool_blocks[0]["input"]["path"] == "/tmp/test.txt"
    # toolResult record present
    tool_results = [r for r in parsed if r["type"] == "toolResult"]
    assert len(tool_results) == 1
    assert tool_results[0]["toolResult"]["callId"] == "call_abc123"
    assert tool_results[0]["toolResult"]["tool_call_id"] == "call_abc123"


def test_end_to_end_usage_writing(tmp_path: Path) -> None:
    """Usage summary is written to usage.json with correct fields."""
    # Arrange
    from tinycua.cli.transcript import write_usage_summary
    usage_events = [
        {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        {"input_tokens": 200, "output_tokens": 80, "total_tokens": 280},
    ]
    usage_path = tmp_path / "usage.json"

    # Act
    write_usage_summary(usage_path, usage_events, elapsed_time=12.5)

    # Assert
    import json
    data = json.loads(usage_path.read_text())
    assert data["input_tokens"] == 300
    assert data["output_tokens"] == 130
    assert data["total_tokens"] == 430
    assert data["cache_read_tokens"] == 0
    assert data["cache_write_tokens"] == 0
    assert data["cost_usd"] == 0.0
    assert data["request_count"] == 2
    assert data["elapsed_time"] == 12.5


def test_usage_summary_zero_filled_fallback(tmp_path: Path) -> None:
    """Empty usage events produce zero-filled usage.json, never {}."""
    # Arrange
    from tinycua.cli.transcript import write_usage_summary
    usage_path = tmp_path / "usage.json"

    # Act
    write_usage_summary(usage_path, [], elapsed_time=0.0)

    # Assert
    import json
    data = json.loads(usage_path.read_text())
    assert data["input_tokens"] == 0
    assert data["output_tokens"] == 0
    assert data["total_tokens"] == 0
    assert data["request_count"] == 0
    assert data["elapsed_time"] == 0.0


def test_usage_int_bool_returns_zero():
    """_usage_int() coerces booleans to 0, not 1."""
    assert _usage_int(True) == 0
    assert _usage_int(False) == 0
```

### Key Test Scenarios

- [ ] **Scenario 1**: Working messages with tool calls → `transcript.jsonl` with tool_use content blocks and toolResult records
- [ ] **Scenario 2**: Usage events → `usage.json` with aggregated token counts
- [ ] **Scenario 3**: Zero usage → zero-filled `usage.json` (never empty dict)

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for `_usage_int()`, `_build_content_blocks()`, `convert_working_messages_to_openclaw()`, `write_usage_summary()`
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Run `tinycua run "Hello"` and verify `transcript.jsonl`, `usage.json`, and `agent.log` are written to the output directory
- [ ] Verify `transcript.jsonl` is valid JSONL (each line is parseable JSON)

### Performance Considerations

- [ ] N/A — transcript conversion is O(n) in message count; no performance concern for typical agent runs

## Proposed Changes

### CLI Transcript Module

#### [MODIFY] `tinycua/cli/transcript.py`

- **Add `_usage_int()` helper**: Coerce nullable token counts to non-negative integers. Prevents `null` in JSON output.
- **Add `_build_content_blocks()`**: Build content field from assistant messages with tool calls. Returns list of content blocks (text + tool_use) when tool calls present, plain string otherwise.
- **Add `convert_working_messages_to_openclaw()`**: Convert BaseLoop working messages to OpenClaw-compatible JSONL records. Handles user, assistant, and tool_result roles; skips system messages. Accepts optional `per_message_usage` for per-response token counts.
- **Add `write_openclaw_jsonl()`**: Write converted records to disk as JSONL.
- **Add `write_usage_summary()`**: Aggregate per-response usage events into `usage.json` with zero-filled fallback.
- **Preserve existing `write_transcript()`**: Unchanged for backward compatibility.

#### [MODIFY] `tinycua/cli/run.py`

- **Wire usage capture**: After agent execution, collect `response.usage` events from the streaming iterator into a list. Pass to `convert_working_messages_to_openclaw()` as `per_message_usage`.
- **Call enhanced transcript writer**: Use `convert_working_messages_to_openclaw()` + `write_openclaw_jsonl()` for the primary `transcript.jsonl` output. Keep `write_transcript()` call for backward compatibility (raw format).
- **Write `usage.json`**: Call `write_usage_summary()` with captured usage events and elapsed time.
- **Ensure `agent.log` continues unchanged**: No changes to `write_log_entry()` calls.

#### [MODIFY] `tinycua/loops/tinycua_loop.py`

- **Capture `response.usage` events**: In `_run_stream()`, when `event.get("type") == "response.usage"`, append the usage dict to a collected list. Expose via a new `usage_events` property.

### New Test Files

#### [NEW] `tests/unit/test_transcript_conversion.py`

- Unit tests for `_usage_int()` — None, valid int, bool, string
- Unit tests for `_build_content_blocks()` — no tool calls, with tool calls, empty content
- Unit tests for `convert_working_messages_to_openclaw()` — user/assistant/tool_result/system messages
- Unit tests for `write_usage_summary()` — aggregation, zero-filled fallback

#### [NEW] `tests/integration/test_artifact_writing.py`

- Integration test: working messages → `transcript.jsonl` → parseable as JSONL
- Integration test: usage events → `usage.json` with correct fields
- Integration test: zero usage → zero-filled `usage.json`

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `cli/transcript.py` | Modify | Add OpenClaw conversion, content block builder, usage coercion, usage summary writer |
| `cli/run.py` | Modify | Wire usage capture, call enhanced transcript writer, write usage.json |
| `loops/tinycua_loop.py` | Modify | Capture `response.usage` events during streaming |
| `tests/unit/test_transcript_conversion.py` | New | Unit tests for transcript conversion functions |
| `tests/integration/test_artifact_writing.py` | New | Integration tests for end-to-end artifact production |

## Data Model Changes

```python
# New helper — no new types, just functions
# UsageSummary is written as a plain dict to usage.json:
# {
#     "input_tokens": int,
#     "output_tokens": int,
#     "cache_read_tokens": int,
#     "cache_write_tokens": int,
#     "total_tokens": int,
#     "cost_usd": float,
#     "request_count": int,
#     "elapsed_time": float
# }
```

## API Changes

### New Functions (internal, not public API)

| Function | Module | Description |
|----------|--------|-------------|
| `_usage_int(value) -> int` | `cli/transcript.py` | Coerce nullable token count to int |
| `_build_content_blocks(entry, tool_calls) -> str \| list[dict]` | `cli/transcript.py` | Build content field with tool_use blocks |
| `convert_working_messages_to_openclaw(working, per_message_usage) -> list[dict]` | `cli/transcript.py` | Convert BaseLoop messages to OpenClaw format |
| `write_openclaw_jsonl(records, path) -> None` | `cli/transcript.py` | Write converted records to JSONL |
| `write_usage_summary(path, usage_events, elapsed_time) -> None` | `cli/transcript.py` | Write aggregated usage.json |

### Modified Endpoints

None — CLI interface unchanged (`tinycua run` signature and flags remain the same).

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| (none) | — | All dependencies already present |

### Internal Dependencies

- [ ] Depends on existing `BaseLoop._working_messages` (already implemented)
- [ ] Depends on existing `write_transcript()` (preserved for backward compat)

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `response.usage` events not emitted by local model endpoints | Medium | Medium | Zero-fill fallback in `usage.json`; document that local models may not report token counts |
| `tool_calls` format varies by provider | Medium | Low | Normalize via SDK's existing tool-call shape (`function.name`, `function.arguments` as JSON string) |
| Working message list doesn't include all messages needed for transcript | Low | High | Verify with integration tests that all user/assistant/tool_result messages are captured |
| WildClawBench transcript_loader.py rejects our format | Low | High | Test with the actual loader; follow the adapter-contract.md schema exactly |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-14*
