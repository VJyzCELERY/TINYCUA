# Stage 09 — Task Breakdown: Refactor Tools Framework

## Task 1 — Delete Memory Modules
- [ ] Delete `tools/memory.py`
- [ ] Delete `tools/memory_tools.py`
- [ ] Remove any imports/references to these modules across the codebase

## Task 2 — Refactor `tools/decorators.py`
- [ ] Remove `ToolRegistry` import
- [ ] Remove `ToolRegistry.register(t)` side effect from `@tool`
- [ ] Update `Tool` dataclass:
  - [ ] Add `to_config()` method
  - [ ] Add `to_bundle()` method
  - [ ] Add `invoke(**kwargs)` method
  - [ ] Add `_external_dependencies` field
  - [ ] Add `_tool_dependencies` field
  - [ ] Add `_version` field
- [ ] Ensure `@tool` returns a `Tool` instance directly

## Task 3 — Update `tools/__init__.py`
- [ ] Remove memory-related exports
- [ ] Add `generate_schema` export from `.schema`
- [ ] Add `MCPClient` export from `.mcp`
- [ ] Update `__all__` list

## Task 4 — Move / Flatten Native Tools
- [ ] Move content from `skills/tools.py` to `tools/native/skills_tools.py`
- [ ] Ensure `tools/native/context_tools.py` remains intact

## Task 5 — Delete `CallableTool`
- [ ] Locate and remove `CallableTool` class
- [ ] Update any call sites to use `Tool.invoke(**kwargs)` instead

## Task 6 — Test Verification
- [ ] Run `pytest` for the `tools/` package
- [ ] Fix any broken imports or references
- [ ] Confirm all remaining tests pass

## Definition of Done
- All acceptance criteria in `implementation-plan.md` are met.
- `pytest` passes for the `tools/` package.
- No memory-related symbols remain in `tools/` public API.
