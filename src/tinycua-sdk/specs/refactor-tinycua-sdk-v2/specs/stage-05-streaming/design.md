# Stage 5: Streaming — Design

**Spec**: `specs/refactor-tinycua-sdk-v2/specs/stage-05-streaming/spec.md`
**Last Updated**: 2026-05-09

## Architecture

### API Endpoint: OpenAI Responses API

The SDK communicates with the LLM via the **OpenAI Responses API** (`POST /v1/responses`), not the Chat Completions API. This means:

- Request payload uses `"input"` (not `"messages"`) for the conversation array.
- Streaming SSE events are typed (`response.output_text.delta`, `response.function_call_arguments.delta`, etc.) rather than the Chat Completions `choices[].delta` format.
- Tool call arguments arrive as `response.function_call_arguments.delta` / `.done` events correlated by `item_id`.
- The stream ends with a `response.completed` event (not `data: [DONE]`).

See the [spec](specs/refactor-tinycua-sdk-v2/specs/stage-05-streaming/spec.md#api-contract-openai-responses-api) for the full API contract comparison.

### Streaming Decision (simplified)

```
Agent.run(stream=False)
    │
    └──► BaseLoop.run() ──► _run_sync() ──► returns str
            └──► LLMClient.chat(stream=False) ──► single response dict

Agent.run(stream=True)
    │
    └──► BaseLoop.run() ──► _run_stream() ──► AsyncIterator[dict]
            └──► LLMClient.chat(stream=True) ──► AsyncIterator[chunk]
                    └──► Yield every chunk as-is (raw passthrough)
```

## Implementation

### `BaseLoop.run()` with Streaming

```python
async def run(
    self,
    agent: Agent,
    messages: list[dict],
    tools: list[Tool],
    override_instructions: str | None = None,
    stream: bool = False,
) -> str | AsyncIterator[dict]:
    if not stream:
        return await self._run_sync(agent, messages, tools, override_instructions)
    return self._run_stream(agent, messages, tools, override_instructions)

async def _run_stream(self, agent, messages, tools, override_instructions=None):
    system_msg = self._build_system_message(agent, override_instructions)
    messages = [system_msg] + messages

    yield {"type": "response.created"}

    cumulative_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for iteration in range(self.max_iterations):
        if agent.is_cancelled:
            yield {"type": "response.cancelled"}
            break

        # Stream LLM response — yield raw events, accumulate internally
        stream = await agent._call_llm(messages, tools, stream=True)
        content_parts = []
        content_item_id = ""
        tool_calls_buffer = {}

        async for chunk in stream:
            yield chunk  # raw passthrough

            chunk_type = chunk.get("type", "")
            if chunk_type == "response.output_text.delta":
                if not content_item_id:
                    content_item_id = chunk.get("item_id", "")
                content_parts.append(chunk.get("delta", ""))
            elif chunk_type in ("response.output_item.added",
                                "response.function_call_arguments.delta",
                                "response.function_call_arguments.done"):
                # Accumulate tool call data
                ...
            elif chunk_type == "response.usage":
                usage = chunk.get("usage", {})
                for key in cumulative_usage:
                    cumulative_usage[key] += usage.get(key, 0)

        # No synthetic events — just accumulate message state
        if tool_calls_data:
            # Execute tools, append results to messages
            ...
            continue
        else:
            break

    yield {"type": "response.usage", "usage": dict(cumulative_usage)}
    yield {"type": "response.completed", "finish_reason": finish_reason}
```

## Design Decisions

### Raw Passthrough
The SDK is a thin passthrough for events. Consumers who want filtering can add it in their own layer. This eliminates 4 code paths through the same generator, reduces bug surface area, and aligns with the OpenAI Responses API design.

### Stream Accumulation
Tool calls may be split across multiple SSE chunks. The loop must accumulate partial tool call JSON before executing. We use an in-memory buffer that assembles the full tool call before execution.

### Cumulative Usage
Usage data is accumulated across all LLM iterations in a single `cumulative_usage` dict. Raw usage events are forwarded during the stream, and a final cumulative `response.usage` event is emitted at the end.

### Error Handling in Streaming
The `_run_stream` generator wraps its main loop in a try/except block. On any exception:
1. A `response.failed` event is yielded with error details.
2. An `error` event is yielded with the same details.
3. The generator returns (stops iteration).

```python
async def _run_stream(self, ...):
    yield {"type": "response.created"}
    try:
        for _ in range(self.max_iterations):
            ...
    except Exception as e:
        yield {"type": "response.failed", "error": {"message": str(e)}}
        yield {"type": "error", "error": {"message": str(e)}}
        return
    yield {"type": "response.completed", "finish_reason": finish_reason}
```

### Event Flow Summary

```
Stream Start
  │
  ├── response.created
  │
  ├── [while iterating]
  │     ├── Raw SSE events passthrough from LLM
  │     │   (response.output_text.delta, response.output_item.added, response.function_call_arguments.delta, response.function_call_arguments.done, response.usage, ...)
  │     │
  │     ├── [tool calls detected: execute tools silently]
  │     │   └── (no synthetic events emitted)
  │     │
  │     └── [repeat if more tool calls]
  │
  ├── response.usage (cumulative, at end)
  ├── response.completed  (on success)
  │
  └── response.failed + error (on failure)
```

### Deferred/Removed Events

| Event | Status | Rationale |
|---|---|---|
| `response.output_text.done` | Removed | No longer synthetic — consumers track completion via delta stream end |
| `response.output_item.added` | Accumulated | Used to initialise tool call buffers from raw events |
| `response.output_item.done` | Removed | No longer synthetic — raw passthrough only |
| `response.in_progress` | Deferred to Stage 8 | Lifecycle completeness |
| `response.function_call_arguments.delta/.done` | Accumulated | Used to accumulate partial tool call arguments from raw events |
| `response.content_part.added/.done` | Deferred to Stage 9 | Multi-part response support |
| `response.output_text.annotation.added` | Deferred to Stage 9 | Citation/annotation support |

### Return Type
`Agent.run()` returns `str` when `stream=False` and `AsyncIterator[dict]` when `stream=True`.

## File Changes

| File | Change |
|------|--------|
| `agent/loop.py` | `_run_stream` generator with raw passthrough; remove `_stream_llm`, `_build_tool_events`, `stream_mode` params; add cumulative usage |
| `agent/llm_client.py` | Add `stream: bool` param; add `_chat_stream()` for SSE parsing/raw event passthrough; add `_chat_sync()` for non-streaming path request; update `chat()` dispatch to return `AsyncIterator[dict]` when `stream=True` |
| `agent/agent.py` | Change `stream: bool = False`, remove mode validation |

## Testing Strategy

- Mock `agent._call_llm(stream=True)` to yield fake event dicts.
- Verify raw events passthrough unchanged.
- Verify lifecycle events (created, completed, failed, cancelled, usage).
- Verify tool call execution still works (but no synthetic tool events).
- Verify cumulative usage across multiple LLM iterations.
