# TINYCUA SDK Specification

**Status**: In Progress
**Created**: 2026-03-11
**Last Updated**: 2026-03-16
**Subproject(s) Affected**: tinycua-sdk

---

## Overview

The TINYCUA SDK provides a unified interface for building AI agents with tool-calling capabilities. It supports both local execution (LM Studio, Ollama) and cloud providers (OpenAI).

---

## Problem Statement

**Goals**: Provide developers with a simple SDK to create AI agents that can:
1. Use tools via natural language
2. Run locally with various LLM providers
3. Deploy to a backend for remote execution
4. Manage sessions and memory

**Gaps**:
- No unified agent abstraction
- No built-in tools for session/memory
- No agent hierarchy support
- No streaming tool execution

---

## Core Features

### 1. Client (`ResponsesClient`)

| Feature | Status |
|---------|--------|
| Connect to OpenAI-compatible APIs | ✅ |
| Streaming responses | ✅ |
| Automatic retry | ✅ |
| Request tracing (X-Trace-Id) | ✅ |

### 2. Tool System (`@tool`)

| Feature | Status |
|---------|--------|
| Convert Python functions to Tools | ✅ |
| Auto JSON Schema generation | ✅ |
| Tool dependencies | ✅ |
| Tool serialization (to_config, to_bundle) | ✅ |
| Tool invocation | ✅ |

### 3. Agent System

| Feature | Status |
|---------|--------|
| Agent configuration | ✅ |
| AgentPolicy (max_tool_calls, temperature) | ✅ |
| Plan mode (analyze → execute → aggregate) | ✅ |
| Deployed mode (call backend) | ✅ |
| Agent hierarchy (sub-agents) | ⏳ |
| Streaming tool execution | ✅ |
| Cancel mechanism | ✅ |

### 4. Runner (Local Execution)

| Feature | Status |
|---------|--------|
| Local agent execution | ✅ |
| Auto tool detection/execution | ✅ |
| Message history management | ✅ |
| Multiple provider support | ✅ |
| Token streaming | ✅ |
| Plan mode | ✅ |
| Tool streaming | ✅ |

### 5. Session & Memory Tools

| Feature | Status |
|---------|--------|
| remember/recall/forget | ✅ |
| list_memory/clear_memory | ✅ |
| create/load/save sessions | ✅ |
| List sessions | ✅ |
| Delete sessions | ✅ |
| Local JSON storage | ✅ |
| Remote backend with fallback | ✅ |

### 6. Configuration

| Feature | Status |
|---------|--------|
| .env file support | ✅ |
| Global config | ✅ |
| Per-agent config | ✅ |

---

## Provider Support

| Provider | Base URL | Default Model |
|----------|----------|---------------|
| LM Studio | http://localhost:1234/v1 | qwen/qwen3.5-9b |
| Ollama | http://localhost:11434/v1 | llama3 |
| OpenAI | https://api.openai.com/v1 | gpt-4o-mini |

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   tinycua-sdk                    │
├─────────────────────────────────────────────────┤
│  Agent                                          │
│  ├── .run() - Execute agent                    │
│  ├── .stream() - Token streaming                │
│  ├── .deploy() - Deploy to backend             │
│  └── .run(deployed=True) - Call backend        │
│                                                 │
│  Runner (Internal Runtime)                      │
│  ├── Local LLM execution                        │
│  ├── Tool execution                             │
│  └── Plan mode (analyze → execute → aggregate) │
│                                                 │
│  Tools                                         │
│  ├── @tool decorator                           │
│  ├── Memory tools (remember, recall)             │
│  ├── Session tools                             │
│  └── Sub-agents                                │
│                                                 │
│  Client                                        │
│  └── ResponsesClient → LM Studio/Ollama/OpenAI │
└─────────────────────────────────────────────────┘
```

---

## Usage Examples

### Basic Agent

```python
from tinycua_sdk.tools import tool
from tinycua_sdk.models import Agent

@tool()
def get_weather(location: str) -> dict:
    """Get weather for a location."""
    return {"weather": "sunny", "temp": 22}

