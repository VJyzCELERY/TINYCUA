# Stage 08 — Design: Remove Core Registry

## Overview

Delete `core/registry.py` (the `ToolRegistry` singleton). The SDK does not maintain global mutable state. Tools are composed explicitly via `Agent.add_tools()`.

## Design Decisions

### Why Delete ToolRegistry?

1. **Global mutable state**: A singleton registry is global mutable state, which violates SDK statelessness.
2. **Implicit dependencies**: Code that uses the registry has hidden dependencies on global state, making testing and reasoning harder.
3. **Explicit composition**: `Agent(tools=[tool1, tool2])` is clearer than `@tool` + implicit global registration.
4. **No need for discovery**: The SDK does not need to "discover" tools at runtime. The consumer knows which tools it wants.

### What Replaces ToolRegistry?

Nothing. Tools are passed directly to `Agent`:

```python
@tool
def search(q: str) -> str:
    return f"Results for {q}"

agent = Agent(tools=[search])  # Explicit composition
```

## Files to Delete

| File | Reason |
|------|--------|
| `core/registry.py` | ToolRegistry singleton — global mutable state |

## Code Changes

### Update @tool decorator

```python
# BEFORE (decorators.py)
def tool(func=None, *, name=None, description=None):
    def decorator(fn):
        t = Tool(...)
        ToolRegistry.register(t)  # Global side effect!
        return t
    ...

# AFTER (decorators.py)
def tool(func=None, *, name=None, description=None):
    def decorator(fn):
        t = Tool(...)
        return t  # No side effects
    ...
```

### Update Agent to not use registry

```python
# BEFORE
class Agent:
    def __init__(self, tools=None, ...):
        self.tools = ToolRegistry.resolve(tools)  # Implicit lookup

# AFTER
class Agent:
    def __init__(self, tools=None, ...):
        self.tools = list(tools or [])  # Explicit list
```

### Update exports

```python
# BEFORE (tools/__init__.py)
from .decorators import tool, Tool
from .registry import ToolRegistry  # Deleted

# AFTER (tools/__init__.py)
from .decorators import tool, Tool
# No registry export
```

## Impact Analysis

### Files that import from core.registry

```bash
grep -r "from tinycua_sdk.core.registry" src/tinycua-sdk/tinycua_sdk/
grep -r "ToolRegistry" src/tinycua-sdk/tinycua_sdk/
```

### Expected impact

- `tools/decorators.py` — Remove registry registration side effect
- `tools/__init__.py` — Remove registry export
- `agent/agent.py` — Remove registry lookup
- `core/__init__.py` — Remove registry export
- `core/registry.py` — Deleted

## Consumer Migration Guide

### Before (singleton registry)
```python
from tinycua_sdk import tool
from tinycua_sdk.core.registry import ToolRegistry

@tool
def search(q: str) -> str:
    return f"Results for {q}"

# Tool was auto-registered
registry = ToolRegistry()
agent = Agent(tools=registry.list_tools())
```

### After (explicit composition)
```python
from tinycua_sdk import tool

@tool
def search(q: str) -> str:
    return f"Results for {q}"

# Pass tool directly
agent = Agent(tools=[search])

# Or add later
agent.add_tools(search)
```

## Acceptance Criteria

- [ ] `core/registry.py` is deleted.
- [ ] `@tool` decorator does not register into a global singleton.
- [ ] `Agent` does not import from `core.registry`.
- [ ] `ToolRegistry` is not exported from `tinycua_sdk`.
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02.
- **Blocks**: None (can proceed in parallel with Stages 03–07, 09–10).
