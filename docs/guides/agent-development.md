# Agent Development Guide

This guide walks you through building agents with TinyCUA SDK.

## Quick Start

### Installation

```bash
pip install tinycua-sdk
```

### Basic Agent

```python
from tinycua_sdk import Agent

# Create an agent
agent = Agent(
    name="my-agent",
    instructions="You are a helpful coding assistant",
    model="gpt-4o-mini",
)

# Run the agent
result = agent.run("Hello, how are you?")
print(result)
```

## Configuration

### Using Environment Variables

```bash
export TINYCUA_BACKEND_URL=http://localhost:8000
export TINYCUA_API_KEY=your-api-key
export TINYCUA_PROVIDER=openai
export TINYCUA_MODEL=gpt-4
export TINYCUA_BASE_URL=https://api.openai.com/v1
```

### Using YAML Config

Create `config.yaml`:

```yaml
backend_url: http://localhost:8000
llm:
  provider: openai
  model: gpt-4
  base_url: https://api.openai.com/v1
  api_key: your-api-key
```

Load the config:

```python
from tinycua_sdk.core.config import SDKConfig

config = SDKConfig.from_yaml("config.yaml")
```

## Adding Tools

### Basic Tool

```python
from tinycua_sdk.tools import tool

@tool(name="calculate", description="Perform calculations")
def calculate(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))

# Use in agent
agent = Agent(
    name="math-agent",
    instructions="You are a math assistant",
    tools=[calculate]
)
```

### Tool with Parameters

```python
from tinycua_sdk.tools import tool
from typing import Annotated

@tool(name="search", description="Search the web")
def search(
    query: Annotated[str, "The search query"],
    num_results: Annotated[int, "Number of results"] = 5
) -> list[dict]:
    """Search for information."""
    # Implementation here
    return [{"title": "Result 1", "url": "http://example.com"}]
```

## Session Management

### Create a Session

```python
from tinycua_sdk import Agent

agent = Agent(name="my-agent")

# Create a named session
session = agent.create_session(name="my-session")

# Run with specific session
result = agent.run("Hello", session=session)
```

### List Sessions

```python
# List all sessions
sessions = agent.list_sessions()

for session in sessions:
    print(f"{session.id}: {session.name}")
```

## Running Agents

### Local Mode

```python
from tinycua_sdk import Agent

agent = Agent(name="my-agent")
result = agent.run("What is 2 + 2?")
print(result)
```

### Deployed Mode

```python
from tinycua_sdk import Agent

agent = Agent(name="my-agent")
agent.deploy()

# Agent is now available via API
```

## Next Steps

- Learn about [Skills](skills.md)
- Learn about [Context Management](context-management.md)
- Learn about [Middleware](middleware.md)
- Learn about [Agent Creation Kit](agent-creation-kit.md)
