# Custom Providers

**Prerequisites**: [Responses Provider](./responses-provider.md) —
you understand how the built-in clients translate messages and handle API calls.

## Overview

The TINYCUA SDK supports custom LLM providers through the `ProviderRegistry`.
You can register your own provider factory — a callable that takes a
`LanguageModel` configuration and returns an `LLMClient` instance — and the
SDK will treat it like any built-in provider.

By the end of this page, you'll understand the `LLMClient` ABC, the
`ProviderFactory` protocol, provider alias resolution, and how to build and
register a custom provider.

## Architecture

The provider system has three layers:

1. **`LLMClient`** — Abstract base class. Your provider must implement
   `_chat_impl()` and `close()`.
2. **`ProviderFactory`** — Protocol: `Callable[[LanguageModel, upload_session], LLMClient]`.
   Your factory creates client instances.
3. **`ProviderRegistry`** — Singleton that maps provider IDs to factories.
   The SDK calls `registry.create_client(model_config)` to instantiate clients.

```
LanguageModel(provider="my-provider")
        |
        v
ProviderRegistry.create_client(model_config)
        |
        v
your_factory(model_config, upload_session=None) -> MyLLMClient
        |
        v
Agent calls client.chat(messages, tools)
```

## The LLMClient ABC

Every provider must implement `LLMClient`:

```python
from collections.abc import AsyncIterator
from typing import Any

from tinycua_sdk.agent.llm_client import LLMClient
from tinycua_sdk.agent.events import (
    LLMEvent,
    LLMMessage,
    LLMResponse,
    LLMToolSpec,
    RawSseEvent,
    TokenUsage,
)


class MyProviderClient(LLMClient):
    async def _chat_impl(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        stream: bool = False,
        raw_events: bool = False,
    ) -> (
        LLMResponse
        | AsyncIterator[LLMEvent]
        | AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]
    ):
        ...

    async def close(self) -> None:
        ...
```

The `_chat_impl` method receives canonical message types (`SystemMessage`,
`UserMessage`, `AssistantMessage`, `ToolResultMessage`) and must return:

- **Non-streaming** (`stream=False`): An `LLMResponse` dict with `content`,
  `tool_calls`, `usage`, `finish_reason`, and `model`.
- **Streaming** (`stream=True`): An async iterator yielding canonical
  `LLMEvent` items (or `(LLMEvent | None, RawSseEvent | None)` tuples
  when `raw_events=True`).

You don't need to override `chat()` — the ABC's concrete `chat()` validates
that `raw_events` requires `stream=True`, then delegates to `_chat_impl`.

## ProviderFactory Protocol

A factory is any callable matching this signature:

```python
from typing import Any, Protocol

from tinycua_sdk.agent.llm_client import LLMClient
from tinycua_sdk.agent.llm_model import LanguageModel


class ProviderFactory(Protocol):
    def __call__(
        self,
        model_config: LanguageModel,
        *,
        upload_session: Any | None = None,
    ) -> LLMClient: ...
```

It can be a function, a lambda, or a class with `__call__`. The `model_config`
provides the provider name, model name, API key, base URL, and all model
parameters. The `upload_session` is an optional `UploadSession` for file
upload caching — you can ignore it if your provider doesn't handle files.

## Full Example: Echo/Debug Provider

Here's a complete custom provider that echoes back messages instead of making
real API calls. It's useful for debugging, testing, or as a template.

```python
from collections.abc import AsyncIterator

from tinycua_sdk.agent.llm_client import LLMClient
from tinycua_sdk.agent.events import (
    ContentDeltaEvent,
    ContentDoneEvent,
    LLMEvent,
    LLMMessage,
    LLMResponse,
    LLMToolSpec,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseInProgressEvent,
    ResponseUsageEvent,
    TokenUsage,
)

ECHO_USAGE = TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0)


class EchoClient(LLMClient):
    def __init__(self, model_config):
        self._model_config = model_config

    async def close(self) -> None:
        pass

    async def _chat_impl(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        stream: bool = False,
        raw_events: bool = False,
    ) -> LLMResponse | AsyncIterator[LLMEvent]:
        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = str(msg.get("content", ""))
                break

        if not stream:
            return LLMResponse(
                content=f"[Echo] {last_user}",
                tool_calls=None,
                usage=ECHO_USAGE,
                finish_reason="stop",
                model=self._model_config.model_name,
            )

        return self._stream_response(f"[Echo] {last_user}")

    async def _stream_response(self, text: str) -> AsyncIterator[LLMEvent]:
        yield ResponseCreatedEvent(type="response.created")
        yield ResponseInProgressEvent(type="response.in_progress")

        for idx, char in enumerate(text.split()):
            yield ContentDeltaEvent(
                type="response.output_text.delta",
                delta=char + " ",
                index=idx,
            )

        yield ContentDoneEvent(type="response.output_text.done", index=0)
        yield ResponseUsageEvent(type="response.usage", usage=ECHO_USAGE)
        yield ResponseCompletedEvent(
            type="response.completed", finish_reason="stop",
        )
```

