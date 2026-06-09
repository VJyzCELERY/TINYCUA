# Design Document: TinyCUATaskAnalyzerNode

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-10

---

## Overview

This design extends `TinyCUATaskAnalyzerNode` in `tinycua.loops.task_analyzer` to support the full set of five analysis modes specified in the target architecture. The node is a `ProcessNode` that performs mode-specific task analysis, decomposition, and refinement. It directly mutates `session.task` through TinyCUALoop task helpers and does not return opaque mutation instructions. The design follows `src/tinycua/docs/design/loops/task_analyzer.md` and `src/tinycua/docs/design/tools/task.md`.

---

## Architecture

### Component Overview

```
TaskAnalyzerNode(ProcessNode)
├── mode: TaskAnalyzerMode (enum-like frozenset)
├── tool_scope: list[str]  (resolved from mode)
├── _resolve_tool_scope(mode) → list[str]
├── _validate_task_tree_non_none(response) → None
└── __call__(input) → LLMResult
        ├── build messages (inherited from ProcessNode)
        ├── call LLM with mode-scoped tools
        ├── validate task tree is non-None
        └── record output + propagate
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/loops/task_analyzer.py` | Modified | Extend mode set, tool scope, and task tree validation |
| `tinycua/config/node_config.py` | Referenced | `TinyCUATaskAnalyzerNodeConfig` per-node config |
| `tinycua/loops/node.py` | Referenced | `ProcessNode` base class |
| `tinycua/docs/design/tools/task.md` | Referenced | Tool scope per mode |
| `tinycua/docs/design/loops/task_analyzer.md` | Referenced | Target architecture for TaskAnalyzer |

---

## Data Model

### TaskAnalyzerMode

```python
# Valid analysis modes (frozenset for immutability)
_TASK_ANALYZER_MODES = frozenset({
    "initial_analysis",
    "recreation",
    "reanalysis",
    "effort_loop_decomposition",
    "local_replan",
})
```

### Tool Scope by Mode

| Mode | TaskInit/TaskCreate | Other Task Tools | Description |
|------|---------------------|------------------|-------------|
| `initial_analysis` | Excluded | TaskUpdate, TaskComplete, TaskDecompose | First analysis after TaskCreateNode |
| `recreation` | Allowed | TaskUpdate, TaskComplete, TaskDecompose | Full task tree rebuild/replacement |
| `reanalysis` | Excluded | TaskUpdate, TaskComplete, TaskDecompose | Refine existing tree without replacement |
| `effort_loop_decomposition` | Excluded | TaskUpdate, TaskComplete, TaskDecompose | Decompose tasks during effort passes |
| `local_replan` | Excluded | TaskUpdate, TaskComplete, TaskDecompose | Local replan after ResultReviewer replan |

### Task Tree Validation

```python
# After __call__ completes, task tree must not be None
# This is a contract violation — the loop owns root task and
# TaskAnalyzer mutations must produce a valid tree.
```

---

## API / Interface Contracts

### TinyCUATaskAnalyzerNode Constructor

```python
class TinyCUATaskAnalyzerNode(ProcessNode):
    def __init__(
        self,
        node_id: str = "task_analyzer",
        config: NodeConfigBase | None = None,
        mode: str = "initial_analysis",
    ) -> None:
        """
        Initialize TaskAnalyzerNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses default if None.
            mode: Analysis mode. Must be one of the five valid modes.

        Raises:
            ValueError: If mode is not in _TASK_ANALYZER_MODES.
        """
```

### Tool Scope Resolution

```python
def _resolve_tool_scope(self, mode: str) -> list[str]:
    """
    Resolve tool scope based on analysis mode.

    Args:
        mode: The analysis mode.

    Returns:
        List of tool names available in this mode.

    Raises:
        ValueError: If mode is not a recognized analysis mode.
    """
```

Mode resolution logic:
- `recreation` → all task tools including TaskInit/TaskCreate
- All other modes → task tools excluding TaskInit/TaskCreate

### Task Tree Validation

