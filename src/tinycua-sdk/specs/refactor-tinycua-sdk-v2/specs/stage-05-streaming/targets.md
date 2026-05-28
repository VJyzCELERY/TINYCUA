# Stage 5: Streaming — Targets

## Purpose
Verify all four streaming modes work correctly. Uses a real or mock LLM server with SSE support.

---

### Target 5.1: stream="off" Returns String (Default)

**File:** `targets/01_stream_off.py`

```python
"""Target 5.1: Verify stream='off' returns a plain string."""

import asyncio
from tinycua_sdk import Agent, LanguageModel

BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "unsloth/qwen3.6-35b-a3b"


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
    )

    response = await a.run("Say hello.", stream="off")
    assert isinstance(response, str)
    print(f"[off] Final: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/01_stream_off_expected-output.txt` → `[off] Final: <any string>` (must not raise)

---

### Target 5.2: stream="token" Yields Token Deltas

**File:** `targets/02_stream_token.py`

```python
"""Target 5.2: Verify stream='token' yields token delta events."""

import asyncio
from tinycua_sdk import Agent, LanguageModel

BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "unsloth/qwen3.6-35b-a3b"


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
    )

    token_stream = await a.run("Count to 3.", stream="token")
    print("\n[token] Tokens:")
    async for chunk in token_stream:
        assert chunk["type"] == "response.output_text.delta"
        delta = chunk.get("delta", "")
        if delta:
            print(delta, end="", flush=True)
    print()


asyncio.run(main())
```

**Expected Output:** `targets/02_stream_token_expected-output.txt` → `[token] Tokens:\n<streamed text>` (must not raise)

---

### Target 5.3: stream="event" Yields Agent Events Only

**File:** `targets/03_stream_event.py`

```python
"""Target 5.3: Verify stream='event' yields agent events without token deltas."""

import asyncio
from tinycua_sdk import Agent, LanguageModel

BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "unsloth/qwen3.6-35b-a3b"


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
    )

    event_stream = await a.run("What is 2+2?", stream="event")
    print("\n[event] Events:")
    async for event in event_stream:
        # Should NOT contain .delta events
        assert not event["type"].endswith(".delta"), f"Unexpected delta event: {event['type']}"
        item_type = event.get("item", {}).get("type", "")
        print(f"  [{event['type']}]: {item_type}")


asyncio.run(main())
```

**Expected Output:** `targets/03_stream_event_expected-output.txt` → `[event] Events:\n<list of events>` (must not raise)

---

### Target 5.4: stream="all" Yields Both Tokens and Events

**File:** `targets/04_stream_all.py`

```python
"""Target 5.4: Verify stream='all' yields interleaved token deltas and agent events."""

import asyncio
from tinycua_sdk import Agent, LanguageModel

BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "unsloth/qwen3.6-35b-a3b"


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
    )

    mixed_stream = await a.run("Tell me a short fact.", stream="all")
    print("\n[all] Mixed stream:")
    async for item in mixed_stream:
        if item["type"].endswith(".delta"):
            delta = item.get("delta", "")
            if delta:
                print(delta, end="", flush=True)
        else:
            print(f"\n  [EVENT: {item['type']}]")
    print()


asyncio.run(main())
```

**Expected Output:** `targets/04_stream_all_expected-output.txt` → `[all] Mixed stream:\n<interleaved text and events>` (must not raise)
