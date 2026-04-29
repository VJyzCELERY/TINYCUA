# Implementation: Remove Core Registry

Delete `core/registry.py` (the `ToolRegistry` singleton). The SDK does not maintain global mutable state. Tools are composed explicitly via `Agent.add_tools()`.

## Context

- **Spec Reference**: `spec.md` — Stage 08 Remove Core Registry
- **Design Reference**: `design.md` — Stage 08 Design: Remove Core Registry
- **Priority**: P0
- **Estimated Effort**: S

## Proposed Changes

### Core

#### [DELETE] `core/registry.py`

- **Description of change**: Delete `core/registry.py` containing the `ToolRegistry` singleton.
- **Rationale**: Singletons are global mutable state and violate SDK statelessness.

#### [MODIFY] `core/__init__.py`

- **Description of change**: Remove `ToolRegistry` export.
- **Rationale**: The class no longer exists and must not be exposed.

### Tools

#### [MODIFY] `tools/decorators.py`

- **Description of change**: Remove `ToolRegistry` import and registration side effect from `@tool`. The decorator should return a `Tool` instance directly.
- **Rationale**: `@tool` should be side-effect free; callers decide what to do with the returned `Tool`.

#### [MODIFY] `tools/__init__.py`

- **Description of change**: Remove `ToolRegistry` export.
- **Rationale**: The class no longer exists and must not be exposed.

### Agent

#### [MODIFY] `agent/agent.py`

- **Description of change**: Remove `ToolRegistry` imports and registry lookup. Agent should hold its own `list[Tool]` directly.
- **Rationale**: Explicit composition via `Agent(tools=[...])` is clearer than implicit global registration.

#### [MODIFY] `agent/definition.py`

- **Description of change**: Remove `ToolRegistry` imports if present.
- **Rationale**: No dependency on the deleted registry.

### Skills

#### [MODIFY] `skills/tools.py`

- **Description of change**: Remove `CallableTool` wrapper (it depends on `ToolRegistry` patterns). Evaluate whether the file should be deleted or moved if it only contains tools for skill progressive disclosure.
- **Rationale**: Eliminate all code that depends on registry patterns.

### Tests

#### [MODIFY] Remaining tests

- **Description of change**: Remove all `ToolRegistry` usage. Pass tools directly to `Agent` constructor or `add_tools()`.
- **Rationale**: Tests must not reference deleted code.

## Architecture Changes

| Component        | Change Type | Description                        |
|------------------|-------------|------------------------------------|
| `core/registry`  | Remove      | Delete `ToolRegistry` singleton    |
| `tools/decorators`| Modify     | Remove registration side effect    |
| `tools/__init__` | Modify      | Remove registry export             |
| `agent/agent`    | Modify      | Remove registry lookup; hold list  |
| `agent/definition`| Modify     | Remove registry imports            |
| `skills/tools`   | Modify      | Remove `CallableTool` wrapper      |
| Tests            | Modify      | Remove all registry references     |

## Data Model Changes

None.

## API Changes

### Removed Symbols

| Symbol           | Location         | Migration Path                    |
|------------------|------------------|-----------------------------------|
| `ToolRegistry`   | `core/registry`  | Pass tools directly to `Agent`    |

### Modified Interfaces

| Interface   | Change                                                    |
|-------------|-----------------------------------------------------------|
| `@tool`     | No longer registers globally; returns `Tool` instance only |
| `Agent`     | Accepts `tools` list directly; no registry lookup         |

## Verification Plan

### Automated Tests

- [ ] Unit tests for `@tool` decorator
- [ ] Unit tests for `Agent` tool list handling
- [ ] Full `pytest` suite passes

### Manual Verification

- [ ] Confirm `core/registry.py` does not exist
- [ ] Confirm `ToolRegistry` is not exported from `tinycua_sdk`

### Performance Considerations

- [ ] No performance impact; removed a global lookup mechanism.

## Rollout Strategy

1. **Phase 1** (Remove registry): Delete `core/registry.py`, clean up exports.
2. **Phase 2** (Update decorator and agent): Make `@tool` side-effect free; update `Agent` to hold tools directly.
3. **Phase 3** (Update tests): Remove all registry references from tests and verify `pytest` passes.

## Dependencies

### External Dependencies

None.

### Internal Dependencies

- [ ] Depends on Stage 01, Stage 02
- [ ] Blocks: None (can proceed in parallel with Stages 03–07, 09–10)

## Risks and Mitigations

| Risk                                              | Impact | Mitigation                                      |
|---------------------------------------------------|--------|-------------------------------------------------|
| Hidden references to `ToolRegistry` remain        | Medium | Run `grep -r "ToolRegistry"` across codebase   |
| Tests fail due to implicit registration reliance  | Medium | Update all tests to pass tools explicitly      |

---

*Generated from spec.md and design.md*
*Last updated: 2026-04-29*
