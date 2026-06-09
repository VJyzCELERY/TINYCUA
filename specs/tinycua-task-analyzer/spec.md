# Feature Specification: TinyCUATaskAnalyzerNode

**Status**: Draft
**Created**: 2026-06-10
**Last Updated**: 2026-06-10
**Subproject(s) Affected**: tinycua (loops/task_analyzer)

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a mode-aware `TaskAnalyzerNode` that performs task analysis, decomposition, and refinement so that **TinyCUA worker orchestration** can **mutate the task tree according to the current analysis mode without returning opaque mutation instructions**.
- **Gaps**: The existing `TinyCUATaskAnalyzerNode` implementation supports only three modes (`analysis`, `initial_analysis`, `effort_loop_decomposition`) and lacks the full mode set specified in the target architecture (`recreation`, `reanalysis`, `local_replan`). Tool scope filtering is incomplete — recreation mode should allow TaskInit/TaskCreate tools but currently does not. The node does not validate that the task tree is non-None after completion.
- **Non-Goals**: This spec does NOT cover task creation (TaskCreateNode), task execution (TaskExecutor), task assessment (TaskAssessor), or result review (ResultReviewer). It does NOT cover queue routing or WorkerNode decision logic.
- **Constraints**: Must work without modifying `tinycua-sdk` public APIs. Must use mode-dependent tool scope via `NodeToolPolicy`. Must directly mutate `session.task` through TinyCUALoop task helpers — must NOT return opaque mutation instructions.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A TinyCUA WorkerNode decides to create or refine a task tree. It spawns a `TinyCUATaskAnalyzerNode` with the appropriate mode (`initial_analysis`, `recreation`, `reanalysis`, `effort_loop_decomposition`, or `local_replan`). The TaskAnalyzer receives the previous query/continuation, applies mode-specific tool scoping, invokes the LLM with task-structure tools, and directly mutates `session.task` through TinyCUALoop task helpers. The final response summarizes the task changes.

### Acceptance Scenarios

1. **Given** a `TinyCUATaskAnalyzerNode(mode="initial_analysis")`, **When** it is called after TaskCreateNode, **Then** it must NOT have TaskInit/TaskCreate tools available and must refine the existing task tree.
2. **Given** a `TinyCUATaskAnalyzerNode(mode="recreation")`, **When** it is called, **Then** it MUST have TaskInit/TaskCreate tools available for LLM-assisted task tree replacement.
3. **Given** a `TinyCUATaskAnalyzerNode(mode="reanalysis")`, **When** it is called, **Then** it must NOT have TaskInit/TaskCreate tools and must refine the existing task tree without full replacement.
4. **Given** a `TinyCUATaskAnalyzerNode(mode="effort_loop_decomposition")`, **When** it is called during an effort-loop pass, **Then** it must NOT have TaskInit/TaskCreate tools and must decompose tasks selected by TaskAssessor.
5. **Given** a `TinyCUATaskAnalyzerNode(mode="local_replan")`, **When** it is called after ResultReviewer replan decision, **Then** it must NOT have TaskInit/TaskCreate tools (unless mode explicitly allows it) and must perform local replan of the active task or local region.
6. **Given** a `TinyCUATaskAnalyzerNode` completes execution, **When** the task tree is `None`, **Then** the node MUST raise a `NodeExecutionError`.
7. **Given** a `TinyCUATaskAnalyzerNode` with an invalid mode, **When** it is instantiated, **Then** it MUST raise a `ValueError` with the list of valid modes.
8. **Given** a `TinyCUATaskAnalyzerNode` with no mode specified, **When** it is instantiated, **Then** mode MUST default to `initial_analysis`.

### Edge Cases

