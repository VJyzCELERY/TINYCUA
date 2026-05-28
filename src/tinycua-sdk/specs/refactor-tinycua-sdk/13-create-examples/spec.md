# Stage 13 — Create Examples

## Objective

Write new, stateless, runnable examples demonstrating the refactored SDK API.

## Files to Create

| File | Description |
|------|-------------|
| `docs/examples/01_basic_agent.py` | Basic agent with LLMModel |
| `docs/examples/02_tools.py` | Agent with tools |
| `docs/examples/03_skills.py` | Agent with skills |
| `docs/examples/04_config_file.py` | Agent from YAML config |
| `docs/examples/05_streaming.py` | Streaming response |
| `docs/examples/06_sub_agents.py` | Agent with sub-agents |
| `docs/examples/07_custom_loop.py` | Custom ReAct loop extending `BaseLoop` |

## Example Requirements

### 01_basic_agent.py
```python
"""Basic agent example."""
import asyncio
from tinycua_sdk import Agent, LLMModel

async def main():
    agent = Agent(
        llm_model=LLMModel(
            base_url="http://localhost:1234/v1",
            model_name="qwen3.5-9b",
            system_prompt="You are a helpful assistant.",
        ),
        instructions="Answer questions concisely.",
    )
    response = await agent.run("What is quantum computing?")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

### 02_tools.py
```python
"""Agent with tools example."""
import asyncio
from tinycua_sdk import Agent, LLMModel, tool

@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

async def main():
    agent = Agent(
        llm_model=LLMModel(),
        instructions="Use search to find information.",
    )
    agent.add_tools(search)
    response = await agent.run("What is quantum computing?")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

### 03_skills.py
```python
"""Agent with skills example."""
import asyncio
from tinycua_sdk import Agent, LLMModel, Skill

async def main():
    skill_md = """
---
name: researcher
category: research
tools:
  - search
---
# Researcher
## Instructions
Research topics thoroughly and cite sources.
"""
    researcher = Skill.load(skill_md)

    agent = Agent(
        llm_model=LLMModel(),
        instructions="Answer questions using research skills.",
    )
    agent.add_skills(researcher)
    response = await agent.run("What is quantum computing?")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

### 04_config_file.py
```python
"""Agent from YAML config example."""
import asyncio
from tinycua_sdk import Agent

async def main():
    agent = Agent.from_config("agent.yaml")
    response = await agent.run("What is quantum computing?")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

### 05_streaming.py
```python
"""Streaming response example."""
import asyncio
from tinycua_sdk import Agent, LLMModel

async def main():
    agent = Agent(llm_model=LLMModel())
    async for chunk in await agent.run("Tell me a story", stream=True):
        print(chunk, end="")
    print()

if __name__ == "__main__":
    asyncio.run(main())
```

### 06_sub_agents.py
```python
"""Agent with sub-agents example."""
import asyncio
from tinycua_sdk import Agent, LLMModel

async def main():
    parent = Agent(
        name="coordinator",
        llm_model=LLMModel(),
        instructions="Coordinate tasks between sub-agents.",
    )
    child = Agent(
        name="researcher",
        llm_model=LLMModel(),
        instructions="Research topics.",
    )
    # Sub-agent composition
    parent.add_skills(...)  # or equivalent mechanism
    response = await parent.run("Research quantum computing")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

### 07_custom_loop.py
```python
"""Example: custom ReAct loop by extending BaseLoop."""
import asyncio
from tinycua_sdk import Agent, LLMModel, BaseLoop, tool

class ReActLoop(BaseLoop):
    """Custom ReAct loop: reason then act."""

    async def run(self, agent, messages, tools):
        for i in range(self.max_iterations):
            # 1. Reasoning step
            reasoning_msgs = messages + [
                {"role": "assistant", "content": "Let me think step by step..."}
            ]
            # 2. Action step (tool call)
            # ... call LLM with tools ...
            # 3. Return final answer when done
            pass  # implementation omitted for brevity

@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

async def main():
    agent = Agent(
        llm_model=LLMModel(),
        instructions="Use search to find information.",
        loop=ReActLoop(max_iterations=3),
    )
    agent.add_tools(search)
    response = await agent.run("What is quantum computing?")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

## Acceptance Criteria

- [ ] All examples are stateless (no session, no memory, no storage).
- [ ] All examples are runnable (importable, no missing dependencies).
- [ ] All examples use the new API (`LLMModel`, `add_tools()`, `Skill.load()`, etc.).
- [ ] Examples do not use deleted modules or singletons.
- [ ] Example 07 demonstrates extending `BaseLoop` (no built-in `ReactLoop`).

## Dependencies

- **Requires**: Stage 11, Stage 12 (Agent and Config must be refactored first)
