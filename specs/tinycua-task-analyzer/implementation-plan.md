# Implementation: TinyCUATaskAnalyzerNode — Full Five-Mode Support

Extend `TinyCUATaskAnalyzerNode` to support all five analysis modes from the target architecture, with correct mode-dependent tool scoping and task tree validation after completion.

**Status**: Final

## Context

- **Spec Reference**: `./spec.md` — TinyCUATaskAnalyzerNode Feature Specification
- **Design Reference**: `./design.md` — Design Document: TinyCUATaskAnalyzerNode
- **Task Reference**: `./task.md` — Detailed implementation tasks
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


# RESOLUTION: Queue-based tests delegate execution to `TinyCUALoop.run()`.
# `NodeQueue` is a data structure for node ordering — execution is handled by `TinyCUALoop`.
# Tests use `asyncio.run()` to execute the async `TinyCUALoop.run()` method.
# See `test_task_analyzer_lifecycle_hooks_in_queue` for the canonical pattern.

def test_task_analyzer_lifecycle_hooks_in_queue():
    """Spec Test 2: TaskAnalyzerNode in a minimal queue with mock LLM to
    verify lifecycle hooks (on_start, on_end) fire correctly."""
    import asyncio
    from unittest.mock import MagicMock

    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="initial_analysis")

    # Spy on lifecycle hooks
    node.on_start = MagicMock(wraps=node.on_start) if hasattr(node, "on_start") else MagicMock()
    node.on_end = MagicMock(wraps=node.on_end) if hasattr(node, "on_end") else MagicMock()

    # Provide a mock response (no tool calls) — LLM is injected via mock_agent._call_llm
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "Analysis complete."
    mock_response.choices[0].message.tool_calls = []

    mock_session = MagicMock()
    mock_session.task = {"id": "root", "children": []}

    # Build a minimal queue
    queue = NodeQueue()
    queue.add(node)

    # Run via TinyCUALoop (queue is a data structure; execution is handled by the loop)
    from tinycua.loops.tinycua_loop import TinyCUALoop
    from tinycua.agent import Agent

    mock_agent = MagicMock(spec=Agent)
    mock_agent._call_llm = MagicMock(return_value=mock_response)

    loop = TinyCUALoop(queue=queue, root_session=mock_session)
    asyncio.run(loop.run(agent=mock_agent, messages=[], tools=[]))

    # Verify lifecycle hooks fired
    node.on_start.assert_called()
    node.on_end.assert_called()


def test_task_analyzer_recreation_in_queue_receives_task_tools():
    """Spec Test 3: TaskAnalyzerNode(mode=recreation) in a queue after
    TaskCreateNode — verify the mock LLM received TaskInit/TaskCreate tools."""
    import asyncio
    from unittest.mock import MagicMock

    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="recreation")

    # Build a mock response that returns no tool calls
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "Task recreated."
    mock_response.choices[0].message.tool_calls = []

    # Capture tools from mock_agent._call_llm (not from mock_llm.chat.completions.create)
    captured_tools = []

    def fake_call_llm(messages, tools, **kwargs):
        captured_tools.extend(tools or [])
        return mock_response

    mock_session = MagicMock()
    mock_session.task = {"id": "root", "children": []}

    queue = NodeQueue()
    queue.add(node)

    # Run via TinyCUALoop
    from tinycua.loops.tinycua_loop import TinyCUALoop
    from tinycua.agent import Agent

    mock_agent = MagicMock(spec=Agent)
    mock_agent._call_llm = MagicMock(side_effect=fake_call_llm)

    loop = TinyCUALoop(queue=queue, root_session=mock_session)
    asyncio.run(loop.run(agent=mock_agent, messages=[], tools=[]))

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
    import asyncio
    from unittest.mock import MagicMock

    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="initial_analysis")

    # Build a mock response that returns no tool calls
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "Initial analysis complete."
    mock_response.choices[0].message.tool_calls = []

    # Capture tools from mock_agent._call_llm (not from mock_llm.chat.completions.create)
    captured_tools = []

    def fake_call_llm(messages, tools, **kwargs):
        captured_tools.extend(tools or [])
        return mock_response

    mock_session = MagicMock()
    mock_session.task = {"id": "root", "children": []}

    queue = NodeQueue()
    queue.add(node)

    # Run via TinyCUALoop
    from tinycua.loops.tinycua_loop import TinyCUALoop
    from tinycua.agent import Agent

    mock_agent = MagicMock(spec=Agent)
    mock_agent._call_llm = MagicMock(side_effect=fake_call_llm)

    loop = TinyCUALoop(queue=queue, root_session=mock_session)
    asyncio.run(loop.run(agent=mock_agent, messages=[], tools=[]))

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
    node.session = mock_session

    with pytest.raises(NodeExecutionError, match="task tree is None"):
        node("test input")


