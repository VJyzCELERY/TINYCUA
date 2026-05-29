# Your First Agent

**Prerequisites**: [Installation and Setup](./installation-and-setup.md) —
the SDK is installed and environment variables are configured.

## Overview

The `Agent` is the central abstraction in the TINYCUA SDK. It wraps a language
model, an optional set of tools, and configuration into a single callable
interface.

This page shows you how to create an agent, configure it for local or remote
providers, and run your first query.

## Creating an Agent

At minimum, an agent needs a **name** and **instructions** (system prompt).
Everything else has sensible defaults.

### Local Agent (Local LLM Server)

```python
from tinycua_sdk import Agent, LanguageModel

model = LanguageModel(
    provider="openai-compatible",
    model_name="qwen/qwen3.5-9b",
    base_url="http://localhost:1234/v1",
)

agent = Agent(
    name="hello-agent",
    instructions="You are a friendly assistant. Keep responses short.",
    llm_model=model,
)
```

If `LLM_BASE_URL` and `LLM_MODEL` are set in your environment, the defaults
suffice:

```python
from tinycua_sdk import Agent

agent = Agent(
    name="hello-agent",
    instructions="You are a friendly assistant. Keep responses short.",
    # llm_model defaults to LanguageModel(), reading LLM_MODEL, LLM_BASE_URL,
    # and api_key from the environment
)
```

### Remote Agent (OpenAI)

```python
import os

from tinycua_sdk import Agent, LanguageModel

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="hello-agent",
    instructions="You are a friendly assistant. Keep responses short.",
    llm_model=model,
)
```

For Chat Completions, swap the provider:

```python
import os

from tinycua_sdk import Agent, LanguageModel

model = LanguageModel(
    provider="openai-chat-completions",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="hello-agent",
    instructions="You are a friendly assistant. Keep responses short.",
    llm_model=model,
)
```

## Running the Agent

Once constructed, call `run()` with a query string (live LLM interaction):

```python
import asyncio

response = asyncio.run(agent.run("Say hello in three languages"))

print(response)
```

Example output:

```
Hello! / ¡Hola! / Bonjour!
```

### Streaming Responses

Enable streaming with `stream=True`:

```python
import asyncio

async def demo():
    async for event in await agent.run("Say hello in three languages", stream=True):
        print(event)

asyncio.run(demo())
```

Each event is a dictionary. To accumulate text content:

```python
import asyncio

async def main():
    content = ""
    async for event in await agent.run("Tell me a short joke", stream=True):
        if event["type"] == "response.output_text.delta":
            content += event.get("delta", "")
    print(content)

asyncio.run(main())
```

### Passing a Message History

```python
import asyncio

messages = [
    {"role": "user", "content": "What is the capital of France?"},
    {"role": "assistant", "content": "The capital of France is Paris."},
    {"role": "user", "content": "What is its population?"},
]

response = asyncio.run(agent.run(messages=messages))

print(response)
```

## Inspecting the Agent

```python
import os

from tinycua_sdk import Agent, LanguageModel

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="hello-agent",
    instructions="You are a friendly assistant. Keep responses short.",
    llm_model=model,
)

print(f"Name: {agent.name}")
print(f"Instructions: {agent.instructions}")
print(f"Model: {agent.llm_model.model_name if agent.llm_model else 'default'}")
print(f"Provider: {agent.llm_model.provider if agent.llm_model else 'default'}")
```

## Common Pitfalls

**`agent.run()` blocks indefinitely**. The default loop runs until the model
produces a final answer or hits a max-iteration guard. Press Ctrl+C to cancel,
or pass a policy with `max_tool_calls` to cap iterations.

**Streaming without `await`**. `agent.run(stream=True)` returns an async
iterator. Wrap in `asyncio.run()` for synchronous use:

```python
import asyncio

async def main():
    content = ""
    async for event in await agent.run("Hello", stream=True):
        if event["type"] == "response.output_text.delta":
            content += event.get("delta", "")
    print(content)

asyncio.run(main())
```

**Forgetting `python-dotenv`**. The SDK does not bundle it. Install with
`pip install python-dotenv` if you use `load_dotenv()`.

## Next Steps

- **[Agent Configuration](./agent-configuration.md)** — Learn `AgentConfig`,
  `AgentPolicy`, and serialization to JSON/YAML.

## See Also

- **[Creating Tools](../agent-extensions/creating-tools.md)** — Extend your
  agent with custom tools.