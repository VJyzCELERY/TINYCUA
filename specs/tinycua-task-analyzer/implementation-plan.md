# Implementation: TinyCUATaskAnalyzerNode — Full Five-Mode Support

Extend `TinyCUATaskAnalyzerNode` to support all five analysis modes from the target architecture, with correct mode-dependent tool scoping and task tree validation after completion.

## Context

- **Spec Reference**: `./spec.md` — TinyCUATaskAnalyzerNode Feature Specification
- **Design Reference**: `./design.md` — Design Document: TinyCUATaskAnalyzerNode
- **Priority**: P1
- **Estimated Effort**: S

## Environment Pre-requisites

### Configuration

- [ ] **None** — this feature has no configuration dependencies

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| [ ] **None** — no external services needed | | | |

### Data / Fixtures

- [ ] **None** — no data or fixtures needed

### Access / Permissions

- [ ] **None** — no special access required

### Developer Tooling

- [ ] **Runtime**: Python 3.12+, uv
- [ ] **Package manager**: uv
- [ ] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/unit/test_task_analyzer_node.py
"""Integration tests for TinyCUATaskAnalyzerNode full five-mode support."""


def test_task_analyzer_all_five_modes_are_valid():
    """All five analysis modes are accepted by TaskAnalyzerNode."""
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

    config = NodeConfigBase()
    for mode in [
        "initial_analysis",
        "recreation",
        "reanalysis",
        "effort_loop_decomposition",
        "local_replan",
    ]:
        node = TinyCUATaskAnalyzerNode(config=config, mode=mode)
        assert node.mode == mode


def test_task_analyzer_recreation_allows_task_creation_tools():
    """recreation mode includes TaskInit and TaskCreate in tool scope."""
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="recreation")
    assert "TaskInit" in node.tool_scope
    assert "TaskCreate" in node.tool_scope


def test_task_analyzer_non_recreation_excludes_task_creation_tools():
    """All modes except recreation exclude TaskInit and TaskCreate."""
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

    config = NodeConfigBase()
    for mode in [
        "initial_analysis",
        "reanalysis",
        "effort_loop_decomposition",
        "local_replan",
    ]:
        node = TinyCUATaskAnalyzerNode(config=config, mode=mode)
        assert "TaskInit" not in node.tool_scope, f"TaskInit should not be in {mode}"
        assert "TaskCreate" not in node.tool_scope, f"TaskCreate should not be in {mode}"


def test_task_analyzer_invalid_mode_raises_value_error():
    """Instantiating with an unknown mode raises ValueError."""
    import pytest
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

    config = NodeConfigBase()
    with pytest.raises(ValueError, match="Unknown analysis mode"):
        TinyCUATaskAnalyzerNode(config=config, mode="nonexistent_mode")


def test_task_analyzer_default_mode_is_initial_analysis():
    """Default mode is 'initial_analysis' (not legacy 'analysis' mode)."""
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config)
    assert node.mode == "initial_analysis"
