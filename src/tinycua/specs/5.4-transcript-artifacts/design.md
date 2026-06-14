# Design Document: Transcript, Usage, and Artifact Compatibility

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-14

---

## Overview

This design implements Milestone 5.4 — Transcript, Usage, and Artifact Compatibility. It enhances the existing CLI `run` command to produce WildClawBench-compatible artifacts: an OpenClaw-compatible JSONL transcript with tool-use content blocks, per-message usage, and tool-result records; a usage summary JSON; and structured agent logs. The design extends the existing `write_transcript()` function with a full OpenClaw converter and adds usage collection from SDK stream events.

---

## Architecture

### Component Overview

```
TinyCUALoop.run(stream=True)
  → _run_stream()
      → yields LLM delta events + lifecycle events
      → UsageCollector captures response.usage events
      → TranscriptCollector captures lifecycle events as TranscriptRecords

CLI run.py
  → runs agent (stream=True or stream=False)
  → collects working_messages + usage_events + lifecycle_events
  → write_transcript_enhanced()
      → convert_working_messages_to_openclaw()
          → preserves tool_use content blocks
          → adds per-message usage
          → generates toolResult records
      → write_openclaw_jsonl()
  → write_usage_summary()
  → write_log_entry() (existing)
```

### Affected Components

> **Path convention**: All paths are relative to `src/tinycua/tinycua/`.

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `cli/transcript.py` | Modified | Add `convert_working_messages_to_openclaw()`, `_build_content_blocks()`, `_usage_int()`, `write_openclaw_jsonl()` |
| `cli/run.py` | Modified | Wire usage capture, call enhanced transcript writer, write `usage.json` |
| `cli/logging.py` | No change | Already satisfies FR-001 (timestamp, event, level, data fields) |
| `config/types.py` | No change | `TranscriptRecord` already defined |
| `loops/tinycua_loop.py` | Modified | Capture `response.usage` events during streaming for usage collection |
| `tests/unit/test_transcript_conversion.py` | New | Unit tests for OpenClaw conversion |
| `tests/unit/test_usage_collection.py` | New | Unit tests for usage summary |
| `tests/integration/test_artifact_writing.py` | New | Integration tests for end-to-end artifact production |

---

## Data Model

### Usage Summary

```python
# Written to usage.json
UsageSummary:
    input_tokens: int          # sum of per-response input tokens
    output_tokens: int         # sum of per-response output tokens
    cache_read_tokens: int     # always 0 (local models don't cache)
    cache_write_tokens: int    # always 0
    total_tokens: int          # input + output
    cost_usd: float            # 0.0 for local models
    request_count: int         # number of LLM requests made
    elapsed_time: float        # wall-clock seconds
```

### OpenClaw Transcript Record Shapes

```python
# Message record
{"type": "message", "message": {"role": "assistant", "content": [...], "usage": {...}}}

# Tool result record
{"type": "toolResult", "toolResult": {"callId": "...", "tool_call_id": "...", "content": "..."}}
```

### Schema Changes

- No changes to existing data structures. The `UsageSummary` type is additive (new). The transcript format is enhanced but backward-compatible (existing `write_transcript()` continues to work for non-OpenClaw consumers).

---

## API / Interface Contracts

### Enhanced Transcript Conversion

```python
def convert_working_messages_to_openclaw(
    working: list[dict],
    per_message_usage: list[dict[str, int]] | None = None,
) -> list[dict]:
    """Convert TinyCUA BaseLoop working messages to OpenClaw-compatible JSONL.

    The working message list contains:
      - role: "system" (skip — not in OpenClaw format)
      - role: "user" (map to user message records)
      - role: "assistant" with optional tool_calls (map to assistant message records)
      - role: "tool_result" with call_id and content (map to toolResult records)

    ``per_message_usage`` is an optional list of usage dicts (one per assistant
    message), where each dict has keys ``input_tokens``, ``output_tokens``,
    ``total_tokens``.  If provided, each assistant message record receives the
    corresponding usage entry.  If ``None``, all assistant messages receive
    zeroed usage.
    """
```

### Content Block Builder

```python
def _build_content_blocks(
    entry: dict, tool_calls: list[dict] | None = None,
) -> str | list[dict]:
    """Build content field from an assistant message.

    If the entry has tool_calls (OpenAI-style with function.name and
    function.arguments as a JSON string), return a list of content
    blocks (text block + tool_use blocks). Otherwise return plain string content.
    """
```

### Usage Coercion Helper

```python
def _usage_int(value: object) -> int:
    """Coerce a nullable token count to a non-negative int.

    TinyCUA's TokenUsage type permits None for all three token
    fields. WildClawBench's extract_usage_from_jsonl() adds these
    values into integer totals, so a JSON null would cause TypeError.
    """
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
```

### Usage Summary Writer

