# Review Report: Stage 08 — Remove Core Registry

## Target Directory
`src/tinycua-sdk/specs/refactor-tinycua-sdk/08-remove-core-registry/`

## Checks Performed

### 1. `core/registry.py` Deleted
**Result:** ✅ PASS

`tinycua_sdk/core/registry.py` does not exist. The `tinycua_sdk/core/` directory contains only:
- `__init__.py`
- `config.py`
- `providers.py`

### 2. No `ToolRegistry` Imports in Source Code
**Result:** ✅ PASS

Grep across `tinycua_sdk/` source code found **zero** references to `ToolRegistry` or `core.registry`.

Grep across `tests/` found only one reference: a docstring in `tests/unit/test_agent.py` line 305 (`"""Agent does not depend on a global ToolRegistry singleton."""`). This is a test description, not an import or usage.

### 3. `@tool` Decorator Has No Side Effects
**Result:** ✅ PASS

In `tinycua_sdk/tools/decorators.py`:
- The `@tool` decorator returns `_make_tool(fn, _external_deps)` directly.
- There is **no** registration into any global singleton.
- The `Tool` dataclass is returned immediately to the caller.

```python
def decorator(fn: Callable) -> Tool:
    return _make_tool(fn, _external_deps)
```

### 4. Agent Holds Tools Directly
**Result:** ✅ PASS

In `tinycua_sdk/agent/definition.py`:
- `AgentDefinition.__init__` accepts `tools: list[Tool] | None = None`.
- Tools are stored directly in `AgentConfig(tools=tools or [])`.
- No `ToolRegistry` lookup or resolution is performed.

In `tinycua_sdk/agent/agent.py`:
- `Agent.__init__` passes `tools` directly to `AgentExecutor` / `AgentDefinition`.
- No registry-related imports or calls.

### 5. `skills/tools.py` Updated
**Result:** ✅ PASS

`CallableTool` wrapper has been removed. The file now contains only factory functions (`create_skills_list_tool`, `create_skill_view_tool`) that accept an explicit `SkillRegistry` instance and return `Tool` instances via the `@tool` decorator.

### 6. Package Imports Cleanly
**Result:** ✅ PASS

```python
from tinycua_sdk import tool, Agent, Tool
```
Imports successfully without errors.

### 7. Tests Related to This Stage
**Result:** ✅ PASS (Stage 08 scope)

- `tests/unit/test_tool.py`: 11/12 passed. The one failure (`test_tool_source_captured`) is unrelated to registry removal — it tests `hasattr(my_tool, "source")` vs `_source` attribute naming.
- `tests/unit/test_tool_schema.py`: 19/19 passed.
- `tests/unit/test_tool_resolver.py`: 5/5 passed.
- `tests/unit/test_import_sanity.py`: 3/3 passed.

## Verdict

**CLEAN**

All Stage 08 acceptance criteria are satisfied:
- [x] `core/registry.py` does not exist.
- [x] `@tool` decorator returns `Tool` instance without side effects.
- [x] `Agent` holds tools directly, not via registry lookup.
- [x] `ToolRegistry` is not exported from `tinycua_sdk`.
- [x] No `ToolRegistry` imports remain in source code.