- What happens when the task tree is `None` after completion? The node must raise a `NodeExecutionError`.
- What happens when an unknown mode is provided? The node must raise `ValueError` with valid mode list.
- What happens when TaskInit/TaskCreate tools are used in a non-recreation mode? The tool scope must exclude them; the LLM should not have access.
- What happens with empty input? The node must handle empty or null input gracefully.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide `TinyCUATaskAnalyzerNode(ProcessNode)` that performs mode-specific task analysis.
- **FR-002**: System MUST support five analysis modes: `initial_analysis`, `recreation`, `reanalysis`, `effort_loop_decomposition`, `local_replan`.
- **FR-003**: System MUST apply mode-dependent tool scope via `NodeToolPolicy` — TaskInit/TaskCreate tools are ONLY available in `recreation` mode.
- **FR-004**: System MUST directly mutate `session.task` through TinyCUALoop task helpers — must NOT return opaque mutation instructions.
- **FR-005**: System MUST validate that the task tree is non-None after completion and raise a `NodeExecutionError` if it is `None`.
- **FR-006**: System MUST raise `ValueError` for unknown analysis modes.
- **FR-007**: System MUST log mode and completion status via the existing logging pattern.
- **FR-008**: System MUST inherit retry, validation, and lifecycle behavior from `ProcessNode`.
- **FR-009**: System MUST NOT modify `tinycua-sdk` public APIs.
- **FR-010**: System MUST default to `initial_analysis` mode when no mode is specified.

### Key Entities _(include if feature involves data)_

- **TaskAnalyzerMode**: Enumeration of supported analysis modes (`initial_analysis`, `recreation`, `reanalysis`, `effort_loop_decomposition`, `local_replan`).
- **TaskTree**: The root task tree stored in `session.task`. Must be non-None after TaskAnalyzer completion.
- **NodeToolPolicy**: Mode-dependent tool scope that controls which task tools are available to the LLM.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Five modes supported**: `initial_analysis`, `recreation`, `reanalysis`, `effort_loop_decomposition`, `local_replan` are all valid modes.
- [ ] **Tool scope correct**: TaskInit/TaskCreate tools are ONLY available in `recreation` mode; excluded from all other modes.
- [ ] **Direct mutation**: TaskAnalyzer uses TinyCUALoop task helpers to mutate `session.task` directly.
- [ ] **Task tree validation**: Node raises contract violation if task tree is `None` after completion.
- [ ] **Invalid mode rejected**: Instantiating with an unknown mode raises `ValueError`.
- [ ] **Logging works**: Mode and completion status are logged via the existing pattern.
- [ ] **Retry works**: Inherits `ProcessNode` retry behavior with `NodeRetryPolicy`.
- [ ] **No SDK changes**: All implementation lives in `tinycua.loops.task_analyzer` without modifying `tinycua-sdk`.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_task_analyzer_node.py`: Consolidated test file covering all five modes, tool scope validation, task tree validation, and direct mutation.

### Integration Tests

- Test TaskAnalyzerNode integration with `NodeToolPolicy` for mode-dependent tool filtering.
- Test TaskAnalyzerNode in a minimal queue with mock LLM to verify lifecycle hooks fire correctly.
- Test TaskAnalyzerNode(mode=recreation) in a queue after TaskCreateNode — verify LLM receives TaskInit/TaskCreate tools.
- Test TaskAnalyzerNode(mode=initial_analysis) in a queue — verify LLM does NOT receive TaskInit/TaskCreate tools.
- Test TaskAnalyzerNode task tree validation — mock LLM returns without mutating session.task, verify NodeExecutionError raised.

### Manual Tests _(if applicable)_

- None required for this milestone.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Five analysis modes | TODO | |
| Mode-dependent tool scope | TODO | |
| Task tree validation | TODO | |
| Direct mutation via task helpers | TODO | |
| Unit tests | TODO | |
| Integration tests | TODO | |

---

## Open Questions _(optional)_

1. **local_replan TaskInit/TaskCreate allowance**: The design doc says "Must NOT use TaskInit/TaskCreate tools unless mode explicitly allows it." Should `local_replan` ever allow TaskInit/TaskCreate, or is the default exclusion sufficient for the prototype?
   - **Owner**: @VJyzCELERY
   - **Status**: Proposed
   - **Proposed Answer**: Default exclusion is sufficient for the prototype. If a future need arises, the mode can be extended.

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices beyond what's in the design docs)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
