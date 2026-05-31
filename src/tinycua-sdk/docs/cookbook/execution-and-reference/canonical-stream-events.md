# Canonical Stream Events

**Prerequisites**: [Custom Execution Loops](./custom-execution-loops.md) —
you understand how `BaseLoop` processes stream events and manages the
tool-calling cycle.

## Overview

When streaming is enabled (`stream=True`), the SDK normalizes all provider
output into canonical stream events — provider-agnostic, standardized event
dicts. Every event is a plain `dict` with a `type` field identifying the
event kind.

This page is a complete reference of all 15 canonical event types, the tool
call state machine, ordering guarantees, and how to work with events in
custom code.

## Event Index

| # | Event Type | Description |
|---|---|---|
| 1 | `response.created` | A new response has been initiated |
| 2 | `response.in_progress` | The response is actively being processed |
| 3 | `response.output_text.delta` | A text content fragment from the LLM |
| 4 | `response.output_text.done` | A text content block is complete |
| 5 | `response.output_item.added` | A new tool call has started |
| 6 | `response.function_call_arguments.delta` | Tool call argument fragment |
| 7 | `response.function_call_arguments.done` | Tool call arguments are complete |
| 8 | `tool_call.ready` | Tool call is fully assembled and ready to execute |
| 9 | `response.usage` | Token usage data from the LLM |
| 10 | `response.completed` | The response is complete (with finish reason) |
| 11 | `response.failed` | The response failed with an error |
| 12 | `response.cancelled` | The response was cancelled |
| 13 | `response.reasoning.delta` | Chain-of-thought reasoning token |
| 14 | `response.reasoning.done` | Reasoning block is complete |
| 15 | `error` | An unexpected error occurred during streaming |

## Event Details

### response.created

```python
{"type": "response.created"}
```