```python
def write_usage_summary(
    path: Path,
    usage_events: list[dict],
    elapsed_time: float,
) -> None:
    """Aggregate per-response usage events into a usage summary JSON.

    Each usage event has keys: input_tokens, output_tokens, total_tokens.
    Aggregates into the WildClawBench usage.json schema.
    """
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Output directory not writable | `SystemExit(1)` before agent run | Fail fast |
| Usage data unavailable | Zero-filled `usage.json` | Never return `{}` |
| Nullable token count | Coerce to `0` | Never write `null` |
| Agent crash mid-execution | Preserve partial artifacts | Write whatever was collected |

---

## Implementation Phases

### Phase 1 — OpenClaw Transcript Conversion (required)

- [ ] Implement `_usage_int()` helper in `cli/transcript.py`
- [ ] Implement `_build_content_blocks()` for assistant messages with tool calls
- [ ] Implement `convert_working_messages_to_openclaw()` with `per_message_usage` parameter
- [ ] Implement `write_openclaw_jsonl()` for writing converted records to disk
- [ ] Preserve existing `write_transcript()` for backward compatibility

### Phase 2 — Usage Collection (required)

- [ ] Capture `response.usage` events from `TinyCUALoop._run_stream()` into a list
- [ ] Implement `write_usage_summary()` to aggregate and write `usage.json`
- [ ] Wire usage collection into `cli/run.py` after agent execution
- [ ] Support zero-filled fallback when no usage events captured

> **Note**: Usage capture requires running the agent in streaming mode (`stream=True`). The `cli/run.py` will be modified to use `stream=True` and collect `response.usage` events from the async iterator into a list. This is a behavioral change from the current non-streaming mode.

### Phase 3 — CLI Integration (required)

- [ ] Modify `cli/run.py` to use `convert_working_messages_to_openclaw()` for the primary transcript output while preserving `write_transcript()` for backward compatibility
- [ ] Pass `per_message_usage` from captured usage events
- [ ] Write `usage.json` to output directory
- [ ] Ensure `agent.log` continues to work unchanged

### Phase 4 — Tests (required)

- [ ] Unit tests for `_usage_int()` — None, valid int, bool, string
- [ ] Unit tests for `_build_content_blocks()` — no tool calls, with tool calls, empty content
- [ ] Unit tests for `convert_working_messages_to_openclaw()` — user/assistant/tool_result/system messages
- [ ] Unit tests for `write_usage_summary()` — aggregation, zero-filled fallback
- [ ] Integration test: agent run → `transcript.jsonl` → parseable as JSONL
- [ ] Integration test: agent run → `usage.json` with correct fields

---

## Technical Decisions

1. **Decision**: Enhance existing `write_transcript()` with a new `convert_working_messages_to_openclaw()` rather than replacing it.
   - **Reason**: Backward compatibility — existing consumers of the raw format continue to work. The new function is additive.
   - **Alternatives Considered**: Replace `write_transcript()` — rejected because it would break any existing tooling that reads the current format.

2. **Decision**: Use Strategy B (instrument `BaseLoop` working messages) for transcript capture, not Strategy A (stream capture).
   - **Reason**: The working message list already contains properly shaped assistant messages with `tool_calls` and tool-result messages with `call_id`. Strategy A cannot preserve tool results without SDK changes.
   - **Alternatives Considered**: Strategy A (stream capture) — rejected because the SDK doesn't emit `tool_result.completed` events.

3. **Decision**: Capture usage from `response.usage` stream events during `_run_stream()`, not from the SDK's `cumulative_usage`.
   - **Reason**: Per-response granularity — each assistant message gets its own usage entry, which WildClawBench sums correctly.
   - **Alternatives Considered**: Use `cumulative_usage` — rejected because it would embed cumulative totals in every message, causing over-counting.

4. **Decision**: Zero-fill usage when no data is available, never return `{}`.
   - **Reason**: WildClawBench's `save_usage()` immediately indexes required fields — an empty dict causes `KeyError` and crashes the benchmark run.
   - **Alternatives Considered**: Return `{}` with a warning — rejected because it breaks the upstream contract.

5. **Decision**: Keep `agent.log` writing unchanged.
   - **Reason**: It already works correctly and meets the contract. No changes needed.
   - **Alternatives Considered**: Merge `agent.log` into transcript — rejected because they serve different purposes (structured log vs. conversation transcript).

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `response.usage` events not emitted by local model endpoints | Medium | Medium | Zero-fill fallback in `usage.json`; document that local models may not report token counts |
| `tool_calls` format varies by provider | Medium | Low | Normalize via SDK's existing tool-call shape (`function.name`, `function.arguments` as JSON string) |
| Working message list doesn't include all messages needed for transcript | Low | High | Verify with integration tests that all user/assistant/tool_result messages are captured |
| WildClawBench transcript_loader.py rejects our format | Low | High | Test with the actual loader; follow the adapter-contract.md schema exactly |

---

## Open Questions _(optional)_

1. **Should `TranscriptRecord` be used as the primary transcript format or as a side channel for lifecycle events?**
   - **Resolved**: Use it as a side channel. The primary transcript uses the OpenClaw format from `convert_working_messages_to_openclaw()`. `TranscriptRecord` can be used for additional lifecycle event logging if needed.

2. **Should the converter handle `role: "tool_result"` messages that the SDK stores internally but doesn't expose in the working message list?**
   - **Resolved**: Yes — the adapter contract confirms that tool-result messages (role: `tool_result`, call_id: str, content: str) ARE present in the working message list. The converter MUST handle them and produce `toolResult` records with both `callId` and `tool_call_id` fields.

---

## References

- Spec: [./spec.md](./spec.md)
- Adapter contract: `specs/wildclawbench-adapter/adapter-contract.md` — OpenClaw JSONL schema, usage collection, transcript loader behavior
- Existing implementation:
  - `tinycua/cli/transcript.py` — `write_transcript()` (raw format)
  - `tinycua/cli/run.py` — CLI `run` command with output directory
  - `tinycua/cli/logging.py` — `write_log_entry()` (agent.log)
  - `tinycua/config/types.py` — `TranscriptRecord` type
  - `tinycua/loops/tinycua_loop.py` — `_run_stream()` streaming, `_run_sync()` non-streaming
- Design docs:
  - `src/tinycua/docs/design/loops/base_loop.md` — streaming architecture
  - `src/tinycua/docs/design/loops/tinycua_loop.md` — loop execution
