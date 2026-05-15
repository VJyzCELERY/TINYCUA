# Stage 8: Extensibility — Custom Loops — Targets

## Purpose
Verify `BaseLoop` can be subclassed for custom execution behavior. Uses a real or mock LLM server.

---

### Target 8.1: Minimal Custom Loop Override

**File:** `targets/01_minimal_custom_loop.py`

```python
"""Target 8.1: Verify subclassing BaseLoop and passing to Agent uses the custom loop."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, BaseLoop


class MyLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream: bool = False):
        return "custom result"


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        loop=MyLoop(),
    )

    response = await a.run("Hello")
    assert response == "custom result"
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/01_minimal_custom_loop_expected-output.txt` → `Response: custom result` (must not raise)

---

### Target 8.2: Custom Loop Accesses LLM via _call_llm

**File:** `targets/02_custom_loop_calls_llm.py`

```python
"""Target 8.2: Verify custom loop can call agent._call_llm()."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, BaseLoop


class LLMLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream: bool = False):
        response = await agent._call_llm(messages)
        return response.get("content", "") or "[no content]"


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        loop=LLMLoop(),
    )

    response = await a.run("Say hi.", stream=False)
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/02_custom_loop_calls_llm_expected-output.txt` → `Response: <any string>` (must not raise)

---

### Target 8.3: Cancellation Respected in Custom Loop

**File:** `targets/03_custom_loop_cancellation.py`

```python
"""Target 8.3: Verify custom loop respects agent.is_cancelled."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, BaseLoop


class SlowLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream: bool = False):
        for i in range(100):
            if agent.is_cancelled:
                return "[cancelled]"
            await asyncio.sleep(0.01)
        return "done"


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        loop=SlowLoop(),
    )

    task = asyncio.create_task(a.run("Wait"))
    await asyncio.sleep(0.05)
    a.cancel()

    response = await task
    assert response == "[cancelled]"
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/03_custom_loop_cancellation_expected-output.txt` → `Response: [cancelled]` (must not raise)

---

### Target 8.4: max_iterations Respected in Custom Loop

**File:** `targets/04_custom_loop_max_iterations.py`

```python
"""Target 8.4: Verify custom loop respects self.max_iterations."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, BaseLoop


class CountingLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream: bool = False):
        count = 0
        for _ in range(self.max_iterations):
            count += 1
        return f"ran {count} times"


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        loop=CountingLoop(max_iterations=3),
    )

    response = await a.run("Hello")
    assert response == "ran 3 times"
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/04_custom_loop_max_iterations_expected-output.txt` → `Response: ran 3 times` (must not raise)

---

### Target 8.5: ReActLoop Example Works

**File:** `targets/05_react_loop.py`

```python
"""Target 8.5: Verify a ReAct-style custom loop works."""

import asyncio
import json
from tinycua_sdk import Agent, LanguageModel, BaseLoop, tool
from tinycua_sdk.agent.executor import ToolExecutor


BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "qwen/qwen3.5-9b"


@tool
def weather(city: str) -> str:
    """Get weather for a city."""
    return f"Sunny in {city}."


class ReActLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream: bool = False):
        response = await agent._call_llm(messages, tools)
        content = response.get("content", "")

        # If the model produces a tool call in its response, execute it
        if response.get("tool_calls"):
            for tc in response["tool_calls"]:
                tool_name = tc["name"]
                arguments = json.loads(tc["arguments"])
                for t in tools:
                    if t.name == tool_name:
                        result = await ToolExecutor.execute(t, arguments, agent)
                        messages.append({"role": "assistant", "content": content})
                        messages.append({"role": "tool", "content": str(result), "name": tool_name})
                        break

            # One more LLM call with the tool result
            response2 = await agent._call_llm(messages)
            return response2.get("content", "") or "[no final answer]"

        return content


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME),
        tools=[weather],
        loop=ReActLoop(),
    )

    response = await a.run("What is the weather in Tokyo?", stream=False)
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/05_react_loop_expected-output.txt` → `Response: <any string>` (must not raise)

---

### Target 8.6: Streaming Events Compliance

**File:** `targets/06_streaming_events.py`

```python
"""Target 8.6: Verify the default BaseLoop stream injects lifecycle events.

Validates R-8.4: the default loop MUST emit response.created, response.in_progress,
response.usage, and response.completed even when the raw provider stream only
emits content deltas.

Uses a deterministic fake stream to avoid needing a live LLM server.
"""

import asyncio
from collections.abc import AsyncIterator

from tinycua_sdk import Agent, LanguageModel


async def fake_call_llm(messages, tools=None, stream: bool = False):
    """Return a stream that emits only content deltas (no lifecycle events).

    This lets us verify the default BaseLoop._run_stream() injects the
    missing response.created, response.in_progress, response.usage, and
    response.completed events required by R-8.4.
    """

    async def chunks() -> AsyncIterator[dict]:
        yield {"type": "response.output_text.delta", "delta": "Hello", "item_id": "msg_1"}

    return chunks()


async def main():
    a = Agent(llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"))
    a._call_llm = fake_call_llm  # type: ignore[method-assign]

    stream = await a.run("Hello", stream=True)
    events = [event async for event in stream]
    event_types = [e["type"] for e in events]

    assert "response.created" in event_types, f"Missing response.created in {event_types}"
    assert "response.in_progress" in event_types, f"Missing response.in_progress in {event_types}"
    assert "response.usage" in event_types, f"Missing response.usage in {event_types}"
    assert "response.completed" in event_types, f"Missing response.completed in {event_types}"

    # Verify order: created -> in_progress -> first content delta
    assert event_types.index("response.created") < event_types.index("response.in_progress"), \
        f"response.created should come before response.in_progress: {event_types}"
    assert event_types.index("response.in_progress") < event_types.index("response.output_text.delta"), \
        f"response.in_progress should come before first delta: {event_types}"

    print(f"Streaming lifecycle events correctly ordered: {event_types}")


asyncio.run(main())
```

**Expected Output:** `targets/06_streaming_events_expected-output.txt` → `Streaming lifecycle events correctly ordered: ['response.created', 'response.in_progress', 'response.output_text.delta', 'response.usage', 'response.completed']` (must not raise)