```python
def _validate_task_tree_non_none(self, response: LLMResult) -> None:
    """
    Validate that the task tree is non-None after completion.

    Raises:
        NodeExecutionError: If session.task is None after analysis.
    """
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Unknown mode | `ValueError("Unknown analysis mode: ...")` | Raised at construction time |
| Task tree is None after completion | `NodeExecutionError("Task tree is None after TaskAnalyzer completion")` | Contract violation |
| LLM failure | `NodeExecutionError` | Per `NodeRetryPolicy.on_retry_exhausted` |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Extend `_VALID_MODES` to include all five modes: `initial_analysis`, `recreation`, `reanalysis`, `effort_loop_decomposition`, `local_replan`
- [ ] Update `_resolve_tool_scope()` to allow TaskInit/TaskCreate only in `recreation` mode
- [ ] Add `_validate_task_tree_non_none()` method to check task tree after completion
- [ ] Call `_validate_task_tree_non_none()` at the end of `__call__()` before returning
- [ ] Update module docstring and class docstring to reflect all five modes
- [ ] Write unit tests for all five modes, tool scope validation, and task tree validation

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- None for this milestone. Mode-specific continuation prompts and advanced task tree inspection are deferred.

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use a `frozenset` for valid modes rather than a Python `Enum`.
   - **Reason**: The existing codebase uses `frozenset` for mode validation (see `_VALID_MODES` in current `task_analyzer.py`). A `frozenset` is consistent with the existing pattern and avoids introducing a new enum type for a simple string-based mode.
   - **Alternatives Considered**: Python `Enum` — rejected for introducing unnecessary type complexity when the mode is used as a string throughout the codebase.

2. **Decision**: Task tree validation happens after the LLM call, not before.
   - **Reason**: The LLM call is what mutates the task tree through tool calls. Validating before the call would be premature — the tree could be valid before and invalid after (if the LLM clears it). Validating after ensures the contract is enforced at the point of completion.
   - **Alternatives Considered**: Pre-call validation — rejected because it doesn't catch mutations that happen during the LLM call.

3. **Decision**: `local_replan` uses the same tool scope as `initial_analysis` and `reanalysis` (no TaskInit/TaskCreate).
   - **Reason**: The design doc says "Must NOT use TaskInit/TaskCreate tools unless mode explicitly allows it." For the prototype, the default exclusion is sufficient. If a future need arises, the mode can be extended.
   - **Alternatives Considered**: Allowing TaskInit/TaskCreate in `local_replan` — rejected for the prototype per design doc guidance.

4. **Decision**: Keep the existing `analysis` mode as an alias or remove it.
   - **Reason**: The current implementation includes an `analysis` mode that is not in the target architecture's five modes. The target architecture specifies `initial_analysis`, `recreation`, `reanalysis`, `effort_loop_decomposition`, and `local_replan`. The `analysis` mode should be removed or aliased to avoid confusion.
   - **Alternatives Considered**: Keep `analysis` as a sixth mode — rejected because it's not in the target architecture and could confuse maintainers.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Removing `analysis` mode breaks existing callers | Medium | Medium | Check all call sites; `analysis` is not used in production code paths |
| Task tree validation misses edge cases | Low | High | Comprehensive unit tests for None tree, empty tree, and valid tree |
| Tool scope filtering has off-by-one errors | Low | Medium | Unit tests for each mode verifying exact tool list |
| `local_replan` mode ambiguity | Low | Low | Clear docstring and test coverage; mode behavior is identical to `initial_analysis` for tool scope |

---

## Open Questions _(optional)_

1. **Should `analysis` mode be preserved as an alias?**
   - **Status**: Proposed
   - **Proposed Answer**: Remove `analysis` mode. The target architecture specifies exactly five modes. If backward compatibility is needed, add a deprecation warning and alias `analysis` to `initial_analysis`.

---

## References

- Spec: `./spec.md`
- Design docs:
  - `src/tinycua/docs/design/loops/task_analyzer.md` — target architecture for TaskAnalyzerNode
  - `src/tinycua/docs/design/tools/task.md` — task tool scope per node
  - `src/tinycua/docs/design/models/task.md` — task model and tree structure
  - `src/tinycua/docs/design/loops/worker.md` — WorkerNode routes that spawn TaskAnalyzer
  - `src/tinycua/docs/design/loops/analysis_effort.md` — AnalysisEffortNode that spawns TaskAnalyzer
  - `src/tinycua/docs/design/config/node_config.md` — `TinyCUATaskAnalyzerNodeConfig`
- Issue: [#87](https://github.com/VJyzCELERY/TINYCUA/issues/87) — Milestone 2.6
