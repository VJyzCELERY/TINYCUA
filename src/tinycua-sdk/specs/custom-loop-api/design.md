# Design Document: Custom Loop Creation API Simplification

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-05-16

---

## Overview

Refactor `tinycua_sdk/agent/loop.py` to decompose both `_run_sync()` and `_run_stream()` into atomic, standalone, public helper functions that accept **raw data types** (dicts, lists, Tools, asyncio.Event) rather than Agent or BaseLoop instances. The goal is to create a toolkit of generic primitives usable in any loop context, not just inside BaseLoop.

`BaseLoop` becomes a thin orchestration layer that delegates to these primitives. Custom loop authors import only the primitives they need and compose them however they like.

### Design Principles

1. **Atomicity**: Each primitive does exactly one thing. `invoke_tool()` only invokes a tool. `check_tool_permission()` only checks a permissions dict. No hidden steps.
2. **Raw data interfaces**: Primitives accept plain Python types (dict, list, Tool, asyncio.Event) rather than framework objects (Agent, BaseLoop). The only exception is `call_llm()` / `call_llm_stream()` which naturally need the Agent for LLM client access.
3. **Composability**: `execute_tool_call()` is a convenience composition of the atomic primitives. Users who want different behavior use the atomic pieces directly.
4. **Backward compatibility**: `ToolExecutor.execute()` and all existing tests work without changes.

---

## Architecture

### Execution Model

Both sync and streaming loops follow the same conceptual model:

```
while iter < max_iterations:
    response = call_llm(agent, messages, tools)

    if has_tool_calls(response):
        for tc in get_tool_calls(response):
            atomic steps                   ← each is replaceable independently
            ├── parse_tool_arguments(tc)
            ├── lookup_tool(tc["name"], tools)
            ├── check_tool_permission(tc["name"], agent.tool_permissions)  ← takes dict
            ├── request_tool_approval(tc, agent.approval_workflow)         ← takes list
            └── invoke_tool(tool, parsed_args)                             ← pure execution
            then
            └── append_tool_result(messages, tc, result)
    else:
        return get_content(response)
```

### Component Diagram

```
  loop.py (public API)
  ─────────────────────────────────────────────────────────────────────
  
  LLM Primitives (take Agent — natural abstraction for model access)
  ├── call_llm(agent, messages, tools)
  ├── call_llm_stream(agent, messages, tools)
  └── build_system_message(instructions, skills)    ← pure, takes raw strings
  
  Atomic Tool Primitives (take raw data — no Agent dependency)
  ├── parse_tool_arguments(tc)                    → (dict|None, str|None)
  ├── lookup_tool(tool_name, tools)               → Tool | None
  ├── check_tool_permission(name, permissions)    → "allow"|"ask"|"deny"
  ├── request_tool_approval(name, args, workflows) → dict (approval result)
  └── invoke_tool(tool, arguments)                 → Any (raw result)
  
  Convenience Composition
  └── execute_tool_call(tc, tools, permissions, workflows)
      → composes parse → lookup → check → approve → invoke
  
  Message Primitives (pure, take raw data)
  ├── build_function_call_message(tc)
  ├── build_function_call_output_message(tc, output)
  └── append_tool_result(messages, tc, result)
  
  Stream Primitives (take asyncio.Event — not Agent)
  ├── read_stream_chunk(llm_stream, cancel_event)
  ├── iter_llm_events(llm_stream, cancel_event)
  ├── iterate_stream_events(llm_stream, cancel_event, ...)
  ├── accumulate_chunk(chunk, ...)
  ├── accumulate_tool_chunk(chunk, ...)
  └── accumulate_usage(cumulative, usage)
  
  Inspection Primitives (pure functions)
  ├── has_tool_calls(response)
  ├── get_tool_calls(response)
  ├── get_content(response)
  └── last_assistant_content(messages)
  
  BaseLoop (thin orchestration — uses only the above)
  ├── run()               ← unchanged dispatcher
  ├── _run_sync()         ← ~35 lines, delegates to primitives
  └── _run_stream()       ← ~50 lines, delegates to primitives
```

### Affected Components

