# Responses Provider

**Prerequisites**: [Chat Completions Provider](./chat-completions-provider.md) —
you understand how the Chat Completions client handles message translation and
supported fields.

## Overview

The `OpenAIResponsesClient` provides access to OpenAI's Responses API — the
newer endpoint with native support for multimodal input items, stateful
conversations via `previous_response_id`, and server-side tool call handling.
It is the **default provider** when no explicit provider is specified.

**Local servers:** This provider targets the OpenAI Responses
endpoint (`/v1/responses`). If you are running a local LLM server or
Ollama that supports the Chat Completions-style API but not the Responses endpoint,
switch to `openai-compatible` (see
[Language Models and Providers](../core-concepts/language-models-and-providers.md)
for the full comparison). The streaming event shapes and tool-call handling differ
between the two, but the Agent interface is identical.

By the end of this page, you'll understand how the client translates input,
manages conversation state, which fields are unsupported, and how to construct
it directly.

## The Default Provider

When you create a `LanguageModel` without specifying a provider, `openai-responses`
is the default. Both of these are equivalent:

```python
import os

from tinycua_sdk import Agent, LanguageModel

model = LanguageModel(
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)
```

```python
import os

from tinycua_sdk import Agent, LanguageModel

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)
```

The alias `"openai"` also resolves to `openai-responses`:

```python
import os

from tinycua_sdk import Agent, LanguageModel

model = LanguageModel(
    provider="openai",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="default-assistant",
    instructions="You are a helpful assistant.",
    llm_model=model,
)
```

## Direct Client Construction

You can construct the client directly for inspection without live calls:

```python
import os

from tinycua_sdk import LanguageModel
from tinycua_sdk.providers.open_ai_responses import OpenAIResponsesClient

model_config = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

client = OpenAIResponsesClient(model_config)
```

Once constructed, the client is ready. The following block demonstrates a live
interaction using canonical messages:

```python
from tinycua_sdk.agent.events import LLMMessage, LLMToolSpec

messages: list[LLMMessage] = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is the capital of Japan?"},
]

tools: list[LLMToolSpec] | None = None

response = await client.chat(messages, tools)
print(f"Content: {response['content']}")
print(f"Model: {response.get('model')}")
print(f"Finish reason: {response.get('finish_reason')}")
```

## Input Item Translation

The `_translate_responses_input` method converts canonical messages to
Responses API `input` items:

| Canonical role | Responses `input` item |
|---|---|
| `system` | `{"role": "system", "content": "..."}` |
| `user` (string content) | `{"role": "user", "content": "..."}` |
| `user` (`ContentPart` list) | `{"role": "user", "content": [...]}` — text/image/file parts |
| `assistant` | `{"role": "assistant", "content": "..."}` |
| `tool_result` | `{"type": "function_call_output", "call_id": "...", "output": "..."}` |

### Multimodal Input Items

For user messages with `ContentPart` content, the client produces native
Responses input items:

- **`text` parts** → `{"type": "input_text", "text": "..."}`
- **`image_url` parts** → `{"type": "input_image", "image_url": "..."}` or inline data URL
- **`file` parts** → `{"type": "input_file", "file_id": "..."}` after upload

```python
from tinycua_sdk.models.attachment import ContentPart
from tinycua_sdk.agent.events import LLMMessage

messages: list[LLMMessage] = [
    {
        "role": "user",
        "content": [
            ContentPart(type="text", text="Summarize this document:"),
            ContentPart(
                type="file",
                file={"file_id": "file-abc123", "mime_type": "application/pdf"},
            ),
        ],
    },
]
```

### Function Call Output Handling

Tool results become `function_call_output` items. When a tool result contains
structured content (images, files), the client also generates synthetic
`user` role input items to carry that content — preserving call-id ordering:

```python
from tinycua_sdk.agent.events import LLMMessage

messages: list[LLMMessage] = [
    {
        "role": "tool_result",
        "call_id": "call_abc123",
        "content": "The user's profile image was retrieved successfully.",
        "attachments": [
            {
                "file_id": "file-xyz789",
                "mime_type": "image/png",
                "filename": "profile.png",
            },
        ],
    },
]
```

## Stateful Conversations

