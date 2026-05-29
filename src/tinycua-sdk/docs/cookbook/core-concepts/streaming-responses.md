# Streaming Responses

**Prerequisites**: [Language Models and Providers](./language-models-and-providers.md)

## Overview

By default, `agent.run()` blocks until the LLM finishes generating and returns the complete response as a single string. For real-time applications — chat UIs, live transcriptions, progressive tool execution — you need token-by-token streaming instead.

Pass `stream=True` to `agent.run()` and it returns an `AsyncIterator` of event dictionaries. Each event has a `type` field identifying what happened (a text delta, a tool call starting, a usage summary, etc.). You iterate over events as they arrive and handle each one based on its type.

This page covers iterating over stream events, accumulating text content from deltas, filtering by event type, and cancelling a running stream.

## Setting Up an Agent for Streaming

Configure an agent as usual. The standalone block stops at construction — the continuation block below demonstrates the live streaming loop.

**Remote (OpenAI):**

```python
import os
from tinycua_sdk import LanguageModel, Agent

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    api_key=os.environ.get("OPENAI_API_KEY"),
    temperature=0.7,
)

agent = Agent(
    name="streaming-agent",
    instructions="You are a helpful, concise assistant.",
    llm_model=model,
)
```

**Local (local LLM server):**

```python
from tinycua_sdk import LanguageModel, Agent

model = LanguageModel(
    provider="openai-compatible",
    model_name="qwen/qwen3.5-9b",
    base_url="http://localhost:1234/v1",
    temperature=0.7,
)

agent = Agent(
    name="streaming-agent",
    instructions="You are a helpful, concise assistant.",
    llm_model=model,
)
```

## Basic Streaming Loop

The continuation block iterates over events from `agent.run(..., stream=True)`. Each event is a `dict` with a `type` key:

```python
import asyncio

async def main():
    response_parts = []
    async for event in await agent.run("Tell me a short story about a robot", stream=True):
        if event["type"] == "response.output_text.delta":
            response_parts.append(event["delta"])
            print(event["delta"], end="", flush=True)
        elif event["type"] == "response.completed":
            print(f"\n\n[Finished: {event.get('finish_reason', 'unknown')}]")

    full_response = "".join(response_parts)
    return full_response

asyncio.run(main())
```

The key event type is `"response.output_text.delta"`, which carries a single token fragment in `event["delta"]`. Accumulate these to reconstruct the full text response.

## Filtering by Event Type

Filter on `event["type"]` to handle different events appropriately. Here's a comprehensive handler:

```python
import asyncio

async def main():
    output_texts = {}
    active_tool_calls = {}

    async for event in await agent.run("Search for the latest Python release date", stream=True):
        etype = event["type"]

        if etype == "response.output_text.delta":
            idx = event.get("index", 0)
            output_texts.setdefault(idx, [])
            output_texts[idx].append(event["delta"])
            print(event["delta"], end="", flush=True)

        elif etype == "response.output_item.added":
            name = event.get("name", "unknown")
            active_tool_calls[event["id"]] = {
                "call_id": event.get("call_id"),
                "name": name,
                "arguments": [],
            }
            print(f"\n[Tool call started: {name}]")

        elif etype == "response.function_call_arguments.delta":
            if event["id"] in active_tool_calls:
                active_tool_calls[event["id"]]["arguments"].append(
                    event["arguments"]
                )

        elif etype == "response.function_call_arguments.done":
            if event["id"] in active_tool_calls:
                tc = active_tool_calls[event["id"]]
                print(f"\n[Tool arguments: {''.join(tc['arguments'])}]")

        elif etype == "tool_call.ready":
            print(f"\n[Tool '{event['name']}' is ready for execution]")

        elif etype == "response.usage":
            usage = event["usage"]
            print(f"\n[Usage: {usage['total_tokens']} total tokens]")

        elif etype == "response.completed":
            print(f"\n[Stream completed: {event.get('finish_reason')}]")

        elif etype == "response.failed":
            print(f"\n[Stream failed: {event.get('error', 'unknown error')}]")

        elif etype == "response.cancelled":
            print("\n[Stream was cancelled]")

asyncio.run(main())
```

## Cancelling a Running Stream

Call `agent.cancel()` to abort an in-progress stream. This is useful for user-initiated stop buttons in UIs or timeout implementations:

```python
import asyncio

async def stream_with_cancel():
    task = asyncio.create_task(run_stream(agent))

    await asyncio.sleep(2.0)
    print("\n[Cancelling stream...]")
    agent.cancel()

    try:
        result = await task
    except Exception:
        print("[Stream cancelled as expected]")

async def run_stream(agent):
    output = []
    async for event in await agent.run(
        "Write a 1000-word essay on the history of computing",
        stream=True,
    ):
        if event["type"] == "response.output_text.delta":
            output.append(event["delta"])
            print(event["delta"], end="", flush=True)
        elif event["type"] == "response.cancelled":
            print("\n[Cancellation confirmed]")
            break
    return "".join(output)

asyncio.run(stream_with_cancel())
```

When `cancel()` is called, the SDK emits a `"response.cancelled"` event and stops the HTTP request. Any resources are released automatically.

## Complete Event Type Reference

The 15 canonical event types emitted during streaming, in typical order of occurrence:

| Event Type | Key Fields | Description |
|---|---|---|
| `response.created` | — | Stream session established |
| `response.in_progress` | — | Processing has begun |
| `response.output_text.delta` | `delta`, `index` | Text token fragment |
| `response.output_text.done` | `index` | One output text item finished |
| `response.output_item.added` | `id`, `call_id`, `name` | Tool call started |
| `response.function_call_arguments.delta` | `id`, `arguments` | Tool argument fragment |
| `response.function_call_arguments.done` | — | Tool arguments complete |
| `tool_call.ready` | `id`, `call_id`, `name`, `arguments` | Tool is ready to execute |
| `response.usage` | `usage` | Token usage info |
| `response.completed` | `finish_reason` | Stream completed successfully |
| `response.failed` | `error` | Stream failed with an error |
| `response.cancelled` | — | Stream was cancelled |
| `response.reasoning.delta` | `delta` | Reasoning token (reasoning models only) |
| `response.reasoning.done` | — | Reasoning phase complete (reasoning models only) |
| `error` | `error` | Unexpected error during stream processing |

Events are emitted in-order within each output item. Tool call events are nested between `response.output_item.added` and `response.function_call_arguments.done`.

## Common Pitfalls

1. **Forgetting `asyncio.run()`** — `agent.run()` with `stream=True` returns an `AsyncIterator`, not a coroutine. You must run it inside an async function wrapped with `asyncio.run()`. Writing `for event in agent.run(...)` without `async` will raise a `TypeError`.

2. **Assuming a single output item** — When agents use tools or generate mixed content, the SDK can produce multiple output items. Track the `index` field on deltas to avoid mixing text from different outputs.

3. **Not checking finish reasons** — The `"response.completed"` event carries a `finish_reason` field (`"stop"`, `"length"`, `"tool_calls"`, `"content_filter"`). Always check it to distinguish a clean completion from a truncated or filtered response.

## Next Steps

Learn how to attach **local files, byte data, and remote URLs** to agent queries in [File Attachments](./file-attachments.md).