| Component | Change | Notes |
|-----------|--------|-------|
| `loop.py` — module-level | ~20 new public functions | All primitives listed above |
| `loop.py` — `_accumulate_tool_chunk` | Renamed → `accumulate_tool_chunk` | Made public |
| `loop.py` — `_accumulate_usage` | Renamed → `accumulate_usage` | Made public |
| `loop.py` — `BaseLoop` | Refactored | Both loop paths delegate to primitives |
| `loop.py` — `_IterStreamState` | Deleted | Replace inline boolean tracking |
| `loop.py` — `_yield_first_chunk_events` | Deleted | Replaced by `iterate_stream_events()` |
| `loop.py` — `_yield_stream_body_events` | Deleted | Replaced by `iterate_stream_events()` |
| `loop.py` — `_execute_tools_stream` | Deleted | Replaced by `invoke_tool()` + `append_tool_result()` |
| `executor.py` — `ToolExecutor.execute()` | Refactored | Delegates to the new primitives (backward compat) |
| `__all__` in `loop.py` | Expanded | Export all public primitives |

---

## API / Interface Contracts

All functions live in `tinycua_sdk/agent/loop.py`. They are designed to accept the most generic types possible.

---

### LLM Primitives

These take `Agent` because accessing the LLM requires the agent's client and model config. This is a natural boundary — the Agent is the right abstraction for "thing that can talk to an LLM."

#### `build_system_message(instructions, skills)`

```python
def build_system_message(
    instructions: str,
    skills: list[Skill],
) -> dict[str, str]:
    """Build a system message from instructions and skill definitions.

    Args:
        instructions: The agent's instructions string.
        skills: List of Skill instances.

    Returns:
        A dict with ``role="system"`` and joined ``content``.
    """
```

Pure function. Takes raw strings and lists — no Agent dependency. Empty instructions produce `{"role": "system", "content": ""}`.

#### `call_llm(agent, messages, tools)`

```python
async def call_llm(
    agent: Agent,
    messages: list[dict],
    tools: list[Tool],
) -> dict[str, Any]:
    """Call the LLM in sync (non-streaming) mode.

    Delegates to ``agent._call_llm()`` with ``stream=False``.

    Args:
        agent: The agent (provides LLM client and model config).
        messages: Working message list.
        tools: List of available tools.

    Returns:
        Normalized response dict with keys ``content``, ``tool_calls``, ``usage``.
    """
```

Raises `TypeError` if the LLM returns a non-dict response.

#### `call_llm_stream(agent, messages, tools)`

```python
async def call_llm_stream(
    agent: Agent,
    messages: list[dict],
    tools: list[Tool],
) -> AsyncIterator[dict[str, Any]]:
    """Call the LLM in streaming mode.

    Delegates to ``agent._call_llm()`` with ``stream=True``.

    Args:
        agent: The agent (provides LLM client and model config).
        messages: Working message list.
        tools: List of available tools.

    Returns:
        An async iterator of SSE event dicts.
    """
```

Raises `TypeError` if the LLM returns a non-AsyncIterator response.

---

### Atomic Tool Primitives

Each of these does exactly one thing. None takes an `Agent`. None has hidden side effects beyond what's documented.

#### `parse_tool_arguments(tc)`

```python
def parse_tool_arguments(
    tc: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """Parse JSON arguments from a tool call dict.

    Args:
        tc: Tool call dict with an ``arguments`` key containing a JSON string.

    Returns:
        ``(parsed_dict, None)`` on success.
        ``(None, error_message)`` on JSON decode failure.
    """
```

Pure function. No side effects.

#### `lookup_tool(tool_name, tools)`

```python
def lookup_tool(
    tool_name: str,
    tools: list[Tool],
) -> Tool | None:
    """Find a tool by name in a list of tools.

    Args:
        tool_name: The name of the tool to find.
        tools: List of Tool instances.

    Returns:
        The matching ``Tool`` or ``None`` if not found.
    """
```

Pure function. Linear scan of the tools list.

#### `check_tool_permission(tool_name, permissions)`

```python
def check_tool_permission(
    tool_name: str,
    permissions: dict[str, Literal["allow", "ask", "deny"]],
) -> Literal["allow", "ask", "deny"]:
    """Check the permission level for a tool name.

    Looks up the tool in the permissions dict. Returns ``"allow"``
    by default if the tool is not in the map.

    Args:
        tool_name: Name of the tool to check.
        permissions: A dict mapping tool names to permission levels.

    Returns:
        One of ``"allow"``, ``"ask"``, or ``"deny"``.
    """
```

