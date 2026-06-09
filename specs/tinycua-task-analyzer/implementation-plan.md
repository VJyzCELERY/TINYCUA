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


# ---------------------------------------------------------------------------
# Integration Tests (queue-based, mock LLM) — aligned with spec scenarios 1-5
# ---------------------------------------------------------------------------


def test_task_analyzer_integration_with_tool_policy():
    """Spec Test 1: TaskAnalyzerNode integrates with NodeToolPolicy for
    mode-dependent tool filtering across all modes."""
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
        # recreation must include TaskInit/TaskCreate
        if mode == "recreation":
            assert "TaskInit" in node.tool_scope
            assert "TaskCreate" in node.tool_scope
        else:
            assert "TaskInit" not in node.tool_scope, f"TaskInit leaked into {mode}"
            assert "TaskCreate" not in node.tool_scope, f"TaskCreate leaked into {mode}"


def test_task_analyzer_lifecycle_hooks_in_queue():
    """Spec Test 2: TaskAnalyzerNode in a minimal queue with mock LLM to
    verify lifecycle hooks (on_start, on_end) fire correctly."""
    from unittest.mock import MagicMock

    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="initial_analysis")

    # Spy on lifecycle hooks
    node.on_start = MagicMock(wraps=node.on_start) if hasattr(node, "on_start") else MagicMock()
    node.on_end = MagicMock(wraps=node.on_end) if hasattr(node, "on_end") else MagicMock()

    # Provide a mock LLM that returns a plain response (no tool calls)
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "Analysis complete."
    mock_response.choices[0].message.tool_calls = []
    mock_llm.chat.completions.create.return_value = mock_response

    mock_session = MagicMock()
    mock_session.task = {"id": "root", "children": []}

    # Build a minimal queue
    from tinycua.queue import NodeQueue

    queue = NodeQueue()
    queue.add(node)

    # Run the queue (node will be called once)
    queue.run(llm=mock_llm, session=mock_session)

    # Verify lifecycle hooks fired
    node.on_start.assert_called()
    node.on_end.assert_called()


def test_task_analyzer_recreation_in_queue_receives_task_tools():
    """Spec Test 3: TaskAnalyzerNode(mode=recreation) in a queue after
    TaskCreateNode — verify the mock LLM received TaskInit/TaskCreate tools."""
    from unittest.mock import MagicMock

    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="recreation")

    # Build a mock LLM that captures the tools kwarg passed to it
    mock_llm = MagicMock()
    captured_tools = []

    def fake_create(**kwargs):
        captured_tools.extend(kwargs.get("tools", []))
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message = MagicMock()
        resp.choices[0].message.content = "Task recreated."
        resp.choices[0].message.tool_calls = []
        return resp

    mock_llm.chat.completions.create.side_effect = fake_create

    mock_session = MagicMock()
    mock_session.task = {"id": "root", "children": []}

    from tinycua.queue import NodeQueue

    queue = NodeQueue()
    queue.add(node)
    queue.run(llm=mock_llm, session=mock_session)

    # Extract tool names from captured tools (they are dicts with "function"."name")
    tool_names = []
    for t in captured_tools:
        if isinstance(t, dict):
            tool_names.append(t.get("function", {}).get("name", ""))
        else:
            tool_names.append(getattr(t, "function", {}).get("name", ""))

    assert "TaskInit" in tool_names, "TaskInit must be in tool scope for recreation mode"
    assert "TaskCreate" in tool_names, "TaskCreate must be in tool scope for recreation mode"


def test_task_analyzer_initial_analysis_in_queue_excludes_task_tools():
    """Spec Test 4: TaskAnalyzerNode(mode=initial_analysis) in a queue —
    verify the mock LLM does NOT receive TaskInit/TaskCreate tools."""
    from unittest.mock import MagicMock

    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="initial_analysis")

    mock_llm = MagicMock()
    captured_tools = []

    def fake_create(**kwargs):
        captured_tools.extend(kwargs.get("tools", []))
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message = MagicMock()
        resp.choices[0].message.content = "Initial analysis complete."
        resp.choices[0].message.tool_calls = []
        return resp

    mock_llm.chat.completions.create.side_effect = fake_create

    mock_session = MagicMock()
    mock_session.task = {"id": "root", "children": []}

    from tinycua.queue import NodeQueue

    queue = NodeQueue()
    queue.add(node)
    queue.run(llm=mock_llm, session=mock_session)

    tool_names = []
    for t in captured_tools:
        if isinstance(t, dict):
            tool_names.append(t.get("function", {}).get("name", ""))
        else:
            tool_names.append(getattr(t, "function", {}).get("name", ""))

    assert "TaskInit" not in tool_names, "TaskInit must NOT be in tool scope for initial_analysis"
    assert "TaskCreate" not in tool_names, "TaskCreate must NOT be in tool scope for initial_analysis"


