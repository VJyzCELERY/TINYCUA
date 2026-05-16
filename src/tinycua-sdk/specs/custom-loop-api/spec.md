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
- Import and use truly generic, atomic primitives that accept raw data (dicts, lists, callables) instead of being coupled to `BaseLoop` or `Agent` internals — making them reusable in any loop context
- Read and understand both `_run_sync()` and `_run_stream()` at a glance because they are thin orchestrators over the same composable building blocks

### Gaps

1. **Both loop paths are too complex.** `_run_sync()` is ~90 lines of interleaved logic (tool iteration, permission checking buried inside `ToolExecutor.execute()`, message building). `_run_stream()` is ~130 lines plus ~120 more across helper methods. Neither can be understood at a glance.

2. **Permission and approval logic is hidden inside `ToolExecutor.execute()`.** A custom loop author who wants different permission behavior (e.g., logging denials, custom approval UI) cannot replace just that piece — they must either fork `ToolExecutor` or reimplement the entire tool calling block.

3. **No standalone primitives for tool call handling.** JSON argument parsing, tool lookup, permission checking, approval workflows, result formatting — all are either in `ToolExecutor` or inline in the loop methods. None are importable standalone.

4. **Existing stream primitives are coupled to BaseLoop internals.** Even the static helper methods (`_read_stream_chunk`, `_iter_llm_events`, `_accumulate_chunk`) are private and undocumented. They take `BaseLoop`-specific types like `_IterStreamState` and cannot be used by external code.

5. **Stream and sync paths share no code.** Despite both doing the same core work (call LLM → process tools → call LLM again), `_run_sync()` and `_run_stream()` have independent implementations of tool execution, message appending, and iteration control.

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

### Primary Scenario: Custom Sync Loop with Custom Permission Logic

A developer wants to write a ReAct loop that logs denied tool calls to a database. Every primitive accepts raw data, so the developer doesn't need access to any internal object:

```python
class LoggingReActLoop(BaseLoop):
    async def run(self, agent, messages, tools, ...):
        system_msg = build_system_message(agent.instructions, agent.skills)
        working = [system_msg] + messages

        for _ in range(self.max_iterations):
            response = await call_llm(agent, working, tools)

            if not has_tool_calls(response):
                return get_content(response)

            for tc in get_tool_calls(response):
                permission = check_tool_permission(
                    tc["name"], agent.tool_permissions
                )
                if permission == "deny":
                    await log_denial_to_db(tc["name"])
                    append_tool_error(working, tc, "denied by policy")
                    continue
                if permission == "ask":
                    approval = await request_tool_approval(
                        tc["name"], tc["arguments"],
                        agent.approval_workflow,
                    )
                    if not approval.get("approved"):
                        append_tool_error(working, tc, approval)
                        continue

                result = await invoke_tool(tc, tools)
                append_tool_result(working, tc, result)

        return last_assistant_content(working)
```

Note that `check_tool_permission()` takes a permissions dict, not an agent. `request_tool_approval()` takes a workflow list, not an agent. `invoke_tool()` is a pure execution primitive with no permission logic. Every function is usable in any context — not just `BaseLoop`.

### Primary Scenario: Custom Streaming Loop

A developer wants streaming with a custom progress callback. The stream primitive accepts a cancel event instead of an agent:

```python
class StreamingLogLoop(BaseLoop):
    async def run(self, agent, messages, tools, ...):
        ...
        llm_stream = await call_llm_stream(agent, working, tools)
        async for event in iterate_stream_events(
            llm_stream, agent._cancel_event,
            content_parts, tool_calls_buffer,
            cumulative_usage, usage_settled_ids,
        ):
            if event["type"] == "response.output_text.delta":
                await progress_callback(event["delta"])
            yield event
        ...
```

### Acceptance Scenarios

1. **Given** a developer writes a custom loop using only the generic public helpers (`call_llm`, `check_tool_permission`, `request_tool_approval`, `invoke_tool`, `append_tool_result`, etc.), **When** the loop runs with valid inputs, **Then** it correctly handles tool calls, permission denials, approval workflows, and streaming lifecycle — without calling any private method.

2. **Given** the existing `test_loop.py` and `test_loop_custom.py` test suites, **When** the refactored `BaseLoop` runs against all tests, **Then** every test passes with zero modifications.

3. **Given** a developer replaces `check_tool_permission()` with a custom implementation, **When** a denied tool is invoked, **Then** the custom permission logic runs instead of the default.