Pure function. Accepts a plain dict — no Agent dependency. Returns `"allow"` for missing tools. Returns `"deny"` for invalid permission values.

#### `request_tool_approval(tool_name, arguments, workflows)`

```python
async def request_tool_approval(
    tool_name: str,
    arguments: dict[str, Any],
    workflows: list[ApprovalWorkflow] | ApprovalWorkflow | None,
) -> dict[str, Any]:
    """Request approval for a tool call via approval workflows.

    Runs each workflow in order. If any workflow rejects, returns
    its rejection dict immediately.

    Args:
        tool_name: Name of the tool to approve.
        arguments: Parsed tool arguments dict.
        workflows: One or more ApprovalWorkflow instances, or None.

    Returns:
        ``{"approved": True}`` if all workflows approve.
        ``{"approved": False, ...}`` if any workflow rejects, or
        ``{"approved": False, "error": "No approval workflow configured"}``
        if workflows is None or empty.
    """
```

Accepts raw workflow data — no Agent dependency. Handles None, single workflow, and multiple workflows.

#### `invoke_tool(tool, arguments)`

```python
async def invoke_tool(
    tool: Tool,
    arguments: dict[str, Any],
) -> Any:
    """Execute a tool with the given arguments.

    This is the pure execution step with no permission checks,
    no approval workflows, and no message building.

    Args:
        tool: The Tool instance to invoke.
        arguments: Parsed argument dict.

    Returns:
        The raw result from ``tool.invoke(**arguments)``.
    """
```

For synchronous tools, this is a thin wrapper around `tool.invoke(**arguments)`. For future async tool support, the async signature is forward-compatible.

---

### Convenience Composition

#### `execute_tool_call(tc, tools, permissions, workflows)`

```python
async def execute_tool_call(
    tc: dict[str, Any],
    tools: list[Tool],
    permissions: dict[str, Literal["allow", "ask", "deny"]],
    workflows: list[ApprovalWorkflow] | ApprovalWorkflow | None,
) -> dict[str, Any]:
    """Execute a single tool call end-to-end.

    Composes the atomic primitives in order:
    1. ``parse_tool_arguments()`` — parse JSON arguments
    2. ``lookup_tool()`` — find the tool by name
    3. ``check_tool_permission()`` — check the permissions dict
    4. ``request_tool_approval()`` — run approval workflows if needed
    5. ``invoke_tool()`` — execute the tool

    Args:
        tc: Tool call dict with keys ``name``, ``arguments``, ``id``/``call_id``.
        tools: List of available Tool instances.
        permissions: Dict mapping tool names to permission levels.
        workflows: ApprovalWorkflow instances or None.

    Returns:
        On success: ``{"output": <raw result from invoke_tool>}``.
        On error: ``{"error": <error message string>}``.
        On approval rejection: the rejection dict from the workflow.
    """
```

This is a convenience function. Users who want different behavior at any step use the atomic primitives directly. It takes raw data (dicts, lists) — no Agent dependency.

---

### Message Building Primitives

#### `build_function_call_message(tc)`

```python
def build_function_call_message(
    tc: dict[str, Any],
) -> dict[str, Any]:
    """Build a ``function_call`` message entry from a tool call dict.

    Args:
        tc: Tool call dict with keys ``name``, ``arguments``,
            and one of ``id`` or ``call_id``.

    Returns:
        ``{"type": "function_call", "call_id": ..., "name": ..., "arguments": ...}``
    """
```

#### `build_function_call_output_message(tc, output)`

```python
def build_function_call_output_message(
    tc: dict[str, Any],
    output: str,
) -> dict[str, Any]:
    """Build a ``function_call_output`` message entry.

    Args:
        tc: Tool call dict (used for ``call_id``).
        output: String representation of the tool result.

    Returns:
        ``{"type": "function_call_output", "call_id": ..., "output": ...}``
    """
```

#### `append_tool_result(messages, tc, result)`

