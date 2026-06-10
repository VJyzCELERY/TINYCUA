# Feature Specification: TinyCUATaskAssessorNode

**Status**: Draft
**Created**: 2026-06-10
**Last Updated**: 2026-06-10
**Subproject(s) Affected**: tinycua

---

## Problem Statement _(mandatory)_

- **Goals**: Provide task tree assessment capability so TinyCUA can select unfinished tasks for decomposition or reanalysis during effort-loop and reviewer-replan flows.
- **Gaps**: The current TinyCUA architecture lacks a dedicated node for evaluating task completeness and selecting which tasks need further processing. Without this, the effort loop cannot determine which tasks to send to TaskAnalyzer, and the reviewer replan path cannot identify tasks that need local replanning.
- **Non-Goals**: This spec does NOT cover task execution (TaskExecutor), task analysis/decomposition (TaskAnalyzer), or task creation (TaskCreate). It does NOT cover the full reviewer replan integration beyond the assessor's role.
- **Contracts to honor**: Must integrate with existing `ProcessNode` base class, `NodeQueue` mechanics, and `AnalysisEffortNode` effort-loop prepending behavior.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

When TinyCUA is processing a complex task that requires decomposition, the `AnalysisEffortNode` prepends `[TaskAssessor, TaskAnalyzer]` pairs to the queue. The `TaskAssessorNode` evaluates the current task tree, identifies unfinished tasks, and selects them for the `TaskAnalyzer` to decompose further. If no unfinished tasks exist, the assessor signals that no analyzer pass is needed, preventing wasted LLM invocations.

### Acceptance Scenarios

1. **Given** a task tree with mixed completed and pending tasks, **When** TaskAssessor runs in effort-loop mode, **Then** it selects only unfinished tasks (status != 'completed') for TaskAnalyzer processing.
2. **Given** a task tree where all tasks are completed, **When** TaskAssessor runs, **Then** it returns an empty selection list and signals no analyzer pass is needed.
3. **Given** TaskAssessor completes with selected tasks, **When** the queue advances, **Then** TaskAnalyzer is the next node in the queue.
4. **Given** TaskAssessor completes with no selected tasks, **When** the queue advances, **Then** TaskAnalyzer is skipped and the queue advances to the next appropriate node (e.g., AnalysisEffortNode).
5. **Given** TaskAssessor runs in reviewer-replan mode (future), **When** evaluating the local region, **Then** it selects unfinished tasks in the active task's local region.

### Edge Cases

- What happens when the task tree is empty? The assessor returns an empty selection.
- How does the system handle malformed LLM responses? The assessor logs a warning and treats the response as an empty selection.
- What is the behavior with null/None task tree? The assessor handles gracefully and returns empty selection.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST implement `TinyCUATaskAssessorNode` as a concrete `ProcessNode`.
- **FR-002**: System MUST evaluate the task tree and select only unfinished tasks (status != 'completed').
- **FR-003**: System MUST support effort-loop mode for full-tree assessment.
- **FR-004**: System MUST support reviewer-replan mode for local-region assessment (future milestone).
- **FR-005**: System MUST return a list of selected task IDs for TaskAnalyzer consumption.
- **FR-006**: System MUST signal when no tasks are selected to prevent unnecessary analyzer passes.
- **FR-007**: System MUST integrate with `AnalysisEffortNode` queue mechanics.
- **FR-008**: System MUST parse LLM responses to extract selected task IDs.
- **FR-009**: System MUST handle malformed LLM responses gracefully with logging.
- **FR-010**: System MUST propagate selected task list for downstream consumption.

### Key Entities _(include if feature involves data)_

- **TaskAssessorNode**: ProcessNode that evaluates task tree and selects unfinished tasks.
- **Task Tree**: Hierarchical task structure with status fields indicating completion.
- **Selected Tasks**: List of task IDs selected for further processing.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **TaskAssessor evaluates task tree**: Node correctly identifies unfinished tasks in the task tree.
- [ ] **TaskAssessor selects only unfinished tasks**: Completed tasks are never selected for processing.
- [ ] **TaskAssessor returns empty selection when appropriate**: No tasks are selected when all tasks are complete.
- [ ] **TaskAssessor integrates with AnalysisEffortNode**: Queue advances correctly based on selection results.
- [ ] **TaskAssessor handles malformed responses**: Graceful degradation with logging when LLM responses are invalid.
- [ ] **TaskAssessor supports effort-loop mode**: Full-tree assessment works as designed.
- [ ] **TaskAssessor propagates selection**: Selected task list is available for TaskAnalyzer consumption.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Test `TinyCUATaskAssessorNode` initialization with default and custom parameters.
- Test `__call__` method with various task tree states (mixed completion, all complete, all incomplete).
- Test `on_complete` method with selected tasks (advances to TaskAnalyzer).
- Test `on_complete` method with no selected tasks (skips TaskAnalyzer).
- Test LLM response parsing (valid JSON, malformed JSON, empty response).
- Test effort-loop mode behavior.
- Test reviewer-replan mode behavior (future milestone).

### Integration Tests

- Test TaskAssessor integration with AnalysisEffortNode queue prepending.
- Test TaskAssessor → TaskAnalyzer handoff with selected tasks.
- Test TaskAssessor → skip → AnalysisEffortNode flow when no tasks selected.

### Manual Tests _(if applicable)_

- Verify TaskAssessor behavior in a live TinyCUA session with complex task trees.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| TinyCUATaskAssessorNode class | TODO | Core node implementation |
| effort-loop mode | TODO | Full-tree assessment |
| reviewer-replan mode | TODO | Deferred to future milestone |
| LLM response parsing | TODO | JSON extraction and validation |
| Integration with AnalysisEffortNode | TODO | Queue mechanics |
| Unit tests | TODO | Comprehensive test coverage |

---

## Open Questions _(optional)_

1. **Assessment Schema**: Should `assessment_schema` be configurable via `NodeToolPolicy` or hardcoded?
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-15
   - **Status**: Proposed
   - **Proposed Answer**: Make it configurable via `TinyCUATaskAssessorNodeConfig.assessment_schema` with a sensible default.

2. **Reviewer-Replan Scope**: What exactly constitutes the "local region" for reviewer-replan mode?
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-20
   - **Status**: Discussion
   - **Proposed Answer**: Active task and its immediate children/parent context.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
