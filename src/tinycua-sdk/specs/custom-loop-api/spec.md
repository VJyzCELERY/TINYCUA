# Feature Specification: Custom Loop Creation API Simplification

**Status**: Draft
**Created**: 2026-05-16
**Last Updated**: 2026-05-16
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

### Goals

Provide a simple, composable API for creating custom agent execution loops so that SDK users can:

- Write a custom loop (sync or streaming, ReAct-style, PlanThenExecute, or any other pattern) as a straightforward while loop with clear dispatch logic — ideally 20–30 lines
- Replace or customize individual steps of the loop (permission checks, approval workflows, tool execution, message building) without forking the entire loop implementation
- Import and use atomic, standalone primitives (`call_llm`, `check_permission`, `request_approval`, `execute_tool`, `build_tool_messages`, etc.) without subclassing `BaseLoop`
- Read and understand both `_run_sync()` and `_run_stream()` at a glance because they are thin orchestrators over the same composable building blocks

### Gaps

1. **Both loop paths are too complex.** `_run_sync()` is ~90 lines of interleaved logic (tool iteration, permission checking buried inside `ToolExecutor.execute()`, message building). `_run_stream()` is ~130 lines plus ~120 more across helper methods. Neither can be understood at a glance.

2. **Permission and approval logic is hidden inside `ToolExecutor.execute()`.** A custom loop author who wants different permission behavior (e.g., logging denials, custom approval UI) cannot replace just that piece — they must either fork `ToolExecutor` or reimplement the entire tool calling block.

3. **No standalone primitives for tool call handling.** JSON argument parsing, tool lookup, permission checking, approval workflows, result formatting — all are either in `ToolExecutor` or inline in the loop methods. None are importable standalone.

4. **Stream and sync paths share no code.** Despite both doing the same core work (call LLM → process tools → call LLM again), `_run_sync()` and `_run_stream()` have independent implementations of tool execution, message appending, and iteration control.

### Non-Goals

- Changing the runtime behavior of `BaseLoop.run()` or `Agent.run()` — existing callers must see zero difference
- Building a full visual workflow/state-machine editor
- Removing `BaseLoop` as a class — it remains the default loop, just refactored internally
- Performance optimization — this is purely a readability/composability improvement

### Constraints

- Backward compatibility: all existing unit/integration tests must pass without modification
- `ToolExecutor.execute()` must continue to work (existing custom loops may use it)
- `Agent` class API unchanged — `agent.run()`, `agent._call_llm()`, `agent.cancel()` all keep their signatures
- Must work with Python 3.11+

---

## User Scenarios & Testing

### Primary Scenario: Custom Sync Loop

A developer wants to write a custom ReAct loop with custom permission logging:

```python
class LoggingReActLoop(BaseLoop):
    async def run(self, agent, messages, tools, ...):
        system_msg = build_system_message(agent)
        working = [system_msg] + messages

        for _ in range(self.max_iterations):
            response = await call_llm(agent, working, tools)

            if not has_tool_calls(response):
                return get_content(response)

            for tc in get_tool_calls(response):
                permission = check_tool_permission(tc["name"], agent)
                if permission == "deny":
                    log_denial(tc["name"])
                    append_tool_error(working, tc, "denied")
                    continue
                if permission == "ask":
                    approval = await request_tool_approval(tc, agent)
                    if not approval:
                        append_tool_error(working, tc, "not approved")
                        continue

                result = await execute_tool(tc, tools, agent)
                append_tool_result(working, tc, result)

        return last_assistant_content(working)
```

Every step (`check_tool_permission`, `request_tool_approval`, `execute_tool`, `append_tool_result`) is a standalone public function the developer can override or replace.

### Primary Scenario: Custom Streaming Loop

A developer wants streaming with a custom progress callback:

```python
class StreamingLogLoop(BaseLoop):
    async def run(self, agent, messages, tools, ...):
        ...
        llm_stream = await call_llm_stream(agent, working, tools)
        async for event in iterate_stream_events(llm_stream, ...):
            if event["type"] == "response.output_text.delta":
                await progress_callback(event["delta"])
            yield event
        ...
```

### Acceptance Scenarios

1. **Given** a developer writes a custom loop using only the atomic public helpers (`call_llm`, `check_tool_permission`, `request_tool_approval`, `execute_tool`, `build_tool_messages`, etc.), **When** the loop runs with valid inputs, **Then** it correctly handles tool calls, permission denials, approval workflows, and streaming lifecycle.

2. **Given** the existing `test_loop.py` and `test_loop_custom.py` test suites, **When** the refactored `BaseLoop` runs against all tests, **Then** every test passes with zero modifications.

3. **Given** the existing `test_agent_run.py` and `test_agent_streaming.py` test suites, **When** `Agent.run()` is called (sync and stream mode), **Then** all tests pass with zero modifications.

4. **Given** a developer replaces `check_tool_permission` with a custom implementation, **When** a denied tool is invoked, **Then** the custom permission logic runs instead of the default.

### Edge Cases

- Tool call with unparseable JSON arguments → error message appended, loop continues
- Tool call for unknown tool name → error message appended, loop continues
- Permission "deny" → error message appended, no execution, loop continues
- Permission "ask" with no `approval_workflow` configured → error message appended
- All tool calls in a single LLM response denied → no content produced, loop continues or terminates based on policy
- Empty LLM response (no content, no tool calls) → loop terminates gracefully
- Cancellation during tool execution → partial results discarded, loop exits

