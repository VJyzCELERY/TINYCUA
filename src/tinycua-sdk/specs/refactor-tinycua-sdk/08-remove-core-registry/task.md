# Tasks: Remove Core Registry

Implementation tasks for Stage 08 — Remove Core Registry. Check off items as completed.

## Implementation Phase

- [ ] Delete `core/registry.py` <!-- id: 0 -->
  - [ ] Remove `ToolRegistry` class and module file
  - [ ] Update `core/__init__.py` to remove registry export
- [ ] Update `@tool` decorator <!-- id: 1 -->
  - [ ] Remove `ToolRegistry` import from `tools/decorators.py`
  - [ ] Remove registration side effect; return `Tool` instance directly
- [ ] Update `tools/__init__.py` <!-- id: 2 -->
  - [ ] Remove `ToolRegistry` export
- [ ] Update `Agent` to hold tools directly <!-- id: 3 -->
  - [ ] Remove `ToolRegistry` imports from `agent/agent.py`
  - [ ] Replace registry lookup with explicit `list[Tool]`
  - [ ] Remove `ToolRegistry` imports from `agent/definition.py` if present
- [ ] Update `skills/tools.py` <!-- id: 4 -->
  - [ ] Remove `CallableTool` wrapper
  - [ ] Evaluate whether to delete or move remaining content

## Testing Phase

- [ ] Remove `ToolRegistry` usage from all tests <!-- id: 5 -->
  - [ ] Pass tools directly to `Agent` constructor or `add_tools()`
- [ ] Run full `pytest` suite <!-- id: 6 -->
  - [ ] Fix any failing tests due to removed registry

## Verification Phase

- [ ] Confirm `core/registry.py` does not exist <!-- id: 7 -->
- [ ] Confirm `@tool` decorator has no side effects <!-- id: 8 -->
- [ ] Confirm `Agent` does not import from `core.registry` <!-- id: 9 -->
- [ ] Confirm `ToolRegistry` is not exported from `tinycua_sdk` <!-- id: 10 -->

## Documentation Phase

- [ ] Update any internal docs referencing `ToolRegistry` <!-- id: 11 -->

## Review and Merge

- [ ] Create pull request <!-- id: 12 -->
- [ ] Address review feedback <!-- id: 13 -->
- [ ] Merge to main branch <!-- id: 14 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement-plan` to execute these tasks*
*Last updated: 2026-04-29*