4. **Given** a developer uses `invoke_tool()` directly without any permission or approval wrapping, **When** they call it with a valid tool and arguments, **Then** the tool executes and returns the raw result.

### Edge Cases

- Tool call with unparseable JSON arguments → `parse_tool_arguments()` returns `(None, error_msg)`
- Tool call for unknown tool name → `lookup_tool()` returns `None`
- Permission "deny" → error message appended, no execution, loop continues
- Permission "ask" with no `approval_workflow` configured → returns `{"approved": False, "error": "..."}`
- Empty LLM response (no content, no tool calls) → loop terminates gracefully
- Cancellation during tool execution → partial results discarded, loop exits

---

## Requirements

### Functional Requirements

**LLM and system message primitives:**

- **FR-001**: The SDK MUST expose a standalone `call_llm()` function that calls the LLM with messages and tools, returning a normalized response dict (sync mode).
- **FR-002**: The SDK MUST expose a standalone `call_llm_stream()` function that calls the LLM with messages and tools, returning an async iterator of SSE events (stream mode).
- **FR-003**: The SDK MUST expose a standalone `build_system_message()` function that builds a system message from instructions and skills.

**Atomic tool-handling primitives:**

- **FR-004**: The SDK MUST expose a standalone `parse_tool_arguments()` function that parses JSON arguments from a tool call dict, returning `(parsed_dict, None)` on success or `(None, error_message)` on failure. This is a pure function with no side effects.
- **FR-005**: The SDK MUST expose a standalone `lookup_tool()` function that finds a tool by name from a list of tools, returning the `Tool` instance or `None`.
- **FR-006**: The SDK MUST expose a standalone `check_tool_permission()` function that checks a tool name against a permissions dict and returns `"allow"`, `"ask"`, or `"deny"`. It MUST accept a plain dict, not an Agent instance.
- **FR-007**: The SDK MUST expose a standalone `request_tool_approval()` function that runs one or more `ApprovalWorkflow` instances for a tool call and returns the approval decision. It MUST accept a list of `ApprovalWorkflow` objects, not an Agent instance.
- **FR-008**: The SDK MUST expose a standalone `invoke_tool()` function that executes a single tool with parsed arguments and returns the raw result. It MUST accept a `Tool` instance and a dict of arguments. It MUST NOT include permission checks, approval, or message building — it is the pure execution step.

**Convenience composition:**

- **FR-009**: The SDK MUST expose a standalone `execute_tool_call()` convenience function that composes `parse_tool_arguments` → `lookup_tool` → `check_tool_permission` → `request_tool_approval` → `invoke_tool` for a single tool call. It MUST accept raw data (tools list, permissions dict, workflows list) rather than an Agent.

**Message building primitives:**

- **FR-010**: The SDK MUST expose standalone `build_function_call_message()` and `build_function_call_output_message()` functions for constructing message dicts in the correct format.
- **FR-011**: The SDK MUST expose a standalone `append_tool_result()` convenience function that appends both function_call and function_call_output messages to a message list.

**Response inspection and utility primitives:**

- **FR-012**: The SDK MUST expose `has_tool_calls()`, `get_tool_calls()`, `get_content()`, and `last_assistant_content()` for inspecting LLM responses and message lists.

**Stream processing primitives:**

- **FR-013**: The SDK MUST expose standalone `read_stream_chunk()` and `iter_llm_events()` functions for reading from LLM stream iterators with cancellation support. These MUST accept an `asyncio.Event` for cancellation, not an Agent.
- **FR-014**: The SDK MUST expose a standalone `iterate_stream_events()` async generator that processes a full LLM stream iteration, yielding lifecycle events and accumulating content/tool calls/usage. It MUST accept an `asyncio.Event` for cancellation, not an Agent.
- **FR-015**: The SDK MUST expose standalone `accumulate_chunk()`, `accumulate_tool_chunk()`, and `accumulate_usage()` functions for accumulating stream data into mutable containers.

**Refactoring of BaseLoop:**

- **FR-016**: `BaseLoop._run_sync()` MUST be refactored to use the standalone primitives, with its body reduced to a clear orchestration layer (~30–40 lines).
- **FR-017**: `BaseLoop._run_stream()` MUST be refactored to use the standalone primitives, with its body reduced to a clear orchestration layer (~40–60 lines).
- **FR-018**: All standalone primitives MUST be tested independently with unit tests.

