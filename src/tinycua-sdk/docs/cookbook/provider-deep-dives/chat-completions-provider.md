# Chat Completions Provider

> **Advanced**: This page uses internal SDK modules for deep provider
> exploration. These import paths (`tinycua_sdk.providers.*`) are not part
> of the stable public API and may change between minor versions. For
> production code, use the high-level `LanguageModel` and `Agent` APIs
> demonstrated in earlier pages.

**Prerequisites**: [Tool Results with Files](../advanced-file-handling/tool-results-with-files.md) —
you understand how tools return content and how multipart results flow through the system.

## Overview

The `OpenAIChatCompletionsClient` provides access to OpenAI's Chat Completions
API and any OpenAI-compatible endpoint (local LLM servers, self-hosted vLLM).
It translates the SDK's canonical message and tool formats into the Chat
Completions wire format, handles multi-turn tool-call conversations, and
normalizes streaming deltas into canonical events.

By the end of this page, you'll understand how the client translates messages,
which `LanguageModel` fields are supported, and how to construct and configure
the client directly.

## Selecting the Provider

Use `LanguageModel(provider="openai-chat-completions")` to route through this
provider — ideal for both remote OpenAI and local LLM servers (set
`base_url` to your local server).

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
    name="chat-assistant",
    instructions="You are a helpful assistant.",
    llm_model=model,
)
```

For local LLM servers, use `openai-chat-completions` with your local server URL:

```python
from tinycua_sdk import Agent, LanguageModel

model = LanguageModel(
    provider="openai-chat-completions",
    model_name="qwen/qwen3.5-9b",
    base_url="http://localhost:1234/v1",
)

agent = Agent(
    name="local-chat-assistant",
    instructions="You are a helpful assistant.",
    llm_model=model,
)
```

## Direct Client Construction

You can construct the client directly for inspection without making live calls:

```python
import os

from tinycua_sdk import LanguageModel
from tinycua_sdk.providers.open_ai_chat_completions import OpenAIChatCompletionsClient

model_config = LanguageModel(
    provider="openai-chat-completions",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

client = OpenAIChatCompletionsClient(model_config)
```

For a local one:

```python
from tinycua_sdk import LanguageModel
from tinycua_sdk.providers.open_ai_chat_completions import OpenAIChatCompletionsClient

model_config = LanguageModel(
    provider="openai-chat-completions",
    model_name="qwen/qwen3.5-9b",
    base_url="http://localhost:1234/v1",
)

client = OpenAIChatCompletionsClient(model_config)
```

Once constructed, the client is ready to call the LLM.

> **Live call**: The following snippet calls the LLM. Ensure your API key is
> set before running. See [Language Models and Providers](../core-concepts/language-models-and-providers.md)
> for environment variable setup.

It builds canonical messages, configures tools, and sends a non-streaming
chat request:

```python
import asyncio

from tinycua_sdk.agent.events import LLMMessage, LLMToolSpec


async def main():
    messages: list[LLMMessage] = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is 15 + 27?"},
    ]

    tools: list[LLMToolSpec] | None = None

    response = await client.chat(messages, tools)
    print(f"Content: {response['content']}")
    print(f"Model: {response.get('model')}")
    print(f"Finish reason: {response.get('finish_reason')}")


asyncio.run(main())
```

## Message Translation

`OpenAIChatCompletionsClient` translates canonical message types to the Chat
Completions format:

| Canonical role | Chat Completions format |
|---|---|
| `system` | `role: "system"` — passes through unchanged |
| `user` (string content) | `role: "user"` with `content` as plain string |
| `user` (`ContentPart` list) | Multi-part user message with text + image/file parts |
| `assistant` | `role: "assistant"` — passes through unchanged |
| `assistant` (with `tool_calls`) | `role: "assistant"` with embedded `tool_calls` array |
| `tool_result` | `role: "tool"` with `tool_call_id` and `content` |

### ContentPart Translation

User messages carrying `ContentPart` items are translated to multimodal Chat
Completions content:

- **`text` parts** → `{"type": "text", "text": "..."}`
- **`image_url` / `image` parts** → `{"type": "image_url", "image_url": {"url": "data:image/..."}}`
- **`file` parts** (non-image) → uploaded via `/v1/files`, referenced by `file_id` as `{"type": "file", "file": {"file_id": "..."}}`

```python
from tinycua_sdk import FileAttachment
from tinycua_sdk.models.attachment import ContentPart
from tinycua_sdk.agent.events import LLMMessage

