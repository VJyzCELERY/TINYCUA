# Stage 09 — Implementation Plan: Refactor Tools Framework

## Objective

Clean up the `tools/` package to contain only the framework (decorator, schema, parser, resolver) and generic built-in tools. Remove memory-dependent tools. Ensure `@tool` returns a `Tool` instance directly with no side effects.

## Source of Truth

- [spec.md](./spec.md)
- [design.md](./design.md)

## Target Package Layout

```
tools/
  __init__.py
  decorators.py          # @tool, Tool dataclass (no side effects)
  schema.py              # JSON-schema generation
  parser.py              # Source parsing
  resolver.py            # Dependency resolution (pure functions)
  mcp.py                 # MCP integration
  cua/                   # CUA helpers
  native/                # Built-in tools shipped with the SDK
    __init__.py
    context_tools.py     # Generic context utilities
    skills_tools.py      # Skill-native tools (moved from skills/)
```

## Implementation Steps

### Step 1 — Delete Memory-Dependent Modules

| File | Action | Reason |
|------|--------|--------|
| `tools/memory.py` | Delete | MemoryBackend hierarchy — stateful |
| `tools/memory_tools.py` | Delete | remember, recall, forget — depend on memory |

### Step 2 — Refactor `tools/decorators.py`

- Remove `ToolRegistry` import and side-effect registration.
- Ensure `@tool` returns a `Tool` instance directly.
- Update `Tool` dataclass with `to_config()`, `to_bundle()`, and `invoke()` methods.
- Reserve fields for future dependency resolution: `_external_dependencies`, `_tool_dependencies`, `_version`.

### Step 3 — Update `tools/__init__.py`

- Remove exports for deleted modules and symbols:
  - `MemoryBackend`
  - `LocalMemoryBackend`
  - `HybridMemoryBackend`
  - `get_memory_backend`
  - `set_memory_backend`
  - `reset_memory_backend`
  - `remember`
  - `recall`
  - `forget`
  - `list_memory`
  - `clear_memory`
- Add exports for framework modules: `generate_schema`, `MCPClient`.
- Update `__all__` accordingly.

### Step 4 — Flatten / Move Native Tools

- Move skill-native tools from `skills/tools.py` to `tools/native/skills_tools.py`.
- Ensure `tools/native/context_tools.py` stays as generic context utilities.

### Step 5 — Delete `CallableTool`

- Remove `CallableTool` class from `skills/tools.py` (or wherever it exists).
- Rationale: `Tool.invoke()` already accepts `**kwargs`, making `CallableTool` redundant.

### Step 6 — Verify Tests

- Run `pytest` for the `tools/` package.
- Ensure all remaining tests pass after deletions and refactors.

## Acceptance Criteria

- [ ] `tools/memory.py` does not exist.
- [ ] `tools/memory_tools.py` does not exist.
- [ ] `@tool` decorator returns a `Tool` instance directly (no side effects).
- [ ] `ToolRegistry` singleton is not used in `tools/`.
- [ ] `CallableTool` is deleted (replaced by standard `Tool.invoke()`).
- [ ] `tools/__init__.py` does not export memory-related symbols.
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02, Stage 08
- **Blocks**: Stage 11 (Agent refactor depends on clean tool framework)