def test_task_analyzer_task_tree_validation_none_raises_error():
    """Spec Test 5: Mock LLM returns without mutating session.task to a valid
    tree — NodeExecutionError must be raised when task tree is None."""
    import pytest
    from unittest.mock import MagicMock

    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.node import NodeExecutionError
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="initial_analysis")

    # LLM returns without mutating session.task — task stays None
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "No changes made."
    mock_response.choices[0].message.tool_calls = []
    mock_llm.chat.completions.create.return_value = mock_response

    mock_session = MagicMock()
    mock_session.task = None  # task is None — should trigger validation

    with pytest.raises(NodeExecutionError, match="task tree is None"):
        node(mock_llm, session=mock_session)
```

### Key Test Scenarios (Spec-Aligned Integration Tests)

- [ ] **Scenario 1** — `test_task_analyzer_integration_with_tool_policy`: TaskAnalyzerNode integrates with `NodeToolPolicy` for mode-dependent tool filtering across all modes
- [ ] **Scenario 2** — `test_task_analyzer_lifecycle_hooks_in_queue`: TaskAnalyzerNode in a minimal queue with mock LLM verifies lifecycle hooks (`on_start`, `on_end`) fire correctly
- [ ] **Scenario 3** — `test_task_analyzer_recreation_in_queue_receives_task_tools`: TaskAnalyzerNode(mode=recreation) in a queue after TaskCreateNode — verify mock LLM receives TaskInit/TaskCreate tools
- [ ] **Scenario 4** — `test_task_analyzer_initial_analysis_in_queue_excludes_task_tools`: TaskAnalyzerNode(mode=initial_analysis) in a queue — verify mock LLM does NOT receive TaskInit/TaskCreate tools
- [ ] **Scenario 5** — `test_task_analyzer_task_tree_validation_none_raises_error`: Mock LLM returns without mutating session.task — `NodeExecutionError` raised when task tree is `None` after completion

### Additional Unit-Level Tests

- [ ] **Unit 1** — `test_task_analyzer_all_five_modes_are_valid`: All five analysis modes are accepted by the constructor
- [ ] **Unit 2** — `test_task_analyzer_recreation_allows_task_creation_tools`: `recreation` mode includes TaskInit and TaskCreate in tool scope
- [ ] **Unit 3** — `test_task_analyzer_non_recreation_excludes_task_creation_tools`: All modes except recreation exclude TaskInit and TaskCreate
- [ ] **Unit 4** — `test_task_analyzer_invalid_mode_raises_value_error`: Unknown modes raise `ValueError` with valid mode list
- [ ] **Unit 5** — `test_task_analyzer_default_mode_is_initial_analysis`: Default mode is `initial_analysis` (replaces legacy `analysis`)

## Verification Plan

### Automated Tests

- [ ] Integration tests (spec-aligned, defined above) — these must pass for implementation to be complete:
  1. `test_task_analyzer_integration_with_tool_policy` — mode-dependent tool filtering across all modes
  2. `test_task_analyzer_lifecycle_hooks_in_queue` — queue-based lifecycle hooks fire correctly
  3. `test_task_analyzer_recreation_in_queue_receives_task_tools` — recreation mode in queue receives TaskInit/TaskCreate tools
  4. `test_task_analyzer_initial_analysis_in_queue_excludes_task_tools` — initial_analysis mode in queue excludes TaskInit/TaskCreate
  5. `test_task_analyzer_task_tree_validation_none_raises_error` — NodeExecutionError when task tree is None
- [ ] Unit tests for tool scope filtering, task tree validation, error handling (5 additional unit tests defined above)
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
