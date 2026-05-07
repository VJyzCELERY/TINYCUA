# Stage 08 — Remove Core Registry

## Objective

Delete `core/registry.py` (the `ToolRegistry` singleton). Singletons are global mutable state and violate SDK statelessness.

## Files to Delete

| File | Reason |
|------|--------|
| `core/registry.py` | ToolRegistry singleton |

## Code Changes

### Update @tool Decorator

In `tools/decorators.py`:
- `@tool` should return a `Tool` instance directly.
- It should NOT register the tool into a global singleton.

```python
# BEFORE
@tool
def my_tool(): ...
# Implicitly registers into ToolRegistry singleton

# AFTER
@tool
def my_tool(): ...
# Returns Tool instance; caller decides what to do with it
```

### Update Agent

In `agent/agent.py`, `agent/definition.py`:
- Remove `ToolRegistry` imports.
- Agent holds its own `list[Tool]` directly.

### Update Skills

In `skills/tools.py`:
- Remove `CallableTool` wrapper (it depends on ToolRegistry patterns).
- If `skills/tools.py` only contains tools for skill progressive disclosure, evaluate whether it should be deleted or moved.

### Update Tests

In remaining tests:
- Remove `ToolRegistry` usage.
- Pass tools directly to `Agent` constructor or `add_tools()`.

## Acceptance Criteria

- [ ] `core/registry.py` does not exist.
- [ ] `@tool` decorator returns `Tool` instance without side effects.
- [ ] `Agent` holds tools directly, not via registry lookup.
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02