---

## Requirements

### Functional Requirements

**Core loop structure:**

- **FR-001**: The SDK MUST expose a standalone `call_llm()` function that calls the LLM with messages and tools, returning a normalized response dict (sync mode).
- **FR-002**: The SDK MUST expose a standalone `call_llm_stream()` function that calls the LLM with messages and tools, returning an async iterator of SSE events (stream mode).
- **FR-003**: The SDK MUST expose a standalone `build_system_message()` function that builds a system message from agent instructions and skills.

**Tool handling primitives:**

- **FR-004**: The SDK MUST expose a standalone `check_tool_permission()` function that checks a tool name against the agent's permission map and returns `"allow"`, `"ask"`, or `"deny"`.
- **FR-005**: The SDK MUST expose a standalone `request_tool_approval()` function that runs the agent's `ApprovalWorkflow` for a tool call and returns the approval decision.
- **FR-006**: The SDK MUST expose a standalone `execute_tool_call()` function that, given a single tool call dict, parses arguments, looks up the tool, checks permission, requests approval (if needed), and executes via `ToolExecutor`.
- **FR-007**: The SDK MUST expose standalone functions for building tool call messages: `build_function_call_message()` and `build_function_call_output_message()`.

**Utility primitives:**

- **FR-008**: The SDK MUST expose `has_tool_calls()` and `get_tool_calls()` helpers for inspecting LLM responses.
- **FR-009**: The SDK MUST expose `last_assistant_content()` for extracting the last assistant message from a message list.

**Refactoring of BaseLoop:**

- **FR-010**: `BaseLoop._run_sync()` MUST be refactored to use the standalone primitives, with its body reduced to a clear orchestration layer (~30–40 lines).
- **FR-011**: `BaseLoop._run_stream()` MUST be refactored to use the standalone primitives, with its body reduced to a clear orchestration layer (~40–60 lines).
- **FR-012**: All standalone primitives MUST be tested independently with unit tests.

**Backward compatibility:**

- **FR-013**: All existing tests MUST pass without modification.
- **FR-014**: Custom loops written against the current `BaseLoop` subclassing contract MUST continue to work.

### Key Entities

- **LLM Primitives**: `call_llm()`, `call_llm_stream()` — communicate with the language model provider.
- **Permission & Approval Primitives**: `check_tool_permission()`, `request_tool_approval()` — decouple access control from execution.
- **Tool Execution Primitives**: `execute_tool_call()` — orchestrate permission check → approval → execution for a single tool call.
- **Message Building Primitives**: `build_system_message()`, `build_function_call_message()`, `build_function_call_output_message()` — construct message dicts in the correct format.
- **Response Inspection Primitives**: `has_tool_calls()`, `get_tool_calls()`, `get_content()`, `last_assistant_content()` — extract information from LLM responses and message lists.
- **Stream Processing Primitives**: `iterate_stream_events()` — process an LLM streaming response, yielding lifecycle events and accumulating content, tool calls, and usage.

---

## Success Criteria

- [ ] **Custom sync loop in 25 lines**: A developer can write a fully functional ReAct loop (including permission checks, approval, tool execution) in ~25 lines of `run()` implementation using only public primitives
- [ ] **Custom streaming loop in 20 lines**: A developer can write a streaming loop (including lifecycle events) in ~20 lines using public primitives
- [ ] **`_run_sync()` readability**: The refactored `_run_sync()` body is ≤40 lines and uses only public primitive calls
- [ ] **`_run_stream()` readability**: The refactored `_run_stream()` body is ≤60 lines and uses only public primitive calls
- [ ] **Permission is replaceable**: A developer can replace `check_tool_permission()` with their own implementation without forking any other code
- [ ] **Approval is replaceable**: A developer can replace `request_tool_approval()` with their own implementation without forking any other code
- [ ] **All existing tests pass**: `test_loop.py`, `test_loop_custom.py`, `test_agent_run.py`, `test_agent_streaming.py`, and integration tests pass with zero modifications
- [ ] **Standalone primitive tests**: Each primitive has dedicated unit tests with at least 3 scenarios (happy path + 2 edge cases)

---

## Testing Plan

### Unit Tests

- New test module `test_loop_primitives.py` covering each standalone primitive:
  - `call_llm()` — returns dict, handles errors
  - `build_system_message()` — instructions, override, skills, empty
  - `check_tool_permission()` — allow, ask, deny, missing, invalid
  - `request_tool_approval()` — approved, denied, no workflow configured
  - `execute_tool_call()` — success, unknown tool, JSON parse error, cancelled
  - `build_function_call_message()` / `build_function_call_output_message()` — correct format
  - `has_tool_calls()` / `get_tool_calls()` — has calls, no calls, empty list
  - `last_assistant_content()` — various message orderings
- Existing `test_loop.py` and `test_loop_custom.py` must still pass

### Integration Tests

- Existing integration tests (`test_agent_streaming.py`, `test_custom_agent_loop.py`, `test_tool_loading.py`, `test_permission_system.py`, `test_guardrail_system.py`) must pass without modification

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Spec | Revised | Expanded from stream-only to full loop; added atomic primitives |

---

## Open Questions

None at this time.
