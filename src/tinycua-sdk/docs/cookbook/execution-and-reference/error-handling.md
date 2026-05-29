# Error Handling

**Prerequisites**: [Canonical Stream Events](./canonical-stream-events.md) —
you understand stream events, the `LLMResponse` structure, and how the
execution loop processes responses.

## Overview

The TINYCUA SDK raises three provider-specific exception classes during
LLM operations. Understanding when each is raised and how to handle them
lets you build resilient agents that recover from transient failures,
handle authentication issues gracefully, and degrade with clear error
messages.

By the end of this page, you'll know how to catch and recover from each
error type, implement retry logic, handle cancellations, and use the async
context manager for clean resource lifecycle.

## Error Class Hierarchy

```
Exception
├── ProviderAuthError       — wrong/missing API key (401, 403, credential keywords)
├── ProviderApiError         — non-auth API errors (rate limits, server errors, bad requests)
└── ValueError
    └── ProviderNotSupportedError   — unknown provider ID
```

## ProviderAuthError

Raised when provider authentication fails — wrong API key, missing key,
expired credentials, or any 401/403 response. Also raised when the error
message contains `"auth"` or `"credential"` regardless of status code.

```python
from tinycua_sdk.core.exceptions import ProviderAuthError

def check_auth():
    raise ProviderAuthError("Invalid API key")
```

Catch it to differentiate authentication issues from other errors:

```python
import os

from tinycua_sdk import Agent, LanguageModel
from tinycua_sdk.core.exceptions import ProviderAuthError

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="test-agent",
    instructions="You are a helpful assistant.",
    llm_model=model,
)

try:
    response = asyncio.run(agent.run("Hello"))
except ProviderAuthError as e:
    print(f"Authentication failed: {e}")
    print("Check your API key and environment variables.")
```

## ProviderApiError

Raised for non-auth API errors. This includes rate limits (429), server
errors (5xx), bad requests (400), and provider-specific error conditions.
The exception carries a `status_code` and a `message`:

```python
from tinycua_sdk.core.exceptions import ProviderApiError

def simulate_rate_limit():
    raise ProviderApiError(429, "Rate limit exceeded. Try again in 30 seconds.")
```

Catch and inspect the status code to decide recovery strategy:

```python
from tinycua_sdk.core.exceptions import ProviderApiError

try:
    response = asyncio.run(agent.run("Summarize this long document..."))
except ProviderApiError as e:
    if e.status_code == 429:
        print(f"Rate limited! {e.message}")
    elif e.status_code >= 500:
        print(f"Server error ({e.status_code}): {e.message}")
    else:
        print(f"API error [{e.status_code}]: {e.message}")
```

## ProviderNotSupportedError

Raised when you request a provider that isn't registered. The exception
includes the requested `provider_id` and a `supported_list` of registered
providers:

```python
from tinycua_sdk.core.exceptions import ProviderNotSupportedError

def show_supported():
    raise ProviderNotSupportedError(
        "my-custom-provider",
        supported_list=["openai-responses", "openai-chat-completions"],
    )
```

Catch it to provide helpful error messages:

```python
import os

from tinycua_sdk import Agent, LanguageModel
from tinycua_sdk.core.exceptions import ProviderNotSupportedError

model = LanguageModel(
    provider="unknown-provider",
    model_name="some-model",
    base_url="https://api.example.com/v1",
    api_key=os.environ.get("SOME_API_KEY"),
)

agent = Agent(
    name="test-agent",
    instructions="You are a helpful assistant.",
    llm_model=model,
)

try:
    response = asyncio.run(agent.run("Hello"))
except ProviderNotSupportedError as e:
    print(f"Provider '{e.provider_id}' is not supported.")
    if e.supported_list:
        print(f"Available: {', '.join(e.supported_list)}")
```

## Comprehensive Error Handler

Combine all three into a single handler that differentiates recovery
strategies:

