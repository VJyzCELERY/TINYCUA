# Custom Execution Loops

**Prerequisites**: [Custom Providers](../provider-deep-dives/custom-providers.md) —
you understand how providers, the LLM client interface, and the registry work
together.

## Overview

The `BaseLoop` is the execution engine that drives the agent's conversation.
It manages the tool-calling cycle: send messages to the LLM, receive tool
calls, execute them, feed results back, repeat — until the LLM produces a
final answer or a limit is reached.

By the end of this page, you'll understand the loop's internals, how to
control iteration limits, how `AgentExecutor` orchestrates everything, and
how to build custom loops with logging, monitoring, or alternative strategies.

## BaseLoop Internals

`BaseLoop` has three responsibilities:

1. **Build the system message** (`build_system_message`) — combines agent
   instructions with skill instructions.
2. **Process tool calls** (`process_tool_calls`) — parses arguments,
   executes tools, appends results to the message list.
3. **Run the loop** (`run`) — the main entry point that dispatches to
   `_run_sync` (non-streaming) or `_run_stream` (streaming).

```
agent.run("query")
    |
    v
BaseLoop.run(agent, messages, tools, stream=False/True)
    |
    +--> stream=False:  # internal: _run_sync()
    |        loop until content or max_iterations:
    |            # internal: agent._call_llm(working, tools)
    |            if tool_calls: process_tool_calls()
    |            else: return content
    |
    +--> stream=True:  # internal: _run_stream()
             loop until content or max_iterations:
                 # internal: agent._call_llm(working, tools, stream=True)
                 yield events + execute tool calls
             yield response.completed
```

### build_system_message

Combines the agent's instructions with skill instructions into a single
system message:

```python
from tinycua_sdk import Agent, BaseLoop

loop = BaseLoop(max_iterations=5)

agent = Agent(
    name="helper",
    instructions="You are a helpful assistant.",
)

system_msg = loop.build_system_message(agent)
print(system_msg)
```

When skills are attached, they are appended with `[skill_name]\n{instructions}`
blocks. You can override instructions per-run with `override_instructions`:

```python
system_msg = loop.build_system_message(
    agent,
    override_instructions="You are an expert Python developer.",
)
```

### process_tool_calls

This method (and its streaming variant `process_stream_tool_calls`) handles
the tool execution pipeline:

```python
tool_call_count, max_reached = await loop.process_tool_calls(
    agent=agent,
    tools=tools,
    tool_calls=[{"name": "calculator", "arguments": '{"expression": "2+2"}'}],
    working_messages=working,
    tool_call_count=0,
    assistant_content="",
)
```

It does the following for each tool call:

1. Checks `agent.is_cancelled` before each call
2. Checks `tool_call_count >= agent.policy.max_tool_calls`
3. Parses arguments with `json.loads()`
4. Looks up the tool by name
5. Executes via `ToolExecutor.execute(tool, arguments, agent)`
6. Appends an assistant message (with tool_calls embedded) and tool result
   messages to `working_messages`

### last_assistant_content

Extracts the final content from the conversation:

```python
messages = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"},
    {"role": "user", "content": "What's up?"},
    {"role": "assistant", "content": "Not much!"},
]

final = loop.last_assistant_content(messages)
print(final)  # "Not much!"
```

## Controlling max_iterations

The default `max_iterations` is 5. This limits the number of LLM call rounds
in the main loop. To allow longer conversations, increase it:

```python
from tinycua_sdk import Agent, BaseLoop

loop = BaseLoop(max_iterations=20)

agent = Agent(
    name="long-runner",
    instructions="You are a persistent assistant.",
)
```

The loop exits with `"[max iterations reached]"` if the limit is hit before
the LLM produces a final answer.

## AgentExecutor: The Execution Engine

`AgentExecutor` is the execution engine that binds `Agent` configuration to
the `BaseLoop`. It manages:

- **LLM client creation** via `ProviderRegistry.create_client()`
- **Upload session** for file caching
- **Cancellation** via `cancel()` and `is_cancelled`
- **Resource cleanup** via `close()` (calls `client.close()`)

```python
from tinycua_sdk import Agent, AgentExecutor

agent = Agent(
    name="helper",
    instructions="You are a helpful assistant.",
)

executor = AgentExecutor(config=agent.to_config())

async with executor:
    pass
```

The executor supports async context manager — `close()` is called on exit:

