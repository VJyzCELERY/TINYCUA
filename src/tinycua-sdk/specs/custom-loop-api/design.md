# Design Document: Custom Loop Creation API Simplification

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-05-16

---

## Overview

Refactor `tinycua_sdk/agent/loop.py` to decompose both `_run_sync()` and `_run_stream()` into atomic, standalone, public helper functions. The loop execution model becomes a straightforward while loop where each step — calling the LLM, checking permissions, requesting approval, executing a tool, building messages — is a replaceable primitive. `BaseLoop` becomes a thin orchestration layer that delegates entirely to these primitives.

Custom loop authors import only the primitives they need and compose them however they like, without subclassing `BaseLoop` or touching private internals.

---

## Architecture

### Execution Model

Both sync and streaming loops follow the same conceptual model:

```
while iter < max_iterations:
    response = call_llm(agent, messages, tools)

    if has_tool_calls(response):
        for tc in get_tool_calls(response):
            permission = check_tool_permission(tc["name"], agent)

            if permission == "deny":
                append_tool_error(messages, tc, "denied")
                continue

            if permission == "ask":
                approval = await request_tool_approval(tc, agent)
                if not approval["approved"]:
                    append_tool_error(messages, tc, approval)
                    continue

            # permission == "allow" (or approved)
            result = await execute_tool(tc, tools, agent)
            append_tool_result(messages, tc, result)
    else:
        content = get_content(response)
        append_assistant_message(messages, content)
        return content
```

Every function in this flow is a standalone public primitive. The user can replace any single function without touching the rest.

### Component Diagram

```
  loop.py (public API)
  ─────────────────────────────────────────────────────────────
  
  LLM Primitives                 Permission/Approval
  ├── call_llm()                 ├── check_tool_permission()
  ├── call_llm_stream()          ├── request_tool_approval()
  └── build_system_message()     └── execute_tool_call()
  
  Message Building               Response Inspection
  ├── build_function_call_message()    ├── has_tool_calls()
  ├── build_function_call_output_message()  ├── get_tool_calls()
  └── append_tool_result()             ├── get_content()
                                       └── last_assistant_content()
  
  Stream Processing              Tool Utilities
  └── iterate_stream_events()    └── parse_tool_arguments()
                                  └── lookup_tool()
  
  BaseLoop (thin orchestration)
  ├── run()               ← unchanged dispatcher
  ├── _run_sync()         ← now delegates to primitives (~35 lines)
  └── _run_stream()       ← now delegates to primitives (~50 lines)
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `loop.py` — module-level | New public functions | ~15 new standalone primitives |
| `loop.py` — `_accumulate_tool_chunk` | Renamed → `accumulate_tool_chunk` (public) | |
| `loop.py` — `_accumulate_usage` | Renamed → `accumulate_usage` (public) | |
| `loop.py` — `BaseLoop` | Modified | Both `_run_sync()` and `_run_stream()` refactored to delegate to primitives |
| `loop.py` — `_IterStreamState` | Deleted | No longer needed |
| `loop.py` — `_yield_first_chunk_events` | Deleted | Replaced by `iterate_stream_events()` |
| `loop.py` — `_yield_stream_body_events` | Deleted | Replaced by `iterate_stream_events()` |
| `loop.py` — `_execute_tools_stream` | Deleted | Replaced by `execute_tool_call()` and `append_tool_result()` |
| `loop.py` — `__all__` | Expanded | Export all new public functions |
| `ToolExecutor.execute()` | Unchanged | Still works; `execute_tool_call()` delegates to it internally |
| `test_loop.py` | Unchanged | Must pass without modification |
| `test_loop_custom.py` | Unchanged | Must pass without modification |
| `test_agent_run.py` | Unchanged | Must pass without modification |
| `test_agent_streaming.py` | Unchanged | Must pass without modification |

---

## API / Interface Contracts

All functions live in `tinycua_sdk/agent/loop.py`. They are stateless unless otherwise noted.

---

### LLM Primitives

#### `build_system_message(agent, override_instructions=None)`

```python
def build_system_message(
    agent: Agent,
    override_instructions: str | None = None,
) -> dict[str, str]:
    """Build a system message from agent instructions and skill definitions.

    Args:
        agent: The agent whose instructions/skills to use.
        override_instructions: When provided, replaces agent.instructions.

    Returns:
        A dict with ``role="system"`` and joined ``content``.
    """
```

Pure function — no exceptions. Empty instructions produce `{"role": "system", "content": ""}`.

---

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
        agent: The agent (provides LLM client, model config).
        messages: Working message list.
        tools: List of available tools.

    Returns:
        Normalized response dict with keys ``content``, ``tool_calls``, ``usage``.
    """
```