**Backward compatibility:**

- **FR-019**: All existing tests MUST pass without modification.
- **FR-020**: Custom loops written against the current `BaseLoop` subclassing contract MUST continue to work.

### Key Entities

- **LLM Primitives**: `call_llm()`, `call_llm_stream()` — communicate with the LLM provider via the agent's client and model config.
- **Atomic Tool Primitives**: `parse_tool_arguments()`, `lookup_tool()`, `check_tool_permission()` (takes a dict), `request_tool_approval()` (takes a workflow list), `invoke_tool()` (pure execution, no side effects) — each does exactly one thing with no hidden dependencies.
- **Convenience Composition**: `execute_tool_call()` — composes the atomic primitives for a single tool call, accepting raw data.
- **Message Primitives**: `build_function_call_message()`, `build_function_call_output_message()`, `append_tool_result()` — construct messages in the SDK's standard format.
- **Stream Primitives**: `read_stream_chunk()`, `iter_llm_events()`, `iterate_stream_events()`, `accumulate_chunk()`, `accumulate_tool_chunk()`, `accumulate_usage()` — process LLM streaming responses, all accepting an `asyncio.Event` for cancellation.
- **Inspection Primitives**: `has_tool_calls()`, `get_tool_calls()`, `get_content()`, `last_assistant_content()` — extract data from LLM responses and message lists.

---

## Success Criteria

- [ ] **Custom sync loop in 25 lines**: A developer can write a fully functional ReAct loop (including atomic permission check, approval, tool invocation, and message building) in ~25 lines of `run()` implementation using only public primitives
- [ ] **Custom streaming loop in 20 lines**: A developer can write a streaming loop (including lifecycle events) in ~20 lines using public primitives
- [ ] **`_run_sync()` readability**: The refactored `_run_sync()` body is ≤40 lines and uses only public primitive calls
- [ ] **`_run_stream()` readability**: The refactored `_run_stream()` body is ≤60 lines and uses only public primitive calls
- [ ] **Primitives are truly generic**: Every primitive accepts raw data types (dict, list, Tool, asyncio.Event) — not Agent or BaseLoop instances — except where the Agent is the natural abstraction (LLM calls)
- [ ] **`invoke_tool()` is pure execution**: A developer can call `invoke_tool(tool, args)` without any permission or approval logic running
- [ ] **Permission is replaceable**: A developer can replace `check_tool_permission()` with their own implementation — it just takes a tool name and a dict
- [ ] **Approval is replaceable**: A developer can replace `request_tool_approval()` with their own implementation — it just takes tool data and a workflow list
- [ ] **All existing tests pass**: `test_loop.py`, `test_loop_custom.py`, `test_agent_run.py`, `test_agent_streaming.py`, and integration tests pass with zero modifications

---

## Testing Plan

### Unit Tests

- New test module `test_loop_primitives.py` covering each standalone primitive:
  - `call_llm()` — returns dict, handles errors
  - `build_system_message()` — instructions only, skills only, both, empty
  - `parse_tool_arguments()` — valid JSON, invalid JSON, empty string
  - `lookup_tool()` — found, not found, empty list
  - `check_tool_permission()` — allow, ask, deny, missing, invalid value
  - `request_tool_approval()` — approved, denied, no workflows, multiple workflows
  - `invoke_tool()` — success, exception
  - `execute_tool_call()` (convenience) — full pipeline, parse error, unknown tool, denied
  - `build_function_call_message()` / `build_function_call_output_message()` — correct format
  - `has_tool_calls()` / `get_tool_calls()` / `get_content()` — has calls, no calls, empty
  - `last_assistant_content()` — various message orderings
  - `read_stream_chunk()` — normal chunk, cancellation, exhausted stream
  - `iter_llm_events()` — multi-chunk, stream aclose, cancellation
  - `iterate_stream_events()` — empty stream, first-chunk completed/failed/error, normal flow, cancellation
- Existing test suites: `test_loop.py`, `test_loop_custom.py` must pass unchanged

### Integration Tests

- Existing integration tests (`test_agent_streaming.py`, `test_custom_agent_loop.py`, `test_tool_loading.py`, `test_permission_system.py`, `test_guardrail_system.py`) must pass without modification

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Spec | Revised | Expanded to cover sync path, generic primitives accepting raw data |

---

## Open Questions

None at this time.
