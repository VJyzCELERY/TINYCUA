# Creating Tools

**Prerequisites**: [Multimodal Content](../core-concepts/multimodal-content.md) —
familiarity with the SDK's messaging model.

## Overview

Tools give agents the ability to interact with the outside world — fetching data,
running computations, calling APIs, or reading files. The TINYCUA SDK provides a
`@tool` decorator and a `Tool` class that auto-generate JSON Schema from Python
type hints, parse docstrings for descriptions, and support bulk loading from
directory trees.

This page covers every way to define a tool: the decorator (four variant forms),
explicit construction via `Tool.from_callable`, deserialization from config
dicts, and bulk loading. You'll also learn how to return structured data (dicts,
lists) so the agent can act on the output.

## The `@tool` Decorator

The decorator inspects your function signature and docstring and produces a
`Tool` instance ready for an agent. The first line of the docstring becomes the
tool description sent to the LLM; type annotations become the JSON Schema
`properties`.

### Bare Decorator

The simplest form — no arguments, name derived from the function:

```python
from tinycua_sdk import tool


@tool
def get_weather(city: str, units: str = "celsius") -> str:
    """Fetch current weather for a city.

    Args:
        city: Name of the city.
        units: Temperature units (celsius or fahrenheit).

    """
    return f"Weather in {city}: 22°C, sunny"
```

### Parenthesized (no arguments)

Exactly equivalent to the bare form:

```python
from tinycua_sdk import tool


@tool()
def get_time(timezone: str = "UTC") -> str:
    """Return the current time for a timezone."""
    return f"Current time in {timezone}: 14:30"
```

### Custom Name

Override the tool name (useful when the function name is an implementation
detail):

```python
from tinycua_sdk import tool


@tool(name="search_database")
def db_lookup(query: str, limit: int = 10) -> str:
    """Search the internal database.

    Args:
        query: Search query string.
        limit: Maximum number of results.

    """
    return f"Found 3 results for '{query}'"
```

### Declaring Dependencies

Mark tools that require third-party packages. The SDK validates availability at
registration time:

```python
from tinycua_sdk import tool


@tool(dependencies=["requests"])
def fetch_url(url: str) -> str:
    """Fetch and return the text content of a URL."""
    import requests

    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.text[:500]
```

## Explicit Construction with `Tool.from_callable`

If you prefer not to use decorators, call `from_callable` directly:

```python
from tinycua_sdk import Tool


def add(a: float, b: float) -> float:
    """Add two numbers.

    Args:
        a: The first number.
        b: The second number.

    """
    return a + b


adder = Tool.from_callable(add, name="sum")
```

This produces the same `Tool` instance as `@tool(name="sum")` above.

## Load from Config Dict with `Tool.from_dict`

You can reconstruct a `Tool` from a serialized config — useful when loading
tool definitions from a config file or API response:

```python
from tinycua_sdk import Tool

config = {
    "type": "function",
    "function": {
        "name": "multiply",
        "description": "Multiply two numbers.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "number"},
                "y": {"type": "number"},
            },
            "required": ["x", "y"],
        },
    },
}

tool_from_config = Tool.from_dict(config)
print(tool_from_config.name)  # multiply
print(tool_from_config.description)  # Multiply two numbers.
```

`from_dict` accepts both OpenAI-style (`function` wrapper) and bare
(`name`/`description`/`parameters`) formats. Note that tools loaded this way
have no `_callable` — they are schema-only and useful for serialization
roundtrips.

## Bulk Loading with `Tool.load_directory`

Point `load_directory` at a directory tree. Each immediate subdirectory is
scanned for Python modules (files starting with `_` are skipped), and every
`Tool` instance found is collected:

```python
from pathlib import Path
from tinycua_sdk import Tool

tools = Tool.load_directory(Path("./my_tools"))
print([t.name for t in tools])
```

Given a directory structure like:

```
my_tools/
├── weather.py      # contains a Tool named "get_weather"
├── calculator.py   # contains a Tool named "add" and another named "multiply"
└── _internal.py    # skipped
```

`load_directory` returns `[get_weather, add, multiply]`.

## Returning Structured Data

Tools are not limited to strings. Return dicts, lists, or any JSON-serializable
value — the SDK normalizes everything internally:

```python
from tinycua_sdk import tool


@tool
def list_users() -> list:
    """Return all registered users."""
    return [
        {"id": 1, "name": "Alice", "role": "admin"},
        {"id": 2, "name": "Bob", "role": "user"},
    ]


@tool
def get_metadata(record_id: int) -> dict:
    """Return metadata for a record.

    Args:
        record_id: The record identifier.

    """
    return {
        "record_id": record_id,
        "created": "2025-03-15T10:30:00Z",
        "size_bytes": 1_024,
    }
```

> **Note**: If you need to return file attachments from a tool, see
> [Tool Results with Files](../advanced-file-handling/tool-results-with-files.md).

## Attaching Tools to an Agent

Once defined, tools are passed at construction time or added later:

```python
import os

from tinycua_sdk import Agent, LanguageModel, tool


@tool
def get_weather(city: str) -> str:
    """Fetch current weather for a city."""
    return f"Weather in {city}: 22°C, sunny"


# Local — LM Studio
model = LanguageModel(
    provider="openai-compatible",
    model_name="qwen/qwen3.5-9b",
    base_url="http://localhost:1234/v1",
)

agent = Agent(
    name="weather-agent",
    instructions="You help users check weather.",
    llm_model=model,
    tools=[get_weather],
)

# Or use add_tools later
# agent.add_tools(get_weather)
```

Remote (OpenAI):

```python
import os

from tinycua_sdk import Agent, LanguageModel, tool


@tool
def get_weather(city: str) -> str:
    """Fetch current weather for a city."""
    return f"Weather in {city}: 22°C, sunny"


model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="weather-agent",
    instructions="You help users check weather.",
    llm_model=model,
    tools=[get_weather],
)
```

## Common Pitfalls

**Forgetting type annotations**. The SDK generates JSON Schema from annotations.
A parameter without an annotation defaults to `{"type": "string"}`. Use
explicit types for numbers, booleans, and optional values (`Optional[int]`,
`int | None`).

**Overlapping tool names during `add_tools`**. If you register a tool whose name
matches an existing one, the duplicate is silently skipped. Rename tools or use
`Tool.from_callable(..., name="unique_name")` to avoid collisions.

**`load_directory` skips private files**. Files or directories starting with
`_` are excluded. Use this convention for shared utilities that shouldn't be
exposed as tools.

## Next Steps

- **[Skills and Skill Registry](./skills-and-skill-registry.md)** — Add
  reusable instructions to agents with `Skill` objects.
- **[Tool Results with Files](../advanced-file-handling/tool-results-with-files.md)** —
  Return file attachments from tool calls.
