# Stage 5: Streaming — Design

**Spec**: `specs/refactor-tinycua-sdk-v2/specs/stage-05-streaming/spec.md`

## Architecture

### Streaming Decision Tree

```
Agent.run(stream="off")
    │
    ├──► BaseLoop.run() ──► returns str
    │       └──► LLMClient.chat(stream=False) ──► single response dict

Agent.run(stream="token")
    │
    ├──► BaseLoop.run() ──► returns AsyncIterator[dict]
    │       └──► LLMClient.chat(stream=True) ──► AsyncIterator[chunk]
    │               └──► Yield only .delta chunks

Agent.run(stream="event")
    │
    ├──► BaseLoop.run() ──► returns AsyncIterator[dict]
    │       └──► LLMClient.chat(stream=True) ──► AsyncIterator[chunk]
    │               └──► Skip .delta chunks
    │               └──► Yield tool_call events, completion events

Agent.run(stream="all")
    │
    ├──► BaseLoop.run() ──► returns AsyncIterator[dict]
    │       └──► LLMClient.chat(stream=True) ──► AsyncIterator[chunk]
    │               └──► Yield everything
```

## Implementation

### `BaseLoop.run()` with Streaming

```python
from typing import AsyncIterator

async def run(
    self,
    agent: Agent,
    messages: list[dict],
    tools: list[Tool],
    override_instructions: str | None = None,
    stream: str = "off",
) -> str | AsyncIterator[dict]:
    if stream == "off":
        return await self._run_sync(agent, messages, tools, override_instructions)
    return self._run_stream(agent, messages, tools, override_instructions, stream)

async def _run_sync(self, agent, messages, tools, override_instructions):
    # Same as Stage 3 implementation
    ...

async def _run_stream(self, agent, messages, tools, override_instructions, stream_mode):
    system_msg = self._build_system_message(agent, override_instructions)
    messages = [system_msg] + messages

    yield {"type": "response.created"}

    for iteration in range(self.max_iterations):
        if agent.is_cancelled:
            break

        # Stream LLM response
        stream = await agent._call_llm(messages, tools, stream=True)
        content_parts = []
        content_item_id = ""
        tool_calls_data = []

        async for chunk in stream:
            chunk_type = chunk.get("type", "")
            if chunk_type == "response.output_text.delta":
                if not content_item_id:
                    content_item_id = chunk.get("item_id", "")
                content_parts.append(chunk.get("delta", ""))
                if stream_mode in ("token", "all"):
                    yield chunk
            elif chunk_type == "response.tool_call.delta":
                # Accumulate tool call data
                tool_calls_data.append(chunk)

        # Emit completion events for text output
        if content_parts:
            if stream_mode in ("event", "all"):
                yield {
                    "type": "response.output_text.done",
                    "item_id": content_item_id,
                    "content": "".join(content_parts),
                }
                yield {
                    "type": "response.output_item.done",
                    "item": {"type": "text"},
                }

        if tool_calls_data:
            for tc in tool_calls_data:
                if stream_mode in ("event", "all"):
                    yield {
                        "type": "response.output_item.added",
                        "item": {"type": "tool_call", "name": tc["name"], "arguments": tc["arguments"]},
                    }
                    yield {
                        "type": "response.output_item.done",
                        "item": {"type": "tool_call", "name": tc["name"]},
                    }

            # Execute tools
            for tc in tool_calls_data:
                tool = next((t for t in tools if t.name == tc["name"]), None)
                result = await ToolExecutor.execute(tool, tc["arguments"], agent)
                if stream_mode in ("event", "all"):
                    yield {
                        "type": "response.output_item.added",
                        "item": {"type": "tool_output", "name": tc["name"], "output": str(result)},
                    }
                    yield {
                        "type": "response.output_item.done",
                        "item": {"type": "tool_output", "name": tc["name"]},
                    }

            # Continue loop
            continue
        else:
            break

    yield {"type": "response.completed"}
```