Raises: `TypeError` if the LLM returns a non-dict response (same as current behavior).

---

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
        agent: The agent.
        messages: Working message list.
        tools: List of available tools.

    Returns:
        An async iterator of SSE event dicts.
    """
```

Raises: `TypeError` if the LLM returns a non-AsyncIterator response.

---

### Response Inspection Primitives

#### `has_tool_calls(response)`

```python
def has_tool_calls(response: dict[str, Any]) -> bool:
    """Check if an LLM response contains tool calls."""
```

#### `get_tool_calls(response)`

```python
def get_tool_calls(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract tool calls from an LLM response.

    Returns an empty list if no tool calls are present.
    """
```

#### `get_content(response)`

```python
def get_content(response: dict[str, Any]) -> str:
    """Extract text content from an LLM response.

    Returns ``""`` if no content is present.
    """
```

#### `last_assistant_content(messages)`

```python
def last_assistant_content(messages: list[dict]) -> str:
    """Find the content of the last assistant message, or empty string."""
```

---

### Permission & Approval Primitives

#### `check_tool_permission(tool_name, agent)`

```python
def check_tool_permission(
    tool_name: str,
    agent: Agent,
) -> Literal["allow", "ask", "deny"]:
    """Check the permission level for a tool name.

    Looks up the tool in ``agent.tool_permissions``.
    Returns ``"allow"`` by default if the tool is not in the map.

    Args:
        tool_name: Name of the tool to check.
        agent: The agent whose permission map to query.

    Returns:
        One of ``"allow"``, ``"ask"``, or ``"deny"``.
    """
```

Pure function. Returns `"allow"` for tools not in the permission map. Returns `"deny"` for invalid permission values.

---

#### `request_tool_approval(tool_call_data, agent)`

```python
async def request_tool_approval(
    tool_call_data: dict[str, Any],
    agent: Agent,
) -> dict[str, Any]:
    """Request approval for a tool call via the agent's ApprovalWorkflow.

    Args:
        tool_call_data: Dict with ``name``, ``arguments``, and ``call_id``.
        agent: The agent whose ``approval_workflow`` to use.

    Returns:
        Approval result dict (e.g., ``{"approved": True}`` or
        ``{"approved": False, "reason": "..."}``).
    """
```

**Error handling**:
- If no `approval_workflow` is configured: returns `{"approved": False, "error": "No approval workflow configured"}`.
- If a workflow rejects: returns the rejection dict as-is from the workflow.

---

#### `execute_tool_call(tc, tools, agent)`

```python
async def execute_tool_call(
    tc: dict[str, Any],
    tools: list[Tool],
    agent: Agent,
) -> dict[str, Any]:
    """Execute a single tool call with permission check and optional approval.

    Orchestrates the full lifecycle for one tool call in order:
    1. Parse JSON arguments from ``tc["arguments"]``
    2. Look up the tool by name in ``tools``
    3. Check permission via ``check_tool_permission()``
    4. If ``"ask"``, request approval via ``request_tool_approval()``
    5. Execute via ``ToolExecutor.execute()``

    Args:
        tc: Tool call dict with keys ``name``, ``arguments``, ``id``/``call_id``.
        tools: List of available tools.
        agent: The agent (provides permissions, approval workflow).

    Returns:
        Result dict. On success: ``{"output": <tool result>}``.
        On error: ``{"error": <error message>}``.
    """