messages: list[LLMMessage] = [
    {
        "role": "user",
        "content": [
            ContentPart(type="text", text="Describe this image:"),
            ContentPart(
                type="file",
                file=FileAttachment.from_url(
                    "https://example.com/photo.jpg",
                    mime_type="image/jpeg",
                ),
            ),
        ],
    },
]
```

### Tool-Result Synthetic Messages

Chat Completions requires text-only `tool` role messages. When a tool result
returns structured content (e.g., `list[ContentPart]` or `FileAttachment`
references), the client generates synthetic user-type messages to carry that
content. The tool-result batch is emitted with `role: "tool"` first, then any
deferred multimodal content follows as `role: "user"` messages.

## Supported Fields

The following `LanguageModel` fields are mapped to the Chat Completions
request payload:

| Field | Chat Completions param | Notes |
|---|---|---|
| `temperature` | `temperature` | 0.0–2.0 |
| `max_tokens` | `max_tokens` | Max completion tokens |
| `top_p` | `top_p` | Nucleus sampling |
| `frequency_penalty` | `frequency_penalty` | -2.0–2.0 |
| `presence_penalty` | `presence_penalty` | -2.0–2.0 |
| `stop` | `stop` | Stop sequence(s) |
| `seed` | `seed` | Deterministic sampling seed |
| `response_format` | `response_format` | `"text"` or `"json_object"` or `{"type": "json_schema", ...}` |
| `tool_choice` | `tool_choice` | `"auto"`, `"none"`, `"required"`, or specific function |
| `logprobs` | `logprobs` | Return log probabilities |
| `top_logprobs` | `top_logprobs` | Number of top logprobs to return |
| `user` | `user` | End-user identifier for abuse monitoring |

Fields not listed above are silently ignored.

> **Advanced fields**: `stop`, `seed`, `response_format`, `tool_choice`, `logprobs`,
> `top_logprobs`, and `user` are available for advanced use cases. See the
> [OpenAI Chat Completions API reference](https://platform.openai.com/docs/api-reference/chat)
> for per-field documentation and usage examples. The cookbook covers the
> most commonly used subset (`temperature`, `max_tokens`, `top_p`, penalties).

## API Key Resolution

The client resolves the API key in this order:

1. **Explicit** — `LanguageModel(api_key=...)` passed at construction
2. **`OPENAI_CHAT_COMPLETIONS_API_KEY`** — environment variable (provider-specific)
3. Falls back to empty string

> **Note**: When using `LanguageModel` at the agent level, `OPENAI_API_KEY` is
> resolved as a fallback before the key is passed to the client (see
> [Language Models and Providers](../core-concepts/language-models-and-providers.md)).
> At the raw client level, only the explicit key or provider-specific env var is read.

## Base URL Resolution

Base URL is resolved as:

1. **Explicit** — `LanguageModel(base_url=...)` passed at construction
2. **`OPENAI_CHAT_COMPLETIONS_BASE_URL`** — environment variable
3. **`LLM_BASE_URL`** — generic fallback
4. **`https://api.openai.com/v1`** — default

```python
import os

from tinycua_sdk import LanguageModel
from tinycua_sdk.providers.open_ai_chat_completions import OpenAIChatCompletionsClient

model_config = LanguageModel(
    provider="openai-chat-completions",
    model_name="gpt-4o-mini",
    base_url=os.environ.get("OPENAI_CHAT_COMPLETIONS_BASE_URL"),
    api_key=os.environ.get("OPENAI_CHAT_COMPLETIONS_API_KEY"),
)

client = OpenAIChatCompletionsClient(model_config)
```

## Streaming and Tool Call Accumulation

When streaming, the client uses `ChoiceAccumulator` and `ToolCallAccumulator`
to track per-choice state across delta chunks. It emits canonical events:

- `response.output_text.delta` — text content deltas
- `response.output_text.done` — text content block complete
- `response.output_item.added` — tool call started (synthesized from first chunk)
- `response.function_call_arguments.delta` — tool argument fragments
- `response.function_call_arguments.done` — tool arguments complete
- `tool_call.ready` — tool call ready for execution
- `response.usage` — token usage (accumulated from the completion chunk)

The client handles OpenAI's Chat Completions edge cases: null deltas,
multiple tool calls in a single chunk, non-sequential tool call index
arrival, and optional `finish_reason` appearance timing.

## Common Pitfalls

**Using Responses-only parameters with Chat Completions**. The Chat
Completions provider silently ignores parameters not listed in the Supported
Fields table above (e.g., `parallel_tool_calls` directive from the Responses
conversation state model). Always check the table to confirm which parameters
your chosen provider accepts.

**Missing tool-result synthetic messages**. When a tool returns structured
content (images or files), the Chat Completions client generates extra
user-type messages after the `tool` role messages to carry that content.
Your message history will grow more than expected — this is normal.

**Provider aliases use different clients**. `openai-chat-completions` uses
`OpenAIChatCompletionsClient`. The `openai-responses` provider uses a
different client (`OpenAIResponsesClient`) with distinct behavior.

## Next Steps

- **[Responses Provider](./responses-provider.md)** — Deep dive into
  `OpenAIResponsesClient` and the Responses API provider.

## See Also

- **[Custom Providers](./custom-providers.md)** — Build your own provider
  by implementing the `LLMClient` ABC.