```python
import os

from tinycua_sdk import Agent, LanguageModel
from tinycua_sdk.core.exceptions import (
    ProviderApiError,
    ProviderAuthError,
    ProviderNotSupportedError,
)

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="resilient-agent",
    instructions="You are a helpful assistant.",
    llm_model=model,
)

try:
    response = asyncio.run(agent.run("What is the weather today?"))
    print(response)
except ProviderNotSupportedError as e:
    print(f"Provider not supported: {e.provider_id}")
    print(f"Available: {e.supported_list}")
except ProviderAuthError as e:
    print(f"Authentication error: {e}")
except ProviderApiError as e:
    if e.status_code == 429:
        print(f"Rate limited: {e}")
    elif e.status_code == 400:
        print(f"Bad request: {e}")
    elif e.status_code >= 500:
        print(f"Server error: {e}")
    else:
        print(f"API error [{e.status_code}]: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Retry with tenacity

For transient errors (rate limits, server errors), use `tenacity` to retry
with exponential backoff:

```python
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from tinycua_sdk.core.exceptions import ProviderApiError

def is_retryable(exception: Exception) -> bool:
    if isinstance(exception, ProviderApiError):
        return exception.status_code in (429, 500, 502, 503, 504)
    return False

@retry(
    retry=retry_if_exception(is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
async def call_with_retry(agent, query: str) -> str:
    return await agent.run(query)

# Usage:
# result = asyncio.run(call_with_retry(agent, "What is AI?"))
```

> **Note**: Tenacity 8.x+ natively supports `@retry` on async functions. For
> earlier versions, or a dependency-free alternative, use the manual retry
> pattern below.

A simpler pattern with manual retry for any `ProviderApiError`:

```python
import asyncio

from tinycua_sdk.core.exceptions import ProviderApiError

MAX_RETRIES = 3

async def call_with_manual_retry(agent, query: str) -> str:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await agent.run(query)
        except ProviderApiError as e:
            last_error = e
            delay = 2 ** attempt
            print(f"Attempt {attempt} failed [{e.status_code}]: {e}")
            await asyncio.sleep(delay)
    raise last_error

# Usage:
# result = asyncio.run(call_with_manual_retry(agent, "What is AI?"))
```

## Cancellation Handling

The agent supports cooperative cancellation. Calling `agent.cancel()` sets
the `is_cancelled` flag and signals the cancellation event. The execution
loop checks `is_cancelled` before each tool call and between iterations.

### Cancel an In-Progress Run

```python
import asyncio

async def cancel_after_timeout(agent, query: str, timeout: float) -> str:
    task = asyncio.ensure_future(agent.run(query))
    try:
        result = await asyncio.wait_for(task, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        agent.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return "[cancelled]"
```

### Handling CancelledError

The execution loop raises `asyncio.CancelledError` when cancellation is
detected. Catch it to perform cleanup:

```python
try:
    response = asyncio.run(agent.run("A very long query..."))
except asyncio.CancelledError:
    print("Agent run was cancelled.")
except Exception as e:
    print(f"Error: {e}")
```

## Streaming Error Handling

When streaming (`stream=True`), errors are emitted as stream events rather
than raised as exceptions. The agent loop emits:

- `response.failed` for provider-level failures during streaming
- `error` for unexpected exceptions caught in the stream body
- `response.cancelled` for cancellation during streaming

```python
async def stream_with_error_handling(agent, query: str):
    seen_error = False
    async for event in await agent.run(query, stream=True):
        event_type = event.get("type", "")

        if event_type == "response.failed":
            error = event.get("error", {})
            print(f"Stream failed: {error.get('message', 'Unknown error')}")
            seen_error = True

        elif event_type == "error":
            error = event.get("error", {})
            print(f"Stream error: {error.get('message', 'Unknown error')}")
            seen_error = True

        elif event_type == "response.cancelled":
            print("Stream was cancelled.")
            seen_error = True

        elif event_type == "response.output_text.delta":
            if not seen_error:
                print(event.get("delta", ""), end="", flush=True)
```

## Async Context Manager

`AgentExecutor` supports `async with` for automatic cleanup. The `close()`
method is called on exit, closing the underlying LLM client and upload
session:

```python
import asyncio

from tinycua_sdk import Agent, LanguageModel, AgentExecutor

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
)

agent = Agent(
    name="context-agent",
    instructions="You are a helpful assistant.",
    llm_model=model,
)

async def main():
    async with AgentExecutor(config=agent.to_config()) as executor:
        try:
            response = await agent.run("Hello")
            print(response)
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(main())
```

The context manager ensures the OpenAI client connection is closed, even if
exceptions are raised during execution.

## Error Scenarios: Local vs Remote

### Local (local LLM server / openai-compatible)

```python
from tinycua_sdk import Agent, LanguageModel
from tinycua_sdk.core.exceptions import (
    ProviderApiError,
    ProviderAuthError,
    ProviderNotSupportedError,
)

model = LanguageModel(
    provider="openai-compatible",
    model_name="qwen/qwen3.5-9b",
    base_url="http://localhost:1234/v1",
)

agent = Agent(
    name="local-agent",
    instructions="You are a local assistant.",
    llm_model=model,
)

try:
    response = asyncio.run(agent.run("Hello"))
except ProviderNotSupportedError as e:
    print(f"Provider error: {e} — check provider spelling")
except ProviderAuthError as e:
    print(f"Auth error: {e} — local servers usually don't need keys")
except ProviderApiError as e:
    if e.status_code == 0 and "Connection" in e.message:
        print("Local server not running — start the server on port 1234")
    else:
        print(f"API error: {e}")
```

### Remote (OpenAI)

```python
import os

from tinycua_sdk import Agent, LanguageModel
from tinycua_sdk.core.exceptions import (
    ProviderApiError,
    ProviderAuthError,
    ProviderNotSupportedError,
)

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="remote-agent",
    instructions="You are a remote assistant.",
    llm_model=model,
)

try:
    response = asyncio.run(agent.run("Hello"))
except ProviderNotSupportedError as e:
    print(f"Provider not supported: {e} — did you mean 'openai'?")
except ProviderAuthError as e:
    print(
        f"Authentication error: {e} — check OPENAI_API_KEY "
        "or OPENAI_RESPONSES_API_KEY"
    )
except ProviderApiError as e:
    if e.status_code == 429:
        print(f"Rate limited: {e} — back off and retry")
    elif e.status_code == 400:
        print(f"Bad request: {e} — check model name and parameters")
    elif e.status_code >= 500:
        print(f"OpenAI server error [{e.status_code}]: {e}")
    else:
        print(f"API error: {e}")
```

## Common Pitfalls

**Confusing API key resolution at the client vs. LanguageModel level**.
At the raw client level, the Chat Completions client reads
`OPENAI_CHAT_COMPLETIONS_API_KEY` and the Responses client reads
`OPENAI_RESPONSES_API_KEY` — neither falls back to `OPENAI_API_KEY` on its own.
However, `LanguageModel` resolves `OPENAI_API_KEY` as a fallback *before*
passing the key to the client (see [Language Models and
Providers](../core-concepts/language-models-and-providers.md)). If you
construct raw clients directly without `LanguageModel`, set the
provider-specific env var or pass `api_key` explicitly.

**Not catching `asyncio.CancelledError` in streaming loops**. If you wrap
`agent.run(stream=True)` in a try/except, you must catch
`asyncio.CancelledError` separately. The execution loop uses cancellation
for normal shutdown, and letting it propagate uncaught will crash your app.

**Retrying non-retryable errors**. 400 errors (bad request) and 401 errors
(unauthorized) won't resolve with retries. Only retry 429 (rate limit) and
5xx (server errors). The `@retry` decorator above only retries with
`is_retryable()` — use a similar filter in your own code.

## Related Topics

You've completed the TINYCUA SDK Cookbook. Here are related topics for deeper exploration:

- **[Custom Execution Loops](./custom-execution-loops.md)** — Override
  `BaseLoop` to add error handling at the loop level.
- **[Canonical Stream Events](./canonical-stream-events.md)** — Understand
  how `response.failed` and `error` events flow in the stream.
- **[Custom Providers](../provider-deep-dives/custom-providers.md)** —
  Raise `ProviderApiError` and `ProviderAuthError` from your custom
  provider for consistent error handling.