```python
def append_tool_result(
    messages: list[dict],
    tc: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """Append function_call and function_call_output messages for a tool result.

    Mutates ``messages`` in place by appending:
    - A ``function_call`` message (from ``tc``)
    - A ``function_call_output`` message (from ``result``)

    Args:
        messages: Working message list (mutated in place).
        tc: Tool call dict.
        result: Result dict from ``execute_tool_call()`` or ``invoke_tool()``.
            Expected to have ``"output"`` or ``"error"`` key.
    """
```

---

### Stream Primitives

All stream primitives accept `asyncio.Event` for cancellation (not Agent). They are pure stream processors with no knowledge of the loop context.

#### `read_stream_chunk(llm_stream, cancel_event)`

```python
async def read_stream_chunk(
    llm_stream: AsyncIterator[dict[str, Any]],
    cancel_event: asyncio.Event,
) -> tuple[dict[str, Any] | None, bool]:
    """Read one chunk from an LLM stream, raced against cancellation.

    Args:
        llm_stream: The LLM response async iterator.
        cancel_event: An asyncio.Event that is set when cancellation is requested.

    Returns:
        ``(chunk, False)`` on a successful read,
        ``(None, True)`` when cancellation was requested,
        ``(None, False)`` when the stream is exhausted.
    """
```

#### `iter_llm_events(llm_stream, cancel_event)`

```python
async def iter_llm_events(
    llm_stream: AsyncIterator[dict[str, Any]],
    cancel_event: asyncio.Event,
) -> AsyncIterator[tuple[dict[str, Any] | None, bool]]:
    """Yield ``(chunk, is_completed)`` from an LLM stream.

    Yields ``(None, False)`` on exhaustion. Stops iteration on cancellation.

    Args:
        llm_stream: The LLM response async iterator.
        cancel_event: An asyncio.Event set on cancellation.

    Yields:
        ``(chunk, False)`` for normal chunks,
        ``(None, False)`` when the stream ends,
        ``(chunk, True)`` when the chunk type is ``response.completed``.
    """
```

Closes the stream via `aclose()` in a `finally` block.

#### `iterate_stream_events(llm_stream, cancel_event, content_parts, tool_calls_buffer, cumulative_usage, usage_settled_ids)`

```python
async def iterate_stream_events(
    llm_stream: AsyncIterator[dict[str, Any]],
    cancel_event: asyncio.Event,
    content_parts: list[str],
    tool_calls_buffer: dict[str, dict[str, Any]],
    cumulative_usage: dict[str, int],
    usage_settled_ids: set[str],
) -> AsyncIterator[dict[str, Any]]:
    """Process a full LLM stream iteration, yielding lifecycle events.

    Handles first-chunk detection, synthetic lifecycle event injection
    (``response.created``, ``response.in_progress``), body event
    forwarding, and accumulation of content, tool calls, and usage into
    the mutable containers.

    Accepts ``cancel_event`` instead of Agent — usable in any async
    context with any cancellation mechanism.

    Yields:
        Raw SSE event dicts plus synthetic lifecycle events.
    """
```

**Error handling**:
- Empty stream: yields `response.created`, `response.in_progress`, then stops.
- First chunk is terminal: passes through with appropriate lifecycle.
- Cancellation: yields `response.cancelled`, stops.

#### `accumulate_chunk(chunk, content_parts, tool_calls_buffer, cumulative_usage, usage_settled_ids)`

```python
def accumulate_chunk(
    chunk: dict[str, Any],
    content_parts: list[str],
    tool_calls_buffer: dict[str, dict[str, Any]],
    cumulative_usage: dict[str, int],
    usage_settled_ids: set[str],
) -> None:
    """Accumulate a stream chunk into content parts, tool calls, and usage.

    All mutable containers are updated in place. Unknown chunk types
    are silently ignored.
    """
```

#### `accumulate_tool_chunk(chunk, chunk_type, tool_calls_buffer)`

```python
def accumulate_tool_chunk(
    chunk: dict[str, Any],
    chunk_type: str,
    tool_calls_buffer: dict[str, dict[str, Any]],
) -> None:
    """Accumulate tool call data from a stream chunk.

    Handles: ``response.tool_call.delta``, ``response.output_item.added``,
    ``response.function_call_arguments.delta``, ``response.function_call_arguments.done``.
    """
```

#### `accumulate_usage(cumulative, usage)`