Emitted once at the start of every stream session. This is always the first
event (or synthesized as the first event if the provider doesn't emit one).

### response.in_progress

```python
{"type": "response.in_progress"}
```

Emitted after `response.created` and before the first data event. Some
providers emit this natively; the SDK synthesizes it otherwise.

### response.output_text.delta

```python
{
    "type": "response.output_text.delta",
    "delta": "Hello",
    "index": 0,
}
```

Emitted for each text content fragment. The `delta` is a string (may be a
single token, a word, or a partial token). The `index` identifies which
output text block this delta belongs to — useful for multi-block responses.

### response.output_text.done

```python
{
    "type": "response.output_text.done",
    "index": 0,
}
```

Emitted when an output text block is complete. The `index` matches the
`response.output_text.delta` events for the same block.

### response.output_item.added

```python
{
    "type": "response.output_item.added",
    "id": "item_abc123",
    "call_id": "call_xyz789",
    "name": "web_search",
}
```

Emitted when a new tool call begins in the stream. The `id` is the output
item identifier, `call_id` identifies the specific tool call, and `name` is
the tool function name.

### response.function_call_arguments.delta

```python
{
    "type": "response.function_call_arguments.delta",
    "id": "item_abc123",
    "arguments": '{"query": ',
}
```

Emitted for each tool call argument fragment. Arguments arrive as JSON string
fragments. The `id` links to the `response.output_item.added` event.

### response.function_call_arguments.done

```python
{
    "type": "response.function_call_arguments.done",
    "id": "item_abc123",
    "call_id": "call_xyz789",
    "name": "web_search",
    "arguments": '{"query": "latest AI news"}',
}
```

Emitted when tool call arguments are fully assembled. The `arguments` field
contains the complete JSON string, suitable for `json.loads()`.

### tool_call.ready

```python
{
    "type": "tool_call.ready",
    "id": "item_abc123",
    "call_id": "call_xyz789",
    "name": "web_search",
    "arguments": '{"query": "latest AI news"}',
}
```

Emitted when a tool call is fully assembled and ready for execution. The
execution loop uses this event to trigger `ToolExecutor.execute()`.

### response.usage

```python
{
    "type": "response.usage",
    "usage": {
        "input_tokens": 150,
        "output_tokens": 42,
        "total_tokens": 192,
    },
}
```

Emitted with token usage data. In the execution loop, usage is accumulated
across all LLM calls within a single `agent.run()` call, with deduplication
by response ID. The final `response.usage` event before `response.completed`
contains cumulative totals.

### response.completed

```python
{
    "type": "response.completed",
    "finish_reason": "stop",
}
```

Emitted at the end of a successful stream session. Possible `finish_reason`
values:

| Reason | Meaning |
|---|---|
| `stop` | LLM produced a final answer |
| `tool_calls` | LLM requested tool calls (intermediate — suppressed in the agent loop) |
| `max_tool_calls` | Agent policy limit on tool calls was reached |
| `max_iterations` | Execution loop iteration limit was reached |
| `length` | LLM hit output length limit |

### response.failed

```python
{
    "type": "response.failed",
    "error": {
        "message": "Rate limit exceeded",
    },
}
```

Emitted when an exception occurs during streaming. The `error` dict preserves
original provider error value types (numeric codes, nested objects) — use
`isinstance` checks when consuming the error data.

### response.cancelled

```python
{"type": "response.cancelled"}
```

Emitted when execution is cancelled via `agent.cancel()` or
`asyncio.CancelledError`. If cancellation happens before any other event,
`response.created` is emitted first for lifecycle completeness.

### response.reasoning.delta

```python
{
    "type": "response.reasoning.delta",
    "delta": "Let me think about this step by step.",
}
```

Emitted for each chain-of-thought reasoning token. Only produced by models
with reasoning support (DeepSeek R1, Qwen with reasoning, OpenAI o-series).

### response.reasoning.done

```python
{"type": "response.reasoning.done"}
```

Emitted when the reasoning block is complete. The stream subsequently emits
`response.output_text.delta` events for the visible response.

### error

```python
{
    "type": "error",
    "error": {
        "message": "Unexpected stream failure",
    },
}
```

Emitted when an unexpected error occurs that doesn't fit the `response.failed`
category. Only produced by exception handlers inside the execution loop.

## Tool Call State Machine

The tool call lifecycle follows a strict state machine:

```
output_item.added  →  function_call_arguments.delta*  →  function_call_arguments.done  →  tool_call.ready  →  [EXECUTED by loop]
```

- **ADD** (`response.output_item.added`): A new tool call is detected. The
  `id`, `call_id`, and `name` are captured.
- **ARGUMENTS** (`response.function_call_arguments.delta`): Zero or more
  argument fragments arrive, identified by the same `id`.
- **DONE** (`response.function_call_arguments.done`): Arguments are complete
  — the full JSON string is available.
- **READY** (`tool_call.ready`): The SDK marks the tool call as ready for
  execution. The execution loop processes it.
- **EXECUTED**: The loop runs the tool, appends results to messages, and
  continues the LLM conversation.

## Event Ordering Guarantees

1. **Lifecycle first**: `response.created` is always the first event.
   `response.in_progress` follows (synthesized if needed).
2. **Data events follow**: `response.output_text.delta`, tool call events,
   and `response.usage` come after lifecycle events.
3. **Text is contiguous**: `response.output_text.delta` events for the same
   `index` arrive in order with no gaps.
4. **Tool call atomicity**: Tool call events for a single call
   (added → arguments.delta* → arguments.done → ready) are contiguous.
   Different tool calls may interleave but each call's events are ordered.
5. **Usage before completion**: `response.usage` events arrive before
   `response.completed`. The final `response.usage` has cumulative totals.
6. **One terminal event**: Exactly one of `response.completed`,
   `response.failed`, or `response.cancelled` ends the stream.

## Non-Streaming Response (LLMResponse)

When `stream=False`, the LLM returns an `LLMResponse` dict:

```python
from tinycua_sdk.agent.events import LLMResponse

response: LLMResponse = {
    "content": "The capital of Japan is Tokyo.",
    "tool_calls": None,
    "usage": {
        "input_tokens": 42,
        "output_tokens": 8,
        "total_tokens": 50,
    },
    "finish_reason": "stop",
    "model": "gpt-4o-mini",
}
```

| Field | Type | Description |
|---|---|---|
| `content` | `str \| None` | Full response text, or `None` if tool calls only |
| `tool_calls` | `list[ToolCallDict] \| None` | Tool calls the model requested |
| `usage` | `TokenUsage \| None` | Token usage with `input_tokens`, `output_tokens`, `total_tokens` |
| `finish_reason` | `str \| None` | `stop`, `tool_calls`, `length`, or `error` |
| `model` | `str \| None` | Model that produced the response |

### ToolCallDict

```python
from tinycua_sdk.agent.events import ToolCallDict

tc: ToolCallDict = {
    "id": "call_abc123",
    "call_id": "call_abc123",
    "name": "web_search",
    "arguments": '{"query": "latest AI news"}',
}
```

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Tool call identifier |
| `call_id` | `str` | Call identifier used to match results |
| `name` | `str` | Tool function name |
| `arguments` | `str` | JSON string of tool arguments |

## Working with Raw Events

The following reusable function demonstrates how to collect, filter, and
transform canonical stream events from any async event iterator:

```python
import json

async def collect_content(stream):
    content = ""
    tool_calls = {}

    async for event in stream:
        event_type = event.get("type", "")

        if event_type == "response.output_text.delta":
            content += event.get("delta", "")

        elif event_type == "response.output_item.added":
            item_id = event["id"]
            tool_calls[item_id] = {
                "id": item_id,
                "call_id": event["call_id"],
                "name": event["name"],
                "arguments": "",
            }

        elif event_type == "response.function_call_arguments.delta":
            item_id = event.get("id", "")
            if item_id in tool_calls:
                tool_calls[item_id]["arguments"] += event.get("arguments", "")

        elif event_type == "tool_call.ready":
            item_id = event["id"]
            if item_id in tool_calls:
                tool_calls[item_id]["arguments"] = event["arguments"]
                tool_calls[item_id]["parsed"] = json.loads(event["arguments"])

    return content, tool_calls
```

## Common Pitfalls

**Filtering on event type without an `else`**. The event type string can be
empty or unknown. Always check with `event_type == "..."` and have a fallback
path. Don't assume every event is one of the 15 types.

**Ignoring `index` in text events**. When the LLM produces multiple output
text blocks (rare but possible with some providers), deltas with different
`index` values belong to different content blocks. If you simply concatenate
all deltas without tracking `index`, you'll mix content from different blocks.

**Assuming `response.completed` always has a `finish_reason`**. While the
SDK always populates `finish_reason`, consuming events from an external
source or a custom provider may omit it. Check with `event.get("finish_reason")`.

## Next Steps

- **[Error Handling](./error-handling.md)** — Catch `ProviderApiError`,
  `ProviderAuthError`, and `ProviderNotSupportedError` with retry and
  cancellation patterns.

## Related Topics

- **[Custom Execution Loops](./custom-execution-loops.md)** — Override
  `BaseLoop` to customize how events are processed.