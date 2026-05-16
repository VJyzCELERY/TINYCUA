# Stage 5: Streaming — Targets

## Purpose
Verify streaming works correctly. Uses a real or mock LLM server with SSE support.

---

### Target 5.1: stream=False Returns String (Default)

**File:** `targets/01_stream_off.py`

```python
"""Target 5.1: Verify stream=False returns a plain string."""

import asyncio
from tinycua_sdk import Agent, LanguageModel

BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "qwen/qwen3.5-9b"


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
    )

    response = await a.run("Say hello.", stream=False)
    assert isinstance(response, str)
    print(f"[stream=False] Final: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/01_stream_off_expected-output.txt` → `[stream=False] Final: <any string>` (must not raise)

---

### Target 5.2: stream=True Yields Raw Events

**File:** `targets/02_stream_true.py`

```python
"""Target 5.2: Verify stream=True yields raw SSE events."""

import asyncio
from tinycua_sdk import Agent, LanguageModel

BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "qwen/qwen3.5-9b"


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
    )

    stream = await a.run("Count to 3.", stream=True)
    print("[stream] Events:")
    async for event in stream:
        print(f"  [{event['type']}]: {event}")


asyncio.run(main())
```

**Expected Output:** `targets/02_stream_true_expected-output.txt` → `[stream] Events:\n<list of raw events>` (must not raise)
