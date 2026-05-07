# Stage 13 — Design: Create Examples

## Overview

Write new, stateless, runnable examples demonstrating the refactored SDK API. These examples serve as:
1. **Documentation**: Show consumers how to use the SDK
2. **Smoke tests**: Verify the SDK works end-to-end
3. **Migration guide**: Show old patterns → new patterns

## Philosophy

Examples should be:
- **Runnable**: Each example can be executed with `python example.py`
- **Stateless**: No session, no memory, no storage, no file I/O (except config loading)
- **Minimal**: Focus on one concept per example
- **Realistic**: Use realistic tool/skill definitions

## Example Files

### 01_basic_agent.py — Basic Agent

```python
"""Basic agent example.

Demonstrates: Agent construction with LLMModel, simple run().
"""
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

### 02_tools.py — Agent with Tools

```python
"""Agent with tools example.

Demonstrates: @tool decorator, add_tools(), tool invocation in loop.
"""
import asyncio
from tinycua_sdk import Agent, LLMModel, tool

@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

@tool
def summarize(text: str) -> str:
    """Summarize text."""
    return f"Summary: {text[:50]}..."

async def main():
    agent = Agent(
        llm_model=LLMModel(),
        instructions="Use search to find information, then summarize.",
    )
    # Add single tool
    agent.add_tools(search)
    # Add multiple tools
    agent.add_tools([summarize])
    
    response = await agent.run("What is quantum computing?")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

### 03_skills.py — Agent with Skills

```python
"""Agent with skills example.

Demonstrates: Skill.load(), add_skills(), skill-based instructions.
"""
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

### 04_config_file.py — Agent from YAML Config

```python
"""Agent from YAML config example.

Demonstrates: Agent.from_config(), YAML-based agent definition.
"""
import asyncio
from tinycua_sdk import Agent

async def main():
    agent = Agent.from_config("agent.yaml")
    response = await agent.run("What is quantum computing?")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

**agent.yaml:**
```yaml
name: researcher
instructions: Answer questions concisely using available tools.
llm_model:
  provider: openai-compatible
  model_name: qwen3.5-9b
  base_url: http://localhost:1234/v1
  system_prompt: You are a research assistant.
tools:
  - search
  - summarize
```

### 05_streaming.py — Streaming Response

```python
"""Streaming response example.

Demonstrates: stream=True, async iteration over chunks.
"""
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

### 06_sub_agents.py — Agent with Sub-Agents

```python
"""Agent with sub-agents example.

Demonstrates: Agent composition, sub-agent delegation.
"""
import asyncio
from tinycua_sdk import Agent, LLMModel

async def main():
    coordinator = Agent(
        name="coordinator",
        llm_model=LLMModel(),
        instructions="Coordinate tasks between sub-agents.",
    )
    
    researcher = Agent(
        name="researcher",
        llm_model=LLMModel(),
        instructions="Research topics thoroughly.",
    )
    
    writer = Agent(
        name="writer",
        llm_model=LLMModel(),
        instructions="Write clear, engaging content.",
    )
    
    # Compose: coordinator delegates to sub-agents
    coordinator.add_skills(...)  # Or equivalent mechanism
    
    response = await coordinator.run("Write a blog post about quantum computing")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

### 07_custom_loop.py — Custom ReAct Loop

```python
"""Custom ReAct loop example.

Demonstrates: Extending BaseLoop to implement the ReAct pattern.
"""
import asyncio
from tinycua_sdk import Agent, LLMModel, BaseLoop, tool

class ReActLoop(BaseLoop):
    """ReAct (Reasoning + Acting) loop implementation.
    
    This is a consumer-defined loop that extends BaseLoop.
    The SDK only provides BaseLoop; this is built on top.
    """
    
    async def run(self, agent, messages, tools):
        for i in range(self.max_iterations):
            # Reasoning step
            reasoning_msg = messages + [
                {"role": "assistant", "content": "Let me think step by step..."}
            ]
            
            # Action step: call LLM with tools
            response = await agent._call_llm(reasoning_msg)
            
            # Check if done
            tool_calls = self._extract_tool_calls(response)
            if not tool_calls:
                return response
            
            # Execute tools and append results
            for call in tool_calls:
                result = self._execute_tool_call(call, tools)
                messages.append({"role": "tool", "content": result})
        
        return response

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

## Example Requirements

- All examples are stateless (no session, no memory, no storage).
- All examples are runnable (importable, no missing dependencies).
- All examples use the new API (`LLMModel`, `add_tools()`, `Skill.load()`, etc.).
- Examples do not use deleted modules or singletons.
- Example 07 demonstrates extending `BaseLoop` (no built-in `ReactLoop`).

## Running Examples

```bash
# Basic agent
python docs/examples/01_basic_agent.py

# With tools (requires LLM server running)
python docs/examples/02_tools.py

# From config
python docs/examples/04_config_file.py

# Custom loop
python docs/examples/07_custom_loop.py
```

## Acceptance Criteria

- [ ] All 7 example files are created.
- [ ] All examples are stateless.
- [ ] All examples use the new API.
- [ ] Examples do not use deleted modules.
- [ ] Example 07 demonstrates custom loop extension.
- [ ] `agent.yaml` config file example is provided.

## Dependencies

- **Requires**: Stage 11, Stage 12 (Agent and Config must be refactored first).
- **Blocks**: Stage 14 (integration tests based on examples).