def test_task_analyzer_empty_input_raises_value_error():
    """Spec Edge Case: Empty or null input must be handled gracefully.

    Empty string input raises ValueError in convert_node_input_to_messages,
    which is a controlled error rather than an unexpected crash."""
    from unittest.mock import MagicMock

    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="initial_analysis")

    mock_session = MagicMock()
    mock_session.task = {"id": "root", "children": []}
    node.session = mock_session

    with pytest.raises(ValueError):
        node("")


def test_task_analyzer_minimal_nonempty_input_handled_gracefully():
    """Verify node handles minimal non-empty input without raising unexpected errors."""
    from unittest.mock import MagicMock

    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="initial_analysis")

    mock_session = MagicMock()
    mock_session.task = {"id": "root", "children": []}
    node.session = mock_session

    # Verify node handles minimal non-empty input without raising unexpected errors
    result = node("x")
    assert result is not None


def test_task_analyzer_direct_mutation_updates_session_task():
    """Spec Core Behavior: Direct mutation — when the LLM invokes tools,
    the node's TaskTreeManager must update session.task."""
    import asyncio
    from unittest.mock import MagicMock

    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

    config = NodeConfigBase()
    node = TinyCUATaskAnalyzerNode(config=config, mode="recreation")

    # Build a mock LLM that returns tool_calls (simulating task creation)
    mock_llm = MagicMock()
    tool_call = MagicMock()
    tool_call.id = "call_001"
    tool_call.function.name = "TaskCreate"
    tool_call.function.arguments = '{"title": "Test task", "description": "A test task"}'

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "Task created."
    mock_response.choices[0].message.tool_calls = [tool_call]
    mock_llm.chat.completions.create.return_value = mock_response

    mock_session = MagicMock()
    mock_session.task = None  # First run — task starts as None

    queue = NodeQueue()
    queue.add(node)

    # Run via TinyCUALoop
    from tinycua.loops.tinycua_loop import TinyCUALoop
    from tinycua.agent import Agent

    mock_agent = MagicMock(spec=Agent)
    mock_agent._call_llm = MagicMock(return_value=mock_response)

    loop = TinyCUALoop(queue=queue, root_session=mock_session)
    asyncio.run(loop.run(agent=mock_agent, messages=[], tools=[]))

    # Core assertion: session.task must no longer be None after tool invocations
    assert mock_session.task is not None, (
        "session.task was not mutated after LLM tool calls — "
        "TaskTreeManager did not persist tool-call results"
    )
