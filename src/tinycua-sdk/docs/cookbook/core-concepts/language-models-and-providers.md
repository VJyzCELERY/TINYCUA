# Language Models and Providers

**Prerequisites**: [Agent Configuration](../onboarding/agent-configuration.md)

## Overview

`LanguageModel` is the configuration object that controls which LLM provider and model your agent uses under the hood. It handles model name resolution from environment variables, API key auto-detection, and provider-specific tuning like temperature, max tokens, and system prompts.

TINYCUA SDK supports **two categories** of providers: **remote** (OpenAI via `openai-responses` or `openai-chat-completions`) and **local** (local LLM servers — OpenAI-compatible endpoints — via `openai-compatible`). You can switch between them by changing a single `provider` string — the rest of your agent code stays the same.

This page covers how to configure every `LanguageModel` field, understand provider differences, auto-resolve credentials from environment variables, and serialize configurations with `to_dict()`/`from_dict()`.

## Remote Providers

### OpenAI Responses API

The `openai-responses` provider uses OpenAI's stateful Responses API. It's the default and recommended for multi-turn conversations.

```python
import os
from tinycua_sdk import LanguageModel, Agent

remote_model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o",
    api_key=os.environ.get("OPENAI_API_KEY"),
    temperature=0.7,
    system_prompt="You are a precise, helpful coding assistant.",
)

agent = Agent(
    name="remote-agent",
    instructions="Answer user questions concisely.",
    llm_model=remote_model,
)
```

### OpenAI Chat Completions API

The `openai-chat-completions` provider uses the stateless Chat Completions API. It works with any OpenAI-compatible backend and gives you more control over message formatting.

```python
import os
from tinycua_sdk import LanguageModel, Agent

chat_model = LanguageModel(
    provider="openai-chat-completions",
    model_name="gpt-4o",
    api_key=os.environ.get("OPENAI_API_KEY"),
    temperature=0.5,
    max_tokens=4096,
    top_p=0.95,
)

agent = Agent(
    name="chat-agent",
    instructions="Answer user questions concisely.",
    llm_model=chat_model,
)
```

## Local Providers

### Local LLM Server / OpenAI-Compatible

Set `provider="openai-compatible"` and supply a `base_url` pointing to your local server. The `api_key` is optional for local servers that don't require authentication, but you can still pass one if needed.

```python
import os
from tinycua_sdk import LanguageModel, Agent

local_model = LanguageModel(
    provider="openai-compatible",
    model_name="llama-3.1-8b-instruct",
    base_url="http://localhost:1234/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
    temperature=0.7,
    max_tokens=2048,
)

agent = Agent(
    name="local-agent",
    instructions="Answer user questions concisely.",
    llm_model=local_model,
)
```

## LanguageModel Field Reference

### Provider and Connection

| Field | Type | Default | Description |
|---|---|---|---|
| `provider` | `str` | `"openai-responses"` | `"openai-responses"`, `"openai-chat-completions"`, or `"openai-compatible"` |
| `model_name` | `str` | `""` | Model identifier. Auto-resolved from env when empty |
| `base_url` | `str \| None` | `None` | Custom API endpoint URL (required for `openai-compatible`) |
| `api_key` | `str \| None` | `None` | API key string. Auto-detected from provider-specific env vars |

### Generation Parameters

| Field | Type | Default | Description |
|---|---|---|---|
| `temperature` | `float` | `1.0` | Sampling temperature (0.0 to 2.0) |
| `max_tokens` | `int \| None` | `None` | Maximum output tokens; `None` means provider default |
| `top_p` | `float` | `1.0` | Nucleus sampling parameter |
| `frequency_penalty` | `float` | `0.0` | Penalty for token frequency (-2.0 to 2.0) |
| `presence_penalty` | `float` | `0.0` | Penalty for token presence (-2.0 to 2.0) |

### Behavior

| Field | Type | Default | Description |
|---|---|---|---|
| `system_prompt` | `str` | `"You are a helpful assistant."` | System-level instruction injected into every request |
| `strip_thinking` | `bool` | `False` | Strips `thinking` content from reasoning model responses |
| `max_context` | `int` | `128000` | Maximum context window size in tokens |

## API Key Auto-Detection

When `api_key` is not explicitly set, `LanguageModel` checks these environment variables, ordered by priority:

| Provider | Env Vars Checked (in order) |
|---|---|
| `openai-responses` | `OPENAI_RESPONSES_API_KEY` → `OPENAI_API_KEY` |
| `openai-chat-completions` | `OPENAI_CHAT_COMPLETIONS_API_KEY` → `OPENAI_API_KEY` |
| `openai-compatible` | `OPENAI_COMPATIBLE_API_KEY` → `OPENAI_API_KEY` |

You can always override auto-detection by passing `api_key` explicitly.

## Model Name Auto-Resolution

When `model_name` is left empty (`""`) or not provided, `LanguageModel` resolves it from environment variables:

- `OPENAI_RESPONSES_MODEL` for `"openai-responses"`
- `OPENAI_CHAT_COMPLETIONS_MODEL` for `"openai-chat-completions"`
- `OPENAI_COMPATIBLE_MODEL` for `"openai-compatible"`

Example `.env` file leveraging auto-resolution:

```bash
OPENAI_API_KEY=sk-...
OPENAI_RESPONSES_MODEL=gpt-4o
OPENAI_CHAT_COMPLETIONS_MODEL=gpt-4o-mini
OPENAI_COMPATIBLE_MODEL=llama-3.1-8b-instruct
```

With these variables set, you can use the most minimal configuration:

```python
from tinycua_sdk import LanguageModel, Agent

model = LanguageModel(provider="openai-responses")

agent = Agent(
    name="minimal-agent",
    instructions="You are a helpful assistant.",
    llm_model=model,
)
```

All model resolution and API key detection happens automatically — no manual wiring needed.

## Serialization: to_dict() and from_dict()

`LanguageModel` supports full round-trip serialization. Use this to save configurations to JSON/YAML files or share them across agents:

```python
import os
from tinycua_sdk import LanguageModel

original = LanguageModel(
    provider="openai-chat-completions",
    model_name="gpt-4o",
    temperature=0.5,
    max_tokens=2048,
    top_p=0.95,
)

data = original.to_dict()
restored = LanguageModel.from_dict(data)

assert restored.provider == "openai-chat-completions"
assert restored.model_name == "gpt-4o"
assert restored.temperature == 0.5
assert restored.max_tokens == 2048
assert restored.top_p == 0.95
```

`to_dict()` returns a plain `dict` with all fields; `from_dict(data)` reconstructs the instance. Use this to save/load configurations from JSON files or programmatically compare model settings.

## Common Pitfalls

1. **Missing `base_url` for local providers** — When using `provider="openai-compatible"`, you must supply `base_url` (e.g., `"http://localhost:1234/v1"`). Without it, the SDK doesn't know where your local server is running and will fail at connection time.

2. **Wrong provider for your use case** — `openai-responses` is stateful and better for multi-turn conversations with automatic history management. `openai-chat-completions` is stateless and your code must manage the message list. Choose based on your application's architecture, not just the model name.

3. **Hardcoding API keys in source files** — Always use `os.environ.get("OPENAI_API_KEY")` or rely on `LanguageModel`'s built-in env var detection. This keeps secrets out of version control and works across development, CI, and production without code changes.

## Next Steps

Learn how to process **streaming responses** token-by-token in [Streaming Responses](./streaming-responses.md).