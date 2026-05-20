# Feature Specification: Agent Loop Integration

**Status**: Complete
**Created**: 2026-05-20
**Last Updated**: 2026-05-20
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

- **Goals**: Enable the agent loop to consume canonical SSE events for tool use, and provide a subclassable `BaseLoop` for custom loop patterns (ReAct, PlanThenExecute, etc.).
- **Gaps**: Before this stage, the agent loop had no streaming tool call support and no public extension points for custom execution strategies.
- **Non-Goals**: Adding new provider integrations, changing the canonical event schema, or modifying the `LLMClient` ABC.
- **Constraints**: Maintain backward compatibility with existing `Agent.run()` interface. All public helper methods must be accessible to custom loop subclasses.

---

## User Scenarios & Testing

### Primary Scenario

A developer creates an agent using `BaseLoop` for standard tool-calling execution. The agent sends a query, the LLM responds with tool calls via canonical events, the loop buffers and executes them, and returns the final answer.

### Acceptance Scenarios

1. **Given** a streaming agent with tools, **When** the LLM emits `ToolCallStartedEvent` → `ToolCallArgumentsDeltaEvent*` → `ToolCallArgumentsDoneEvent` → `ToolCallReadyEvent`, **Then** the loop buffers the tool call and executes it when `_ready` is set.
2. **Given** a custom loop subclassing `BaseLoop`, **When** it overrides `run()` and calls `agent._call_llm()`, **Then** it receives properly-formatted `LLMResponse` dicts.
3. **Given** a custom loop, **When** it calls `process_tool_calls()`, **Then** tool results are appended as `tool_result` messages.

### Edge Cases

- What happens when tool call arguments are invalid JSON?
- How does the system handle a stream that ends with `response.failed`?
- What is the behavior when `agent.cancel()` is called mid-iteration?
- How are tool calls with `_ready=False` handled (not yet complete)?

---

## Requirements

### Functional Requirements

- **FR-001**: `BaseLoop` MUST consume canonical tool call events (`ToolCallStartedEvent`, `ToolCallArgumentsDeltaEvent`, `ToolCallArgumentsDoneEvent`, `ToolCallReadyEvent`) from the LLM stream.
- **FR-002**: `BaseLoop` MUST buffer and accumulate tool call data during streaming, and only execute tool calls when marked `_ready`.
- **FR-003**: `BaseLoop` MUST expose public helper methods (`build_system_message`, `process_tool_calls`, `process_stream_tool_calls`, `process_stream_iteration`, `last_assistant_content`) for custom loop subclasses.
- **FR-004**: Custom loops MUST be able to override `BaseLoop.run()` and call `agent._call_llm()` directly.
- **FR-005**: Custom loops MUST be able to observe `agent.is_cancelled` and exit cooperatively.
- **FR-006**: Custom loops MUST inherit `max_iterations` from `BaseLoop`.
- **FR-007**: The non-streaming execution path MUST process `tool_calls` from `LLMResponse` dicts and append `tool_result` messages.
- **FR-008**: The streaming execution path MUST yield lifecycle events (`response.created`, `response.in_progress`, `response.output_text.delta`, `response.usage`, `response.completed`) in correct order.
- **FR-009**: Streaming tool calls MUST yield intermediate `response.completed` with `finish_reason: tool_calls` suppressed — consumers see one terminal `response.completed` for the entire `Agent.run(stream=True)` call.

---

## Success Criteria

- [x] `BaseLoop` processes tool calls from both streaming and non-streaming LLM responses
- [x] Custom loop subclasses can override `run()` and call all public helpers
- [x] Cancellation is observed promptly before each tool call and before each stream chunk read
- [x] All unit and integration tests for loops pass (`test_loop.py`, `test_loop_custom.py`, `test_custom_agent_loop.py`)

Note: Live LLM integration cases in `test_custom_agent_loop.py` are marked
`integration` and auto-skip when no compatible local LLM endpoint is reachable.

---

## Testing Plan

### Unit Tests

- `test_loop.py`: Tests for `BaseLoop._run_sync`, `_run_stream`, `_accumulate_chunk`, `_finalize_stream_iteration`, `process_stream_iteration`, cancellation, tool call buffering.
- `test_loop_custom.py`: Contract tests for `BaseLoop` subclassing — ReAct, PlanThenExecute, streaming lifecycle, all public helpers.

### Integration Tests

- `test_custom_agent_loop.py`: Real LLM transport tests for custom loops, streaming lifecycle, tool calling with public helpers.