```python
from tinycua_sdk import Agent, AgentExecutor

agent = Agent(
    name="helper",
    instructions="You are a helpful assistant.",
)

async with AgentExecutor(config=agent.to_config()) as executor:
    pass
```

## Building a Custom Loop

Subclass `BaseLoop` and override `run()` to add logging, metrics, or
alternative strategies. Here's a loop that logs each iteration:

```python
import logging
from collections.abc import AsyncIterator
from typing import Any

from tinycua_sdk import Agent, BaseLoop
from tinycua_sdk.tools.decorators import Tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LoggingLoop(BaseLoop):
    async def run(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        override_instructions: str | None = None,
        stream: bool = False,
    ) -> str | AsyncIterator[dict[str, Any]]:
        logger.info("Starting agent '%s' with %d tools", agent.name, len(tools))
        logger.info("Max iterations: %d", self.max_iterations)

        if not stream:
            result = await self._run_sync(agent, messages, tools, override_instructions)
            logger.info("Agent '%s' finished: %.50s...", agent.name, str(result)[:50])
            return result

        async def logged_stream() -> AsyncIterator[dict[str, Any]]:
            iteration = 0
            async for event in self._run_stream(
                agent, messages, tools, override_instructions,
            ):
                yield event
                if event.get("type") == "response.completed":
                    iteration += 1
                    logger.info(
                        "Agent '%s' iteration %d completed: %s",
                        agent.name, iteration, event.get("finish_reason"),
                    )

        return logged_stream()
```

Use your custom loop by passing it to the agent or calling its methods
directly:

```python
loop = LoggingLoop(max_iterations=10)

agent = Agent(
    name="logged-agent",
    instructions="You are a helpful assistant.",
)
```

## Custom Loop with Tool Execution Hooks

You can also override `process_tool_calls` to intercept tool execution:

```python
import asyncio
import json
from typing import Any

from tinycua_sdk import Agent, BaseLoop
from tinycua_sdk.tools.decorators import Tool


class AuditLoop(BaseLoop):
    async def process_tool_calls(
        self,
        agent: Agent,
        tools: list[Tool],
        tool_calls: list[dict[str, Any]],
        working_messages: list[dict[str, Any]],
        tool_call_count: int,
        assistant_content: str = "",
    ) -> tuple[int, bool]:
        print(f"=== Tool calls requested (iteration {tool_call_count // max(1, len(tool_calls))}) ===")
        for tc in tool_calls:
            print(f"  Tool: {tc['name']}")
            print(f"  Args: {tc['arguments']}")

        result = await super().process_tool_calls(
            agent, tools, tool_calls, working_messages,
            tool_call_count, assistant_content,
        )

        print(f"  Results appended. New tool count: {result[0]}")
        return result
```

## Stream Iteration Details

The streaming path (`_run_stream`) is more complex than sync. Key details:

- **First chunk handling**: The first stream chunk determines the initial
  lifecycle events. If it's a data event, synthetic `response.created` and
  `response.in_progress` are emitted before it.
- **Cumulative usage**: Token counts are accumulated across all LLM calls
  within the run, deduplicating by response ID.
- **Intermediate completions suppressed**: `response.completed` with
  `finish_reason="tool_calls"` from intermediate LLM calls are suppressed
  so consumers only see one terminal completion.
- **Cancellation**: `agent.is_cancelled` is checked between tool calls,
  and `response.cancelled` is yielded on cancellation.

## Common Pitfalls

**Not passing tools to subclasses**. When overriding `run()`, you must
forward `tools` to the parent methods so tool execution works. The
`process_tool_calls` method looks up tools from the list you pass.

**Ignoring max_iterations**. The default of 5 may be too low for multi-turn
tool conversations. If your agent hits `"[max iterations reached]"`,
increase `max_iterations` or adjust `max_tool_calls` in the agent policy.

**Streaming: mixing sync and async**. `_run_sync` returns a `str`, while
`_run_stream` returns an `AsyncIterator[dict]`. If you override `run()`,
make sure your return type matches the `stream` parameter to avoid
surprising consumers who iterate over a string.

## Next Steps

- **[Canonical Stream Events](./canonical-stream-events.md)** — Complete
  reference of all 15 event types that flow through the execution loop.
- **[Error Handling](./error-handling.md)** — Catch and handle provider
  errors, authentication failures, and cancellations.