```python
def accumulate_usage(
    cumulative: dict[str, int],
    usage: dict[str, Any],
) -> None:
    """Accumulate usage into cumulative counters.

    Normalises both Responses API keys and Chat Completions keys
    into the SDK's canonical ``input_tokens``/``output_tokens``/``total_tokens``.
    """
```

---

### Response Inspection Primitives

```python
def has_tool_calls(response: dict[str, Any]) -> bool
def get_tool_calls(response: dict[str, Any]) -> list[dict[str, Any]]
def get_content(response: dict[str, Any]) -> str
def last_assistant_content(messages: list[dict]) -> str
```

All pure functions. `get_tool_calls` returns `[]` for responses with no tool calls. `get_content` returns `""` for responses with no content. `last_assistant_content` returns `""` if no assistant message exists.

---

## Refactored `BaseLoop`

### `_run_sync()` (~35 lines)

```python
async def _run_sync(self, agent, messages, tools, override_instructions=None):
    system_msg = build_system_message(
        override_instructions or agent.instructions, agent.skills
    )
    working_messages = [system_msg] + messages
    tool_call_count = 0

    for _ in range(self.max_iterations):
        if agent.is_cancelled:
            raise asyncio.CancelledError()

        if tool_call_count >= agent.policy.max_tool_calls:
            return last_assistant_content(working_messages) or "[max tool calls reached]"

        response = await call_llm(agent, working_messages, tools)

        if not has_tool_calls(response):
            content = get_content(response)
            if content:
                working_messages.append({"role": "assistant", "content": content})
            return content

        # Assistant message with function_call entries (grouped before outputs)
        assistant_msg = {"role": "assistant", "content": get_content(response) or ""}
        working_messages.append(assistant_msg)
        for tc in get_tool_calls(response):
            working_messages.append(build_function_call_message(tc))

        for tc in get_tool_calls(response):
            if agent.is_cancelled:
                raise asyncio.CancelledError()
            if tool_call_count >= agent.policy.max_tool_calls:
                return last_assistant_content(working_messages) or "[max tool calls reached]"

            result = await execute_tool_call(
                tc, tools, agent.tool_permissions, agent.approval_workflow
            )
            working_messages.append(build_function_call_output_message(tc, str(result)))
            tool_call_count += 1

    return last_assistant_content(working_messages) or "[max iterations reached]"
```

Note: `execute_tool_call` receives raw data (`agent.tool_permissions`, `agent.approval_workflow`) — not the agent itself.

### `_run_stream()` (~50 lines)

```python
async def _run_stream(self, agent, messages, tools, override_instructions=None):
    system_msg = build_system_message(
        override_instructions or agent.instructions, agent.skills
    )
    working_messages = [system_msg] + messages
    tool_call_count = 0
    cumulative_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    usage_settled_ids: set[str] = set()
    finish_reason = "completed"

    try:
        for _ in range(self.max_iterations):
            if agent.is_cancelled:
                yield {"type": "response.created"}
                yield {"type": "response.cancelled"}
                break

            if tool_call_count >= agent.policy.max_tool_calls:
                finish_reason = "max_tool_calls"
                break

            content_parts: list[str] = []
            tool_calls_buffer: dict[str, dict] = {}
            usage_settled_ids.clear()

            llm_stream = await call_llm_stream(agent, working_messages, tools)

            cancelled = False
            provider_failed = False
            completed_by_provider = False
            async for event in iterate_stream_events(
                llm_stream, agent._cancel_event,
                content_parts, tool_calls_buffer,
                cumulative_usage, usage_settled_ids,
            ):
                if event.get("type") == "response.cancelled":
                    cancelled = True
                elif event.get("type") in ("response.failed", "error"):
                    provider_failed = True
                elif event.get("type") == "response.completed":
                    completed_by_provider = True
                yield event

            if cancelled or provider_failed:
                break

            combined_content = "".join(content_parts)
            tool_calls_list = list(tool_calls_buffer.values())

            if tool_calls_list:
                if combined_content:
                    working_messages.append(
                        {"role": "assistant", "content": combined_content}
                    )
                for tc in tool_calls_list:
                    result = await execute_tool_call(
                        tc, tools, agent.tool_permissions, agent.approval_workflow
                    )
                    append_tool_result(working_messages, tc, result)
                    tool_call_count += 1
            else:
                working_messages.append(
                    {"role": "assistant", "content": combined_content}
                )
                break
        else:
            finish_reason = "max_iterations"
    except Exception as e:
        yield {"type": "response.failed", "error": {"message": str(e)}}
        yield {"type": "error", "error": {"message": str(e)}}
        return

    yield {"type": "response.usage", "usage": dict(cumulative_usage)}
    if not agent.is_cancelled and not completed_by_provider and not provider_failed:
        yield {"type": "response.completed", "finish_reason": finish_reason}
```