### `LLMClient.chat()` with Streaming

```python
class OpenAICompatibleClient(LLMClient):
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        model_config: LanguageModel,
        stream: bool = False,
    ) -> dict | AsyncIterator[dict]:
        if not stream:
            return await self._chat_sync(messages, tools, model_config)
        return self._chat_stream(messages, tools, model_config)

    async def _chat_stream(self, messages, tools, model_config):
        client = self._get_client(model_config)
        payload = self._build_payload(messages, tools, model_config)
        payload["stream"] = True

        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    # Normalize to our event shape
                    delta = data["choices"][0].get("delta", {})
                    if delta.get("content"):
                        yield {
                            "type": "response.output_text.delta",
                            "delta": delta["content"],
                            "item_id": data["choices"][0].get("id", ""),
                        }
                    elif delta.get("tool_calls"):
                        for tc in delta["tool_calls"]:
                            yield {
                                "type": "response.tool_call.delta",
                                "id": tc["id"],
                                "name": tc["function"]["name"],
                                "arguments": tc["function"]["arguments"],
                            }
```

## Design Decisions

### Stream Accumulation
Tool calls may be split across multiple SSE chunks. The loop must accumulate partial tool call JSON before executing. We use an in-memory buffer that assembles the full tool call before execution.

### Filtering
The same `_run_stream` code path is used for all modes. Filtering is done at yield time:
- `stream="token"`: yield only `.delta` events.
- `stream="event"`: yield only non-delta events.
- `stream="all"`: yield everything.

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
    yield {"type": "response.completed"}
```

### Event Flow Summary

```
Stream Start
  │
  ├── response.created
  │
  ├── [while iterating]
  │     ├── response.output_text.delta (0..N, token/all modes only)
  │     ├── response.output_text.done  (if text present, event/all)
  │     ├── response.output_item.done  (text item, event/all)
  │     │
  │     ├── response.output_item.added (tool_call, event/all)
  │     ├── response.output_item.done  (tool_call, event/all)
  │     ├── response.output_item.added (tool_output, event/all)
  │     ├── response.output_item.done  (tool_output, event/all)
  │     │
  │     └── [repeat if more tool calls]
  │
  ├── response.completed  (on success)
  │
  └── response.failed + error (on failure)
```

### Deferred Events

The following OpenAI Responses API event types are recognized but deferred to later stages. The "stage" field in spec.md R-5.2.0 references the stage that will implement each:

| Deferred Event | Assigned To | Rationale |
|---|---|---|
| `response.in_progress` | Stage 8 (Custom Loops) | Lifecycle completeness — custom loops should emit full event sets |
| `response.function_call_arguments.delta` / `.done` | Stage 8 (Custom Loops) | Standard OpenAI event naming — custom loop consumers benefit |
| `response.content_part.added` / `.done` | Stage 9 (Final Integration) | Multi-part response support — requires wider integration |
| `response.output_text.annotation.added` | Stage 9 (Final Integration) | Citation/annotation support — final polish item |

### Return Type
`Agent.run()` must return `str` when `stream="off"` and `AsyncIterator[dict]` otherwise. This is a type union. In practice, consumers will know which mode they requested.

## File Changes

| File | Change |
|------|--------|
| `agent/loop.py` | Add `_run_stream` generator, update `run()` signature |
| `agent/llm_client.py` | Add `_chat_stream`, update `chat()` signature |
| `agent/agent.py` | Remove `NotImplementedError` for streaming |

## Testing Strategy

- Mock `httpx.AsyncClient.stream` to yield fake SSE lines.
- Test each mode independently:
  - `token` mode: count `.delta` events, ensure no `tool_call` events.
  - `event` mode: ensure no `.delta` events.
  - `all` mode: ensure both types present.
- Test tool-calling with streaming:
  - Mock LLM returns tool call in stream.
  - Verify tool_call event is emitted.
  - Verify tool_output event is emitted.
  - Verify stream resumes with next LLM response.