Now register it with the provider registry:

```python
from tinycua_sdk.providers.registry import get_provider_registry
from tinycua_sdk.providers.utility import ProviderInfo

registry = get_provider_registry()

def echo_factory(model_config, *, upload_session=None):
    return EchoClient(model_config)

registry.register(
    "echo",
    echo_factory,
    ProviderInfo(id="echo", factory=echo_factory, description="Echo debug provider"),
)
```

Use it like any built-in provider:

```python
import os

from tinycua_sdk import Agent, LanguageModel

model = LanguageModel(
    provider="echo",
    model_name="echo-v1",
)

agent = Agent(
    name="echo-agent",
    instructions="You are a helpful assistant.",
    llm_model=model,
)
```

## Provider Alias Resolution

The registry normalizes provider IDs through `resolve_provider()`, which
applies these alias mappings:

| Alias | Canonical ID |
|---|---|
| `"openai"` | `"openai-responses"` |
| `"lmstudio"` | `"openai-compatible"` |

When you call `registry.register("my-alias", factory)`, the alias is resolved
to its canonical form before storage. This means:

```python
from tinycua_sdk.providers.registry import get_provider_registry

registry = get_provider_registry()

print(registry.is_supported("openai"))          # True (resolved to openai-responses)
print(registry.is_supported("openai-responses")) # True
print(registry.is_supported("lmstudio"))          # True (resolved to openai-compatible)
print(registry.is_supported("openai-compatible")) # True
```

You can register additional aliases by calling `register()` with the alias
identifier:

```python
registry.register(
    "my-shortcut",
    echo_factory,
    ProviderInfo(
        id="my-shortcut",
        factory=echo_factory,
        description="Shortcut alias for echo provider",
    ),
)
```

Because `register()` internally calls `resolve_provider()` which uses the
built-in alias table, the registered identifier is canonical. For custom
aliases that aren't in the table, the identifier is used as-is.

## Working with the Singleton Registry

`get_provider_registry()` returns the singleton `ProviderRegistry`. It
lazily initializes and pre-registers `openai-responses` and
`openai-chat-completions`. For testing, you can reset it:

```python
from tinycua_sdk.providers.registry import ProviderRegistry, get_provider_registry

registry = get_provider_registry()

print("Registered providers:", [p.id for p in registry.list_providers()])

registry.reset()

print("After reset:", [p.id for p in registry.list_providers()])
```

## What Your Provider Must Handle

When implementing a production provider, you need to handle:

1. **Message translation** — Convert canonical messages to your provider's format.
   System messages, user messages with `ContentPart` lists, assistant messages
   with `tool_calls`, and tool-result messages with attachments.

2. **Tool spec translation** — Convert `LLMToolSpec` (name, description,
   parameters) to your provider's tool format.

3. **API key resolution** — Read from `model_config.api_key` or your
   provider-specific environment variable.

4. **Base URL resolution** — Support explicit `base_url` with a sensible default.

5. **Error handling** — Map provider errors to `ProviderApiError` or
   `ProviderAuthError` for consistent error handling upstream.

6. **Streaming normalization** — Emit canonical events in the expected order:
   `response.created` → `response.in_progress` → data events → `response.completed`.

## Common Pitfalls

**Forgetting to call `resolve_provider()` in your factory**. If your factory
doesn't call `resolve_provider()`, aliases like `"lmstudio"` won't work
correctly. The `register()` method handles this for you, so it's best to
register through `ProviderRegistry.register()`.

**Blocking in async methods**. `_chat_impl` is async. If your provider makes
synchronous HTTP calls, wrap them with `asyncio.to_thread()` or use an async
HTTP client. Blocking the event loop will stall the entire agent.

**Not clearing state in `close()`**. If your provider holds connections,
file handles, or caches, release them in `close()`. The `AgentExecutor`
calls `close()` on the client when the agent context exits.

## Next Steps

- **[Custom Execution Loops](../execution-and-reference/custom-execution-loops.md)** —
  Override `BaseLoop` to customize how the agent processes tool calls and
  manages iteration.
- **[Canonical Stream Events](../execution-and-reference/canonical-stream-events.md)** —
  Complete reference of all 15 event types your provider must emit.