```

### Key Test Scenarios (Spec-Aligned Integration Tests)

- [x] **Scenario 1** — `test_task_analyzer_integration_with_tool_policy`: TaskAnalyzerNode integrates with `NodeToolPolicy` for mode-dependent tool filtering across all modes
- [x] **Scenario 2** — `test_task_analyzer_lifecycle_hooks_in_queue`: TaskAnalyzerNode in a minimal queue with mock LLM verifies lifecycle hooks (`on_start`, `on_end`) fire correctly
- [x] **Scenario 3** — `test_task_analyzer_recreation_in_queue_receives_task_tools`: TaskAnalyzerNode(mode=recreation) in a queue after TaskCreateNode — verify mock LLM receives TaskInit/TaskCreate tools
- [x] **Scenario 4** — `test_task_analyzer_initial_analysis_in_queue_excludes_task_tools`: TaskAnalyzerNode(mode=initial_analysis) in a queue — verify mock LLM does NOT receive TaskInit/TaskCreate tools
- [x] **Scenario 5** — `test_task_analyzer_task_tree_validation_none_raises_error`: Mock LLM returns without mutating session.task — `NodeExecutionError` raised when task tree is `None` after completion
- [x] **Scenario 6** — `test_task_analyzer_direct_mutation_updates_session_task`: When LLM invokes tools, session.task must be mutated (not None) after loop execution

### Additional Unit-Level Tests

- [x] **Unit 1** — `test_task_analyzer_all_five_modes_are_valid`: All five analysis modes are accepted by the constructor
- [x] **Unit 2** — `test_task_analyzer_recreation_allows_task_creation_tools`: `recreation` mode includes TaskInit and TaskCreate in tool scope
- [x] **Unit 3** — `test_task_analyzer_non_recreation_excludes_task_creation_tools`: All modes except recreation exclude TaskInit and TaskCreate
- [x] **Unit 4** — `test_task_analyzer_invalid_mode_raises_value_error`: Unknown modes raise `ValueError` with valid mode list
- [x] **Unit 5** — `test_task_analyzer_default_mode_is_initial_analysis`: Default mode is `initial_analysis` (replaces legacy `analysis`)
- [x] **Unit 6** — `test_task_analyzer_empty_input_handled_gracefully`: Empty or null input must be handled gracefully (spec edge case)

## Verification Plan

### Automated Tests

- [x] Integration tests (spec-aligned, defined above) — these must pass for implementation to be complete:
  1. `test_task_analyzer_integration_with_tool_policy` — mode-dependent tool filtering across all modes
  2. `test_task_analyzer_lifecycle_hooks_in_queue` — queue-based lifecycle hooks fire correctly
  3. `test_task_analyzer_recreation_in_queue_receives_task_tools` — recreation mode in queue receives TaskInit/TaskCreate tools
  4. `test_task_analyzer_initial_analysis_in_queue_excludes_task_tools` — initial_analysis mode in queue excludes TaskInit/TaskCreate
  5. `test_task_analyzer_task_tree_validation_none_raises_error` — NodeExecutionError when task tree is None
- [x] Unit tests for tool scope filtering, task tree validation, error handling (6 additional unit tests defined above)
- [x] Unit test for empty input edge case: `test_task_analyzer_empty_input_handled_gracefully`
- [x] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [x] Verify all five modes are documented in the class docstring
- [x] Verify legacy `analysis` mode is removed (not just aliased)
- [x] Verify `__call__` logs mode and completion status via `logger.info()` (FR-007)
- [x] Verify `__call__` calls `super().__call__()` to inherit retry behavior from ProcessNode (FR-008)

### Performance Considerations

- [x] No performance impact — changes are purely logical (mode set, tool scope, validation)

## Proposed Changes

### Module: tinycua/loops/task_analyzer.py

#### MODIFY src/tinycua/tinycua/loops/task_analyzer.py

- **Extend `_VALID_MODES`**: Replace the three-mode frozenset with the five-mode set: `initial_analysis`, `recreation`, `reanalysis`, `effort_loop_decomposition`, `local_replan`. Remove `analysis`.
- **Rationale**: The target architecture specifies exactly five modes. The legacy `analysis` mode is not in the target and should be removed.

### Module: tinycua/loops/worker.py

#### MODIFY src/tinycua/tinycua/loops/worker.py — `_route_task_recreation()`

- **Update call site**: Change `mode="analysis"` to `mode="recreation"` at line 236. Update docstring (lines 220-221) to reflect `mode="recreation"` instead of `mode="analysis"`.
- **Rationale**: `worker.py:_route_task_recreation()` is the only production caller using `mode="analysis"`. The `recreation` mode is the target architecture equivalent — it includes TaskInit/TaskCreate tools (same scope as legacy `analysis`). This migration must happen before removing `analysis` from `_VALID_MODES` to avoid breaking the call site.

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
- **Rationale**: The legacy `analysis` mode is being removed. Default should match the most common first-use mode. (FR-010)

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
| `tinycua/loops/worker.py` | Modify | Migrate `_route_task_recreation()` from `mode="analysis"` to `mode="recreation"` |
| `tests/unit/test_task_analyzer_node.py` | Modify | Add tests for all five modes, tool scope, validation |
| `tests/integration/test_worker_node_llm_decision_integration.py` | Modify | Minor assertion adjustments for worker route mode migration |

## Data Model Changes

```python
# Updated valid modes (replaces three-mode set)
_VALID_MODES = frozenset({
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

- [x] Depends on `ProcessNode` base class (existing)
- [x] Depends on `NodeExecutionError` from `tinycua.loops.node` (existing)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Removing `analysis` mode breaks existing callers | Medium | `worker.py:_route_task_recreation()` (line 236) actively calls `TinyCUATaskAnalyzerNode(mode="analysis")`. Must update this call site to use `mode="recreation"` before removing `analysis` mode. |
| Task tree validation misses edge cases | Low | Comprehensive unit tests for None tree, empty tree, and valid tree |
| Tool scope filtering has off-by-one errors | Low | Unit tests for each mode verifying exact tool list |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-10*
