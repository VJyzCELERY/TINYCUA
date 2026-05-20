# Design Document: Agent Loop Integration

**Spec**: `specs/tinycua-sdk/stage-4-agent-loop-integration/spec.md`
**Status**: Complete
**Last Updated**: 2026-05-20

---

## Overview

This stage integrates canonical SSE events into the internal agent loop and exposes `BaseLoop` as a public, subclassable class for custom loop patterns. The key architectural decision is that `BaseLoop` handles all canonical event accumulation internally while exposing helper methods so custom subclasses can reuse tool call processing, system message building, and stream iteration without duplicating logic.

---

## Architecture

### Component Overview

```
Agent.run()
  └─ BaseLoop.run()
       ├─ _run_sync() ── LLMResponse ── process_tool_calls() ── tool_result messages
       └─ _run_stream() ── AsyncIterator[LLMEvent] ── process_stream_iteration()
              ├─ _process_first_chunk()
              ├─ _process_stream_body()
              │    └─ _accumulate_chunk() → content_parts + tool_calls_buffer
              └─ _finalize_stream_iteration()
                   ├─ process_stream_tool_calls() → tool_result messages
                   └─ breaks or continues loop
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `agent/loop.py` | Modified | Added `process_stream_iteration`, `process_stream_tool_calls`, `_finalize_stream_iteration`, `_get_llm_stream`, `_handle_stream_exception`, public helpers |
| `agent/__init__.py` | Modified | Export `BaseLoop` |
| `agent/agent.py` | Modified | Accept `loop: BaseLoop | None` parameter |
| `agent/config.py` | Modified | Add `loop` field to `AgentConfig` |
| `tests/unit/test_loop.py` | New | Unit tests for loop internals |
| `tests/unit/test_loop_custom.py` | New | Contract tests for custom loop subclassing |
| `tests/integration/test_custom_agent_loop.py` | New | Integration tests with real LLM transport |

---

## Data Model

No new entities. The `tool_calls_buffer` is an internal runtime dict:

```python
{
    "call_id": {
        "id": str,
        "call_id": str,
        "name": str,
        "arguments": str,
        "_ready": bool,  # gates execution
    }
}
```

---

## API / Interface Contracts

### `BaseLoop` (public, subclassable)

```python
class BaseLoop:
    def __init__(self, max_iterations: int = 5) -> None

    async def run(
        self, agent: Agent, messages: list[dict], tools: list[Tool],
        override_instructions: str | None = None, stream: bool = False,
    ) -> str | AsyncIterator[dict[str, Any]]
```

### Public Helper Methods (for custom subclasses)

```python
def build_system_message(self, agent: Agent, override_instructions: str | None = None) -> dict[str, str]

async def process_tool_calls(
    self, agent: Agent, tools: list[Tool], tool_calls: list[dict[str, Any]],
    working_messages: list[dict[str, Any]], tool_call_count: int,
    assistant_content: str = "",
) -> tuple[int, bool]

async def process_stream_tool_calls(
    self, agent: Agent, tools: list[Tool], tool_calls_list: list[dict[str, Any]],
    working_messages: list[dict], tool_call_count: int,
    combined_content: str = "",
) -> tuple[int, bool]

async def process_stream_iteration(
    self, llm_stream: AsyncIterator[dict[str, Any]], agent: Agent,
    content_parts: list[str], tool_calls_buffer: dict[str, dict[str, Any]],
    cumulative_usage: dict[str, int], usage_settled_ids: set[str],
) -> AsyncIterator[dict[str, Any]]

def last_assistant_content(messages: list[dict]) -> str
```

### Streaming Return Contract

The stream yields SDK-normalized event dicts with `type` field. Lifecycle events (`response.created`, `response.in_progress`, `response.completed`, `response.failed`, `response.cancelled`) plus data events (`response.output_text.delta`, `response.usage`, tool call events). Cancellation emits `response.cancelled`.

### Error Handling

| Error Case | Behavior | Notes |
|-----------|----------|-------|
| Tool call JSON parse failure | `tool_result` with `error` message, continues | |
| Unknown tool name | `tool_result` with `error: Unknown tool`, continues | |
| Tool execution exception | `tool_result` with `error: Tool execution failed`, continues | |
| LLM stream exception | Yields `response.failed` + `error` events | |
| `asyncio.CancelledError` | Yields `response.cancelled` event | Observed before each tool and chunk read |
| `max_tool_calls` reached | Emits `response.completed` with `finish_reason: max_tool_calls`, breaks loop | |
| `max_iterations` reached | Emits `response.completed` with `finish_reason: max_iterations` | |

---

## Implementation Phases

### Phase 1 — MVP

- [x] Implement `BaseLoop._run_stream()` with tool call buffering and execution
- [x] Implement `process_stream_iteration()`, `_process_first_chunk()`, `_process_stream_body()`
- [x] Implement `_accumulate_chunk()` dispatching to content/tool/usage accumulators
- [x] Implement `_finalize_stream_iteration()` with tool call processing and loop control
- [x] Implement `_get_llm_stream()` with type validation
- [x] Implement `_handle_stream_exception()` for lifecycle events on error
- [x] Implement `_read_stream_chunk()` with concurrent cancellation
- [x] Implement `_iter_llm_events()` stream wrapper
- [x] Make all helper methods public on `BaseLoop`
- [x] Expose `BaseLoop` in `tinycua_sdk.agent` and `tinycua_sdk` package
- [x] Write unit tests (`test_loop.py`, `test_loop_custom.py`)
- [x] Write integration tests (`test_custom_agent_loop.py`)

### Phase 2 — Enhancements

- [ ] (Future) `_call_llm(llm_model=...)` per-call model override support in all loops

---

## Technical Decisions

1. **Decision**: Use `_ready` gating on tool call buffer entries rather than executing immediately.
   - **Reason**: Canonical events arrive incrementally (`started` → `delta*` → `done` → `ready`). The `_ready` flag ensures tools are only executed after all arguments are received.
   - **Alternatives Considered**: Execute on `function_call_arguments.done` — rejected because it would break when `tool_call.ready` is emitted separately.

2. **Decision**: Suppress intermediate `response.completed` with `finish_reason: tool_calls` during streaming.
   - **Reason**: Consumers see one terminal `response.completed` for the entire `Agent.run(stream=True)` call rather than one per tool-calling iteration.
   - **Alternatives Considered**: Pass through — rejected because it would confuse consumers expecting a single completion event.

3. **Decision**: Make helper methods public on `BaseLoop` rather than as standalone functions.
   - **Reason**: Custom loop subclasses inherit them naturally and can call `self.process_tool_calls(...)` without additional imports.
   - **Alternatives Considered**: Standalone functions in `loop.py` — rejected because they would need `self` access for future extension.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Custom loops miss cancellation checks | Low | Medium | Document `agent.is_cancelled` contract, existing loops check before each tool call |
| Tool call argument accumulation out of order | Low | High | State machine with `_ready` flag ensures only complete tool calls are executed |
| Breaking backward compatibility for existing `Agent.run()` callers | Low | High | `Agent.run()` signature unchanged, `BaseLoop` is backward-compatible default |

---

## References

- Spec: `specs/tinycua-sdk/stage-4-agent-loop-integration/spec.md`
- Source: `src/tinycua-sdk/tinycua_sdk/agent/loop.py`
- Unit tests: `src/tinycua-sdk/tests/unit/test_loop.py`, `test_loop_custom.py`
- Integration tests: `src/tinycua-sdk/tests/integration/test_custom_agent_loop.py`
