# Stage 3: LLM Client & Basic Execution Loop — Targets

## Purpose
Verify the agent can call an LLM, handle tool calls, and support cancellation. Uses a real or mock LLM server.

---

### Target 3.1: Agent.run Returns String (Non-Streaming)

**File:** `targets/01_run_returns_string.py`

```python
"""Target 3.1: Verify agent.run() returns a string with stream='off'."""

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
    response = await a.run("Say hello.", stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/01_run_returns_string_expected-output.txt` → `Response: <any string>` (must not raise)

---

### Target 3.2: Agent.run with Message History

**File:** `targets/02_run_with_history.py`

```python
"""Target 3.2: Verify agent.run() respects prior message history."""

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

    history = [
        {"role": "user", "content": "My name is Alice."},
        {"role": "assistant", "content": "Nice to meet you!"},
    ]

    response = await a.run("What is my name?", messages=history, stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/02_run_with_history_expected-output.txt` → `Response: <any string>` (must not raise)

---

### Target 3.3: Agent.run with Instruction Override

**File:** `targets/03_instruction_override.py`

```python
"""Target 3.3: Verify runtime instruction override works."""

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

    response = await a.run(
        "Tell me a joke.",
        instructions="You are a pirate. Be funny and concise.",
        stream="off",
    )
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/03_instruction_override_expected-output.txt` → `Response: <any string>` (must not raise)

---

### Target 3.4: Cancellation Support

**File:** `targets/04_cancellation.py`

```python
"""Target 3.4: Verify agent.cancel() stops an in-flight run."""

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

    task = asyncio.create_task(a.run("Write a very long essay about cheese."))
    await asyncio.sleep(0.5)  # Let it start
    a.cancel()

    try:
        response = await task
        print(f"Response (may be partial): {response}")
    except asyncio.CancelledError:
        print("Agent run was cancelled.")


asyncio.run(main())
```

**Expected Output:** `targets/04_cancellation_expected-output.txt` → Either `Response: ...` or `Agent run was cancelled.` (must not hang)

---

### Target 3.5: Tool Calling Loop

**File:** `targets/05_tool_calling_loop.py`

```python
"""Target 3.5: Verify agent with tools correctly invokes them."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, tool

BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "qwen/qwen3.5-9b"


@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression."""
    return str(eval(expression, {"__builtins__": {}}, {}))


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
        tools=[calculator],
        instructions="You have access to a calculator. Use it for math.",
    )

    response = await a.run("What is 135 * 42?", stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/05_tool_calling_loop_expected-output.txt` → `Response: <any string>` (must not raise)

---

### Target 3.6: Dynamic add_tools After Creation

**File:** `targets/06_dynamic_add_tools.py`

```python
"""Target 3.6: Verify tools added after creation work on next run."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, tool

BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "qwen/qwen3.5-9b"


@tool
def convert_currency(amount: float, from_c: str, to_c: str) -> str:
    """Convert currency."""
    rates = {"USD": 1.0, "EUR": 0.92}
    usd = amount / rates[from_c]
    return f"{usd * rates[to_c]:.2f}"


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
    )

    # Add tool after creation
    a.add_tools(convert_currency)

    response = await a.run("Convert 100 USD to EUR.", stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/06_dynamic_add_tools_expected-output.txt` → `Response: <any string>` (must not raise)