Note: `iterate_stream_events()` receives `agent._cancel_event` (an `asyncio.Event`) — not the agent itself.

### Private Method Delegates

For backward compatibility, BaseLoop keeps thin delegates for private methods that external custom loops might reference:

```python
class BaseLoop:
    @staticmethod
    async def _read_stream_chunk(llm_stream, cancel_event):
        return read_stream_chunk(llm_stream, cancel_event)

    @staticmethod
    async def _iter_llm_events(llm_stream, cancel_event):
        return iter_llm_events(llm_stream, cancel_event)
    # ... same for _build_system_message, _accumulate_chunk, _last_assistant_content
```

The following are **removed** from BaseLoop:
- `_IterStreamState` (dataclass)
- `_yield_first_chunk_events()`
- `_yield_stream_body_events()`
- `_execute_tools_stream()`

### `ToolExecutor.execute()` Refactoring

```python
class ToolExecutor:
    @staticmethod
    async def execute(tool: Tool, arguments: dict, agent: Agent) -> Any:
        """Execute a tool with permission and approval checks.

        Refactored to delegate to the new standalone primitives
        while maintaining the same outward behavior.
        """
        # This is the old permission check logic extracted
        permission = check_tool_permission(tool.name, agent.tool_permissions)

        if permission == "deny":
            return {"error": f"Tool '{tool.name}' is denied by permission map."}

        if permission not in ("allow", "ask"):
            return {"error": f"Tool '{tool.name}' has invalid permission '{permission}'. Denying execution."}

        if permission == "ask":
            approval = await request_tool_approval(
                tool.name, arguments, agent.approval_workflow
            )
            if not approval.get("approved"):
                return approval

        return await invoke_tool(tool, arguments)
```

This preserves the exact existing behavior while delegating to the public primitives.

---

## Implementation Phases

### Phase 1 — Atomic Tool Primitives

- [ ] **PH1-1**: Create `parse_tool_arguments()` — pure JSON parser with error handling
- [ ] **PH1-2**: Create `lookup_tool()` — linear scan by name
- [ ] **PH1-3**: Create `check_tool_permission()` — extract from `ToolExecutor.execute()`, accept plain dict
- [ ] **PH1-4**: Create `request_tool_approval()` — extract from `ToolExecutor.execute()`, accept workflow list
- [ ] **PH1-5**: Create `invoke_tool()` — thin wrapper around `tool.invoke()`
- [ ] **PH1-6**: Create `execute_tool_call()` — convenience composition of the above five
- [ ] **PH1-7**: Refactor `ToolExecutor.execute()` to delegate to the new primitives

### Phase 2 — Message Building & Inspection Primitives

- [ ] **PH2-1**: Create `build_function_call_message()` and `build_function_call_output_message()`
- [ ] **PH2-2**: Create `append_tool_result()` — convenience for interleaved format
- [ ] **PH2-3**: Create `has_tool_calls()`, `get_tool_calls()`, `get_content()`, `last_assistant_content()`

### Phase 3 — LLM Primitives

- [ ] **PH3-1**: Create `build_system_message()` — standalone, takes raw strings and skills
- [ ] **PH3-2**: Create `call_llm()` — standalone, wraps `agent._call_llm(stream=False)`
- [ ] **PH3-3**: Create `call_llm_stream()` — standalone, wraps `agent._call_llm(stream=True)`

### Phase 4 — Stream Primitives