agent = Agent(
    name="weather-assistant",
    provider="lmstudio",
    model="qwen/qwen3.5-9b",
    tools=[get_weather],
)

# Run agent
response = await agent.run("What's the weather in Tokyo?")

# Stream response
async for token in agent.stream("Hello"):
    print(token, end="")
```

### Plan Mode

```python
agent = Agent(
    name="planner",
    provider="lmstudio",
    model="qwen/qwen3.5-9b",
    tools=[get_weather, calculator],
    plan_mode="plan",  # Analyzes → Executes → Aggregates
)

response = await agent.run(
    "Check weather Tokyo and New York, compare"
)
```

### Deploy to Backend

```python
agent = Agent(
    name="my-agent",
    tools=[get_weather],
    backend_url="http://localhost:8000",
)

deployment = await agent.deploy()
# Returns: {agent_id, backend_url, status: "deployed"}

# Now .run() calls backend instead of local LLM
response = await agent.run("Hello")
```

---

## File Structure

```
tinycua_sdk/
├── __init__.py           # Main exports
├── config.py             # Configuration (.env)
├── clients/
│   ├── client.py        # ResponsesClient
│   └── agent_client.py   # AgentClient (legacy)
├── models/
│   ├── agent.py          # Agent, AgentConfig, AgentPolicy
│   ├── request.py       # Request models
│   ├── response.py      # Response models
│   ├── result.py        # RunResult, ToolCall
│   └── task.py          # TaskPlan, TodoItem
├── runner/
│   └── runner.py         # Local Runner
├── session/
│   └── session.py       # Session class
├── tools/
│   ├── decorators.py     # @tool decorator
│   ├── memory.py        # remember, recall, forget
│   └── session.py       # Session management tools
└── tui/
    └── chat.py           # TUI Chat app
```

---

## Status Tracker

| Component | Status |
|-----------|--------|
| ResponsesClient | ✅ Complete |
| @tool decorator | ✅ Complete |
| Agent class | ✅ Complete |
| Runner | ✅ Complete |
| Plan mode | ✅ Complete |
| Deploy mode | ✅ Complete |
| Streaming | ✅ Complete |
| Config/.env | ✅ Complete |
| Streaming tool execution | ✅ Complete |
| Memory tools | ⏳ Pending |
| Session tools | ⏳ Pending |
| Agent hierarchy | ⏳ Pending |

---

## Requirements

### Tool System

- **FR-001**: `@tool` decorator MUST convert Python functions to Tool objects
- **FR-002**: Tool MUST auto-generate JSON Schema from type annotations
- **FR-003**: Tool.to_bundle() MUST include source code for deployment

### Agent

- **FR-010**: Agent MUST support local execution via Runner
- **FR-011**: Agent MUST support plan mode (analyze → execute → aggregate)
- **FR-012**: Agent MUST support deployed mode (call backend)
- **FR-013**: Agent MUST support token streaming
- **FR-014**: Agent MUST support sub-agents (hierarchy)
- **FR-015**: Agent MUST have .run(), .stream(), .deploy() methods

### Memory & Session

- **FR-020**: remember(key, value) MUST store in local storage
- **FR-021**: recall(key) MUST retrieve from storage
- **FR-022**: forget(key) MUST delete from storage
- **FR-023**: Session tools MUST save/load conversation state
- **FR-024**: Storage MUST be local JSON files

---

## Testing Plan

### Unit Tests
- Tool decorator schema extraction
- Agent configuration serialization
- Runner tool execution
- Memory tool operations

### Integration Tests
- Full agent flow with LM Studio
- Plan mode execution
- Deploy mode (when backend ready)

---

## Open Questions

- **OQ-001**: Should memory be stored in backend or local? → Local JSON for MVP
- **OQ-002**: Max agent hierarchy depth? → Default 3 levels
- **OQ-003**: Streaming tool results format? → Inline or separate stream

---

## Review Checklist

- [x] No implementation details
- [x] All mandatory sections completed
- [ ] Status tracker updated
- [x] Requirements are testable
- [x] Scope clearly bounded