```

### Key Test Scenarios

- [ ] **Scenario 1**: All five modes are valid and accepted by the constructor
- [ ] **Scenario 2**: `recreation` mode allows TaskInit/TaskCreate tools; all other modes exclude them
- [ ] **Scenario 3**: Unknown modes raise `ValueError` with valid mode list
- [ ] **Scenario 4**: Default mode is `initial_analysis` (replaces legacy `analysis`)
- [ ] **Edge case**: Task tree validation — `NodeExecutionError` raised when task tree is `None` after completion

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for tool scope filtering, task tree validation, error handling
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify all five modes are documented in the class docstring
- [ ] Verify legacy `analysis` mode is removed (not just aliased)

### Performance Considerations

- [ ] No performance impact — changes are purely logical (mode set, tool scope, validation)

## Proposed Changes

### Module: tinycua/loops/task_analyzer.py

#### MODIFY src/tinycua/tinycua/loops/task_analyzer.py

- **Extend `_VALID_MODES`**: Replace the three-mode frozenset with the five-mode set: `initial_analysis`, `recreation`, `reanalysis`, `effort_loop_decomposition`, `local_replan`. Remove `analysis`.
- **Rationale**: The target architecture specifies exactly five modes. The legacy `analysis` mode is not in the target and should be removed.

#### MODIFY src/tinycua/tinycua/loops/task_analyzer.py — `_resolve_tool_scope()`

- **Update mode branching**: `recreation` → all task tools including TaskInit/TaskCreate. All other modes → task tools excluding TaskInit/TaskCreate.
- **Rationale**: FR-003 requires TaskInit/TaskCreate tools are ONLY available in `recreation` mode.

#### MODIFY src/tinycua/tinycua/loops/task_analyzer.py — new method `_validate_task_tree_non_none()`

- **Add validation method**: Check that `session.task` is not `None` after the LLM call completes. Raise `NodeExecutionError` if it is `None`.
- **Rationale**: FR-005 requires task tree validation after completion. This is a contract violation check.

#### MODIFY src/tinycua/tinycua/loops/task_analyzer.py — `__call__()`

- **Call validation**: After the LLM call and before returning, call `_validate_task_tree_non_none()` to enforce the contract.
- **Rationale**: Validation must happen after the LLM call since tool calls mutate the task tree during execution.

#### MODIFY src/tinycua/tinycua/loops/task_analyzer.py — constructor

- **Change default mode**: Change `mode` parameter default from `"analysis"` to `"initial_analysis"`.
- **Rationale**: The legacy `analysis` mode is being removed. Default should match the most common first-use mode.

#### MODIFY src/tinycua/tinycua/loops/task_analyzer.py — docstrings

- **Update class docstring**: Document all five modes and their tool scoping behavior.
- **Update module docstring**: Reflect the full five-mode support.
- **Rationale**: FR-007 requires logging and documentation of modes.

### Module: tests/unit/test_task_analyzer_node.py

#### MODIFY src/tinycua/tests/unit/test_task_analyzer_node.py

- **Update existing tests**: Fix tests that reference the legacy `analysis` mode to use `initial_analysis`.
- **Add five-mode tests**: Test all five modes are valid and accepted.
- **Add tool scope tests**: Test `recreation` allows TaskInit/TaskCreate; all others exclude them.
- **Add invalid mode test**: Test `ValueError` for unknown modes.
- **Add task tree validation test**: Test `NodeExecutionError` when task tree is `None` after completion.
- **Add default mode test**: Verify default is `initial_analysis`.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/loops/task_analyzer.py` | Modify | Extend mode set, tool scope, add task tree validation |
| `tests/unit/test_task_analyzer_node.py` | Modify | Add tests for all five modes, tool scope, validation |

## Data Model Changes

```python
# Updated valid modes (replaces three-mode set)
_TASK_ANALYZER_MODES = frozenset({
    "initial_analysis",
    "recreation",
    "reanalysis",
    "effort_loop_decomposition",
    "local_replan",
})
```

## API Changes

### Modified Constructor

| Parameter | Before | After | Change |
|-----------|--------|-------|--------|
| `mode` default | `"analysis"` | `"initial_analysis"` | Default changed to match target architecture |

### New Method

| Method | Description |
|--------|-------------|
| `_validate_task_tree_non_none(response)` | Validates task tree is non-None after completion; raises `NodeExecutionError` if `None` |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| (none) | | |

### Internal Dependencies

- [ ] Depends on `ProcessNode` base class (existing)
- [ ] Depends on `NodeExecutionError` from `tinycua.loops.node` (existing)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Removing `analysis` mode breaks existing callers | Medium | Check all call sites; `analysis` is not used in production code paths (design doc confirms) |
| Task tree validation misses edge cases | Low | Comprehensive unit tests for None tree, empty tree, and valid tree |
| Tool scope filtering has off-by-one errors | Low | Unit tests for each mode verifying exact tool list |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-10*