- [ ] **PH4-1**: Rename `_accumulate_tool_chunk` → `accumulate_tool_chunk` (public)
- [ ] **PH4-2**: Rename `_accumulate_usage` → `accumulate_usage` (public)
- [ ] **PH4-3**: Extract `read_stream_chunk()` — standalone, accept `asyncio.Event`
- [ ] **PH4-4**: Extract `iter_llm_events()` — standalone, accept `asyncio.Event`
- [ ] **PH4-5**: Extract `accumulate_chunk()` — standalone
- [ ] **PH4-6**: Create `iterate_stream_events()` — combined async generator, accept `asyncio.Event`

### Phase 5 — Refactor BaseLoop

- [ ] **PH5-1**: Refactor `_run_sync()` to use standalone primitives (~35 lines)
- [ ] **PH5-2**: Refactor `_run_stream()` to use standalone primitives (~50 lines)
- [ ] **PH5-3**: Remove `_IterStreamState`, `_yield_first_chunk_events`, `_yield_stream_body_events`, `_execute_tools_stream`
- [ ] **PH5-4**: Add private method delegates for backward compatibility
- [ ] **PH5-5**: Run existing tests — all must pass without modification

### Phase 6 — New Tests

- [ ] **PH6-1**: Unit tests for all atomic tool primitives (6 functions, 3+ scenarios each)
- [ ] **PH6-2**: Unit tests for all message building primitives
- [ ] **PH6-3**: Unit tests for all LLM primitives
- [ ] **PH6-4**: Unit tests for all stream primitives (5 functions, 3+ scenarios each)
- [ ] **PH6-5**: Unit tests for response inspection primitives
- [ ] **PH6-6**: Verify existing test suites pass with zero modifications

### Phase 7 — Documentation

- [ ] **PH7-1**: Update `loop.py` module docstring with primitive overview
- [ ] **PH7-2**: Ensure all public functions in `__all__`
- [ ] **PH7-3**: Complete docstrings (Args, Returns, Yields, Raises) on all functions

---

## Technical Decisions

1. **`invoke_tool()` is async even though current tools are synchronous.**
   - The async signature is forward-compatible with future async tool support. Synchronous tools are called via `await asyncio.to_thread(tool.invoke, **args)` or directly if already synchronous. This avoids a breaking change when async tools are added.

2. **`execute_tool_call()` is a convenience wrapper, not the only path.**
   - Users who need custom behavior at any step (e.g., different permission logic, logging, metrics) use the atomic primitives directly. This decision follows from the principle that every step should be independently replaceable.

3. **Stream primitives use `asyncio.Event` for cancellation instead of accepting Agent.**
   - `asyncio.Event` is a universal async synchronization primitive. By accepting it directly, the stream primitives are usable in any async context — test code, standalone scripts, or custom frameworks — not just inside BaseLoop.

4. **`build_system_message()` takes raw strings instead of agent.**
   - The function only needs instructions and skills — two simple data structures. Taking them directly makes the function pure, testable, and usable without an Agent instance.

5. **`check_tool_permission()` accepts a plain dict instead of agent.**
   - The function only needs the permission map. Taking a dict makes it a pure function that can be tested with `{"my_tool": "deny"}` — no mock agent needed.

6. **`ToolExecutor.execute()` is refactored to delegate to primitives, preserving backward compatibility.**
   - Custom loops that use `ToolExecutor.execute()` directly continue to work. The refactoring is internal — the outward behavior is identical.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Extracting permission logic from `ToolExecutor` changes its behavior | Low | High | `ToolExecutor.execute()` is refactored to call the extracted primitives. Each primitive has unit tests matching the old behavior. |
| New `build_system_message()` signature (raw strings) breaks callers expecting agent-based signature | Low | Medium | `BaseLoop._build_system_message()` delegates with backward-compatible signature. Only new code uses the raw-string version. |
| `execute_tool_call()` convenience function encourages skipping permission checks | Low | Low | The convenience function includes permission checks by design. Users must explicitly use the atomic primitives to skip them. |
| Loop authors are confused by having both `invoke_tool` and `execute_tool_call` | Low | Low | Clear docstrings differentiate them: "pure execution" vs. "full pipeline with permission + approval". The design principle of atomicity requires both. |

---

## References

- Spec: `./spec.md`
- Current implementation: `src/tinycua-sdk/tinycua_sdk/agent/loop.py`
- Current `ToolExecutor`: `src/tinycua-sdk/tinycua_sdk/agent/executor.py`
- Permission tests: `tests/unit/test_approval.py`