```

**Error handling**:
- JSON parse error: returns `{"error": "Failed to parse arguments: ..."}`
- Unknown tool: returns `{"error": "Unknown tool: ..."}`
- Permission denied: returns `{"error": "Tool ... is denied by permission map."}`
- Approval denied: returns the approval rejection dict
- Tool execution failure: returns `{"error": "Tool execution failed: ..."}` (caught exception)

This function does NOT append anything to the message list — it only returns the result. The caller decides what to do with it.

---

#### `parse_tool_arguments(tc)`

```python
def parse_tool_arguments(
    tc: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """Parse JSON arguments from a tool call dict.

    Args:
        tc: Tool call dict with an ``arguments`` key.

    Returns:
        ``(parsed_args, None)`` on success,
        ``(None, error_message)`` on parse failure.
    """
```

---

#### `lookup_tool(tool_name, tools)`

```python
def lookup_tool(
    tool_name: str,
    tools: list[Tool],
) -> Tool | None:
    """Find a tool by name in the tools list.

    Returns the ``Tool`` instance or ``None`` if not found.
    """
```

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

    Mutates ``messages`` in place by appending two entries:
    the function_call message and the function_call_output message.

    Args:
        messages: Working message list (mutated in place).
        tc: Tool call dict.
        result: The result dict from ``execute_tool_call()``.
    """
```

---

### Stream Processing Primitive

#### `iterate_stream_events(llm_stream, agent, content_parts, tool_calls_buffer, cumulative_usage, usage_settled_ids)`

```python
async def iterate_stream_events(
    llm_stream: AsyncIterator[dict[str, Any]],
    agent: Agent,
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

    When cancellation is detected, yields ``response.cancelled`` and stops.

    Yields:
        Raw SSE event dicts plus synthetic lifecycle events.
    """
```

**Error handling**:
- Empty stream: yields `response.created`, `response.in_progress`, then stops.
- First chunk is terminal (`response.completed`, `response.failed`, `error`): passes through with appropriate lifecycle.
- Cancellation: yields `response.cancelled`, stops.

---

## Refactored `BaseLoop`

### `_run_sync()` (~35 lines)

```python
async def _run_sync(self, agent, messages, tools, override_instructions=None):
    system_msg = build_system_message(agent, override_instructions)
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

        # Build assistant message with tool calls
        tool_calls = get_tool_calls(response)
        assistant_msg = {"role": "assistant", "content": get_content(response) or ""}
        working_messages.append(assistant_msg)
        # Append function_call entries (before outputs)
        for tc in tool_calls:
            working_messages.append(build_function_call_message(tc))

        for tc in tool_calls:
            if agent.is_cancelled:
                raise asyncio.CancelledError()
            if tool_call_count >= agent.policy.max_tool_calls:
                return last_assistant_content(working_messages) or "[max tool calls reached]"

            result = await execute_tool_call(tc, tools, agent)
            # Only the output message, function_call was already appended above
            working_messages.append(
                build_function_call_output_message(tc, str(result))
            )
            tool_call_count += 1

    return last_assistant_content(working_messages) or "[max iterations reached]"
```

(Note: This inlines the message structure more explicitly compared to the current code — the function_call entries are grouped before outputs, matching the current `_run_sync` behavior. The `append_tool_result` helper uses the interleaved format for stream mode.)

### `_run_stream()` (~50 lines)

```python
async def _run_stream(self, agent, messages, tools, override_instructions=None):
    system_msg = build_system_message(agent, override_instructions)
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
                llm_stream, agent, content_parts, tool_calls_buffer,
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
                assistant_index = len(working_messages)
                if combined_content:
                    working_messages.append(
                        {"role": "assistant", "content": combined_content}
                    )
                for tc in tool_calls_list:
                    result = await execute_tool_call(tc, tools, agent)
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

### Private Method Delegates

For backward compatibility, BaseLoop keeps thin delegates for any private methods that external custom loops might reference:

```python
class BaseLoop:
    @staticmethod
    async def _read_stream_chunk(llm_stream, cancel_event):
        return read_stream_chunk(llm_stream, cancel_event)

    @staticmethod
    async def _iter_llm_events(llm_stream, cancel_event):
        return iter_llm_events(llm_stream, cancel_event)
```

The following are **removed** from BaseLoop (private, no longer used internally, and not part of the documented extension contract):
- `_IterStreamState` (dataclass)
- `_yield_first_chunk_events()`
- `_yield_stream_body_events()`
- `_execute_tools_stream()`

The following **delegate** to standalone primitives:
- `_build_system_message()` → `build_system_message()`
- `_accumulate_chunk()` → `accumulate_chunk()`
- `_last_assistant_content()` → `last_assistant_content()`

---

## Implementation Phases

### Phase 1 — Permission & Approval Primitives

- [ ] **PH1-1**: Extract `check_tool_permission()` from `ToolExecutor.execute()` as standalone function
- [ ] **PH1-2**: Extract `request_tool_approval()` from `ToolExecutor.execute()` as standalone async function
- [ ] **PH1-3**: Create `execute_tool_call()` combining permission check + approval + tool execution
- [ ] **PH1-4**: Existing `ToolExecutor.execute()` refactored to delegate to the new primitives (backward compat)

### Phase 2 — Message Building Primitives

- [ ] **PH2-1**: Create `build_function_call_message()` and `build_function_call_output_message()`
- [ ] **PH2-2**: Create `append_tool_result()` (interleaved format, for stream path)
- [ ] **PH2-3**: Create `has_tool_calls()`, `get_tool_calls()`, `get_content()`, `last_assistant_content()`
- [ ] **PH2-4**: Create `parse_tool_arguments()` and `lookup_tool()`

### Phase 3 — LLM Primitives

- [ ] **PH3-1**: Create `build_system_message()` standalone (extract from BaseLoop)
- [ ] **PH3-2**: Create `call_llm()` standalone (extract from existing inline logic)
- [ ] **PH3-3**: Create `call_llm_stream()` standalone (extract from existing inline logic)

### Phase 4 — Stream Processing

- [ ] **PH4-1**: Rename `_accumulate_tool_chunk` → `accumulate_tool_chunk` (public)
- [ ] **PH4-2**: Rename `_accumulate_usage` → `accumulate_usage` (public)
- [ ] **PH4-3**: Create `iterate_stream_events()` (replaces the two split methods)
- [ ] **PH4-4**: Create `accumulate_chunk()` standalone (extract from BaseLoop)
- [ ] **PH4-5**: Create `read_stream_chunk()` and `iter_llm_events()` standalone (extract from BaseLoop)

### Phase 5 — Refactor BaseLoop

- [ ] **PH5-1**: Refactor `_run_sync()` to use standalone primitives (~35 lines)
- [ ] **PH5-2**: Refactor `_run_stream()` to use standalone primitives (~50 lines)
- [ ] **PH5-3**: Remove `_IterStreamState`, `_yield_first_chunk_events`, `_yield_stream_body_events`, `_execute_tools_stream`
- [ ] **PH5-4**: Add private method delegates for backward compatibility
- [ ] **PH5-5**: Run existing tests — all must pass without modification

### Phase 6 — New Tests

- [ ] **PH6-1**: Unit tests for all permission/approval primitives
- [ ] **PH6-2**: Unit tests for all message building primitives
- [ ] **PH6-3**: Unit tests for all LLM primitives
- [ ] **PH6-4**: Unit tests for all stream processing primitives
- [ ] **PH6-5**: Unit tests for all response inspection utilities
- [ ] **PH6-6**: Verify existing test suites pass with zero modifications

### Phase 7 — Documentation

- [ ] **PH7-1**: Update `loop.py` module docstring with primitive overview
- [ ] **PH7-2**: Ensure all public functions in `__all__`
- [ ] **PH7-3**: Complete docstrings (Args, Returns, Yields, Raises) on all functions

---

## Technical Decisions

1. **`execute_tool_call()` returns a result dict rather than appending to messages.**
   - Message building is separated from tool execution so custom loop authors can format messages differently (e.g., adding metadata, logging). The caller decides how to integrate the result.
   - Alternative considered: `execute_tool_call()` appends to messages directly — rejected because it couples execution with formatting.

2. **Permission checking is exposed as a standalone primitive extracted from `ToolExecutor`.**
   - `ToolExecutor.execute()` currently bundles permission check, approval, and execution into one method. By extracting the first two steps, custom loop authors can replace just the permission/approval logic without touching execution.
   - `ToolExecutor.execute()` itself is refactored to call these primitives, maintaining full backward compatibility.

3. **`_run_sync()` groups function_call entries before outputs (current behavior preserved), while `append_tool_result()` uses interleaved format for stream.**
   - The sync and stream paths produce messages in slightly different orders (grouped vs. interleaved). Rather than forcing one format, the design provides both `build_function_call_message()` / `build_function_call_output_message()` (for explicit ordering) and `append_tool_result()` (for convenience). The loop implementations use whichever matches their context.

4. **BaseLoop remains as the default loop class, not removed.**
   - Removing BaseLoop would be a breaking change for any existing `isinstance()` checks or subclass references. Refactoring it internally achieves the goal without disruption.

5. **`call_llm()` and `call_llm_stream()` are thin wrappers around `agent._call_llm()`.**
   - They exist as public entry points so custom loops don't need to access the private `agent._call_llm()` method. They also provide a natural place for future middleware (logging, retries, metrics).

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Extracting permission logic from `ToolExecutor` changes its behavior | Low | High | `ToolExecutor.execute()` is refactored to call the extracted primitives, with the same logic. Existing tests cover this. |
| `_run_sync()` message ordering changes subtly | Low | Medium | Existing tests cover exact message formats in `test_loop.py`. These must pass. |
| Custom loops referencing removed private methods break | Low | Medium | Thin delegates kept in Phase 5. A deprecation warning could precede their eventual removal. |
| Circular imports from standalone functions referencing `Agent` / `Tool` | Low | Low | Use `TYPE_CHECKING` guards for type hints (existing pattern in the codebase). |

---

## References

- Spec: `./spec.md`
- Current implementation: `src/tinycua-sdk/tinycua_sdk/agent/loop.py`
- Current `ToolExecutor`: `src/tinycua-sdk/tinycua_sdk/agent/executor.py`
- Existing tests: `tests/unit/test_loop.py`, `tests/unit/test_loop_custom.py`, `tests/unit/test_agent_run.py`
- Permission/approval tests: `tests/unit/test_approval.py`