The client maintains a `_previous_response_id` that enables multi-turn
tool-call conversations. When the request `input` contains
`function_call_output` items (tool results), the client automatically
includes `previous_response_id` in the request payload, linking the
follow-up to the prior response.

This means you don't need to manually track response IDs — the client
handles it internally:

```python
from tinycua_sdk.agent.events import LLMMessage, LLMToolSpec

messages_1: list[LLMMessage] = [
    {"role": "user", "content": "Search for latest news about AI"},
]

tools: list[LLMToolSpec] = [
    {
        "name": "web_search",
        "description": "Search the web",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    },
]

response_1 = await client.chat(messages_1, tools)

messages_2: list[LLMMessage] = [
    {"role": "user", "content": "Search for latest news about AI"},
    {"role": "assistant", "content": None},
    {
        "role": "tool_result",
        "call_id": "call_search_1",
        "content": "Found 5 articles about AI advancements.",
    },
]

response_2 = await client.chat(messages_2, tools)
```

In the second call, the client detected `function_call_output` items and
included `previous_response_id` to maintain conversation continuity.

## Supported Fields

| Field | Responses API param | Notes |
|---|---|---|
| `temperature` | `temperature` | 0.0–2.0 |
| `max_tokens` | `max_output_tokens` | Renamed from `max_tokens` |
| `top_p` | `top_p` | Nucleus sampling |
| `response_format` | `text.format` | Mapped to nested `{"format": ...}` |
| `tool_choice` | `tool_choice` | `"auto"`, `"none"`, `"required"` |
| `top_logprobs` | `top_logprobs` | Number of top logprobs |
| `user` | `user` | End-user identifier |

### Unsupported Fields

The following `LanguageModel` fields raise `ProviderApiError` if set to a
non-default value. The Responses API does not support them:

| Field | Default value (must match) |
|---|---|
| `frequency_penalty` | `0.0` |
| `presence_penalty` | `0.0` |
| `stop` | `None` |
| `seed` | `None` |
| `logprobs` | `False` |

If you need these features, use the Chat Completions provider instead.

## API Key Resolution

The client resolves the API key in this order:

1. **Explicit** — `LanguageModel(api_key=...)` passed at construction
2. **`OPENAI_RESPONSES_API_KEY`** — environment variable
3. Falls back to empty string — the OpenAI SDK will NOT fall back to `OPENAI_API_KEY`

```python
import os

from tinycua_sdk import LanguageModel
from tinycua_sdk.providers.open_ai_responses import OpenAIResponsesClient

model_config = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_RESPONSES_API_KEY"),
)

client = OpenAIResponsesClient(model_config)
```

## Streaming and Event Normalization

The client normalizes raw Responses API SSE events into canonical events:

- `response.output_text.delta` / `response.output_text.done` — text content
- `response.output_item.added` — tool call started
- `response.function_call_arguments.delta` / `response.function_call_arguments.done` — tool arguments
- `response.created`, `response.in_progress`, `response.completed` — lifecycle
- `response.failed`, `response.cancelled` — error/cancellation
- `response.usage` — token usage
- `response.reasoning.delta` / `response.reasoning.done` — chain-of-thought tokens

The client also handles provider-specific edge cases: `reasoning_text.delta`
events from some models are normalized to `response.reasoning.delta`, and
`response.reasoning.summary` events are normalized to `response.reasoning.done`.

## Common Pitfalls

**Setting unsupported fields**. `frequency_penalty`, `presence_penalty`,
`stop`, `seed`, and `logprobs` must stay at their defaults. If you need
these features, switch to `openai-chat-completions`.

**Confusing API key resolution**. The Responses client does NOT fall back
to `OPENAI_API_KEY`. If you set `OPENAI_API_KEY` but the client can't
find `OPENAI_RESPONSES_API_KEY` and you didn't pass `api_key` explicitly,
calls will fail with an auth error.

**`previous_response_id` is automatic**. Unlike the Chat Completions
provider, where you must manually inject tool-call history, the Responses
provider tracks state via `previous_response_id`. Don't try to manage it
manually — the client does it for you.

## Next Steps

- **[Chat Completions Provider](./chat-completions-provider.md)** —
  Compare with the Chat Completions provider for a full picture.
- **[Custom Providers](./custom-providers.md)** — Build your own provider
  by implementing `LLMClient` and registering with `ProviderRegistry`.
