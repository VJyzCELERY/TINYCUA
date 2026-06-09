# Feature Specification: TinyCUAAnalysisEffortNode

**Status**: Draft
**Created**: 2026-06-09
**Last Updated**: 2026-06-09
**Subproject(s) Affected**: tinycua (core)
**Milestone**: 2.4 — AnalysisEffortNode
**Design**: ./design.md

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a deterministic effort-control node that governs how many upfront task-assessment and task-analysis passes occur before advancing to execution, so that the Worker can tune planning thoroughness without LLM overhead.
- **Gaps**: Milestone 2.3 established WorkerNode optional LLM decision-making with task creation, recreation, reanalysis, passthrough, and proceed_execution routes. However, after the initial TaskCreate or TaskAnalyzer pass, there is no mechanism to control how many additional `[TaskAssessor, TaskAnalyzer]` rounds precede execution. The Worker currently advances directly to TaskExecutor (Milestone 3.2) without configurable planning depth.
- **Non-Goals**: TaskExecutor and ResultReviewer implementations (Milestone 3.2), full architecture verification (Milestone 4.5), ResponseNode behavior, and WildClawBench integration.
- **Constraints**: Must not modify tinycua-sdk public APIs. Must reuse existing ProcessNode infrastructure. Must maintain the queue invariant that QueryAnalyst is always the first node. AnalysisEffortNode is a deterministic ProcessNode — no LLM call is required.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer creates a TinyCUA agent using `create_tinycua_agent(...)` and calls `.run("Help me write a script")`. QueryAnalyst classifies the input as `worker` and spawns a WorkerNode. WorkerNode detects no task exists and routes to task_creation, spawning TaskCreateNode followed by TaskAnalyzerNode (mode=initial_analysis). After TaskAnalyzerNode completes, AnalysisEffortNode enters. Based on the configured `WorkerEffort` level, AnalysisEffortNode prepends `[TaskAssessor, TaskAnalyzer]` pairs until the pass limit is reached, then spawns TaskExecutor before advancing.

### Acceptance Scenarios

1. **Given** a TinyCUA agent with WorkerNode active and `WorkerEffort="none"`, **When** the worker task_creation route executes, **Then** AnalysisEffortNode enters, detects pass_limit=0, and spawns TaskExecutor immediately without prepending any `[TaskAssessor, TaskAnalyzer]` passes.
2. **Given** a TinyCUA agent with WorkerNode active and `WorkerEffort="low"`, **When** the worker task_creation route executes, **Then** AnalysisEffortNode enters, prepends one `[TaskAssessor, TaskAnalyzer]` pair, and after that pass completes, spawns TaskExecutor.
3. **Given** a TinyCUA agent with WorkerNode active and `WorkerEffort="medium"`, **When** the worker task_creation route executes, **Then** AnalysisEffortNode enters, prepends two `[TaskAssessor, TaskAnalyzer]` pairs sequentially, and after the second pass completes, spawns TaskExecutor.
4. **Given** a TinyCUA agent with WorkerNode active and `WorkerEffort="high"`, **When** the worker task_creation route executes, **Then** AnalysisEffortNode enters, prepends three `[TaskAssessor, TaskAnalyzer]` pairs sequentially, and after the third pass completes, spawns TaskExecutor.
5. **Given** AnalysisEffortNode with pass_count=0 and pass_limit=2, **When** AnalysisEffortNode enters, **Then** it prepends `[TaskAssessor, TaskAnalyzer]` to the queue and increments pass_count to 1.
6. **Given** AnalysisEffortNode with pass_count=1 and pass_limit=2, **When** AnalysisEffortNode re-enters after the first pass completes, **Then** it prepends another `[TaskAssessor, TaskAnalyzer]` and increments pass_count to 2.
7. **Given** AnalysisEffortNode with pass_count=2 and pass_limit=2, **When** AnalysisEffortNode re-enters after the second pass completes, **Then** it spawns TaskExecutor before advancing (pass_count >= pass_limit).
8. **Given** AnalysisEffortNode prepends `[TaskAssessor, TaskAnalyzer]`, **When** TaskAssessor completes with tasks selected, **Then** TaskAnalyzer processes the selected tasks.
9. **Given** AnalysisEffortNode prepends `[TaskAssessor, TaskAnalyzer]`, **When** TaskAssessor completes with no tasks selected (effort loop), **Then** no TaskAnalyzer is spawned and the queue advances back to AnalysisEffortNode.
10. **Given** AnalysisEffortNode is in the queue, **When** any route completes (task_creation, task_recreation, task_reanalysis), **Then** AnalysisEffortNode is placed after the initial TaskCreate/TaskAnalyzer and before TaskExecutor in the queue.
11. **Given** AnalysisEffortNode spawns TaskExecutor, **When** TaskExecutor is spawned, **Then** the terminal response path (ResultReviewer, ResponseNode) is maintained.
12. **Given** AnalysisEffortNode with any effort level, **When** AnalysisEffortNode completes its work, **Then** it is the deterministic ProcessNode — no LLM call is made.
13. **Given** AnalysisEffortNode prepends [TaskAssessor, TaskAnalyzer], **When** TaskAnalyzer completes, **Then** task tree state changes are visible to the next node in the queue.
14. **Given** a TinyCUA agent with WorkerNode active and WorkerEffort not configured, **When** the worker task_creation route executes, **Then** AnalysisEffortNode defaults to WorkerEffort="none" and spawns TaskExecutor immediately.

### Edge Cases

- What happens when WorkerEffort is not configured? → **Design**: Default to `"none"` (pass_limit=0), advancing directly to TaskExecutor. [§Data Model](./design.md#data-model)
- How does the system handle pass_limit=0 (effort=none)? → **Design**: AnalysisEffortNode spawns TaskExecutor immediately without prepending any passes. [§Error Handling](./design.md#error-handling)
- What is the behavior when TaskAssessor selects no tasks during an effort pass? → **Design**: TaskAnalyzer is not spawned; queue advances back to AnalysisEffortNode which increments pass_count and continues. [§Error Handling](./design.md#error-handling)
- What happens when AnalysisEffortNode's pass_count reaches pass_limit? → **Design**: AnalysisEffortNode spawns TaskExecutor before advancing, preventing queue drain. [§Error Handling](./design.md#error-handling)
- What happens when the queue is modified by a route handler after AnalysisEffortNode has prepended passes? → **Design**: Route handlers that call `clear_after_current()` clear stale passes; AnalysisEffortNode re-evaluates on re-entry. [§Error Handling](./design.md#error-handling)

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide `TinyCUAAnalysisEffortNode` as a concrete `ProcessNode`.
- **FR-002**: AnalysisEffortNode MUST be a deterministic node — no LLM call is required.
- **FR-003**: AnalysisEffortNode MUST accept a `WorkerEffort` configuration: `none`, `low`, `medium`, or `high`.
- **FR-004**: AnalysisEffortNode MUST map `WorkerEffort` to pass limits: `none=0`, `low=1`, `medium=2`, `high=3`.
- **FR-005**: AnalysisEffortNode MUST track `pass_count` and prepend `[TinyCUATaskAssessorNode, TinyCUATaskAnalyzerNode]` until `pass_count >= pass_limit`.
- **FR-006**: When `pass_count < pass_limit`, AnalysisEffortNode MUST prepend a `[TaskAssessor, TaskAnalyzer]` pair and increment `pass_count`.
- **FR-007**: When `pass_count >= pass_limit`, AnalysisEffortNode MUST spawn `TaskExecutor` before advancing.
- **FR-008**: AnalysisEffortNode MUST maintain the terminal response path (ResultReviewer, ResponseNode) after spawning TaskExecutor.
- **FR-009**: WorkerNode route handlers (task_creation, task_recreation, task_reanalysis) MUST insert AnalysisEffortNode after the initial TaskCreate/TaskAnalyzer in the queue.
- **FR-010**: AnalysisEffortNode MUST default to `WorkerEffort="none"` (pass_limit=0) when not configured.
- **FR-011**: AnalysisEffortNode MUST NOT modify tinycua-sdk public APIs.
- **FR-012**: AnalysisEffortNode MUST preserve the queue invariant that QueryAnalyst is always the first node.
- **FR-013**: AnalysisEffortNode MUST handle the case where TaskAssessor selects no tasks (no analyzer spawned, queue advances back to AnalysisEffortNode).
- **FR-014**: AnalysisEffortNode MUST propagate task tree state changes from TaskAssessor and TaskAnalyzer passes.

### Key Entities _(include if feature involves data)_

- **TinyCUAAnalysisEffortNode**: Concrete ProcessNode that controls planning depth via configurable pass limits. Deterministic (no LLM call). Tracks pass_count and prepends [TaskAssessor, TaskAnalyzer] pairs.
- **WorkerEffort**: Enum/string with values `none`, `low`, `medium`, `high`. Maps to pass limits 0, 1, 2, 3 respectively.
- **TinyCUATaskAssessorNode**: Concrete ProcessNode that evaluates the task tree and selects unfinished tasks. Operates in effort-loop mode when called from AnalysisEffortNode — see design.md for LLM instruction, output format, and tool scope.
- **TinyCUATaskAnalyzerNode**: Concrete ProcessNode that performs task analysis with mode-based tool filtering. Operates in `effort_loop_decomposition` mode when called from AnalysisEffortNode.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **SC-001** — **Acceptance Scenario 1**: Given WorkerEffort="none", when worker task_creation route executes, then AnalysisEffortNode spawns TaskExecutor immediately (pass_limit=0).
- [ ] **SC-002** — **Acceptance Scenario 2**: Given WorkerEffort="low", when worker task_creation route executes, then one [TaskAssessor, TaskAnalyzer] pass occurs before TaskExecutor.
- [ ] **SC-003** — **Acceptance Scenario 3**: Given WorkerEffort="medium", when worker task_creation route executes, then two [TaskAssessor, TaskAnalyzer] passes occur before TaskExecutor.
- [ ] **SC-004** — **Acceptance Scenario 4**: Given WorkerEffort="high", when worker task_creation route executes, then three [TaskAssessor, TaskAnalyzer] passes occur before TaskExecutor.
- [ ] **SC-005** — **Acceptance Scenarios 5–7** (Pass Counting): pass_count increments correctly and TaskExecutor spawns when threshold reached.
- [ ] **SC-006** — **Acceptance Scenario 9** (No Tasks Selected): When TaskAssessor selects no tasks, TaskAnalyzer is not spawned and queue advances back to AnalysisEffortNode.
- [ ] **SC-007** — **Acceptance Scenario 10** (Queue Shape): AnalysisEffortNode is placed after initial TaskCreate/TaskAnalyzer and before TaskExecutor in all worker routes.
- [ ] **SC-008** — **Acceptance Scenario 11** (Terminal Path): Terminal response path is maintained after TaskExecutor spawning.
- [ ] **SC-009** — **Acceptance Scenario 12** (Deterministic): AnalysisEffortNode makes no LLM calls.
- [ ] **SC-010** — **FR-010** (Default Effort): AnalysisEffortNode defaults to WorkerEffort="none" when not configured.
- [ ] **SC-011** — **FR-011** (SDK API Stability): AnalysisEffortNode does not modify tinycua-sdk public API surface.
- [ ] **SC-012** — **FR-012** (Queue Invariant): QueryAnalyst remains first node in queue after AnalysisEffortNode insertion.
- [ ] **SC-013** — **FR-014** (Task Tree State): Task tree state changes from TaskAssessor/TaskAnalyzer are visible to next node.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_none_effort_spawns_executor_immediately`: WorkerEffort="none" spawns TaskExecutor immediately (pass_limit=0).
- `test_low_effort_does_not_spawn_immediately`: WorkerEffort="low" prepends one [TaskAssessor, TaskAnalyzer] pass.
- `test_medium_effort_does_not_spawn_immediately`: WorkerEffort="medium" prepends two [TaskAssessor, TaskAnalyzer] passes.
- `test_high_effort_does_not_spawn_immediately`: WorkerEffort="high" prepends three [TaskAssessor, TaskAnalyzer] passes.
- `test_pass_count_increment`: pass_count increments correctly on each pass.
- `test_threshold_reached_spawns_executor`: TaskExecutor spawns when pass_count >= pass_limit.
- `test_no_llm_call`: AnalysisEffortNode does not invoke LLM client.
- `test_default_effort_when_not_configured`: Defaults to WorkerEffort="none" when not configured.
- `test_preserves_terminal_path`: Terminal response path maintained after TaskExecutor spawning.
- `test_effort_to_pass_limit_mapping_all_levels`: All four effort levels map to correct pass limits.
- `test_task_tree_propagation`: Task tree state changes from TaskAssessor and TaskAnalyzer passes are propagated to the next node in the queue.
- `test_effort_loop_mode_evaluates_task_tree`: TinyCUATaskAssessorNode operates in effort-loop mode when called from AnalysisEffortNode, selecting only unfinished tasks.
- `test_effort_loop_mode_no_tasks_selected`: TinyCUATaskAssessorNode returns no tasks when all tasks are complete, allowing queue to advance back to AnalysisEffortNode.
- `test_effort_loop_mode_selects_unfinished_tasks`: TinyCUATaskAssessorNode selects unfinished tasks for processing by TaskAnalyzer.

### Integration Tests

- `test_analysis_effort_node_with_worker_task_creation`: End-to-end: WorkerNode → task_creation → TaskCreate → TaskAnalyzer → AnalysisEffortNode → TaskExecutor.
- `test_analysis_effort_node_with_worker_task_recreation`: End-to-end: WorkerNode → task_recreation → TaskAnalyzer → AnalysisEffortNode → TaskExecutor.
- `test_analysis_effort_node_with_worker_task_reanalysis`: End-to-end: WorkerNode → task_reanalysis → TaskAnalyzer → AnalysisEffortNode → TaskExecutor.
- `test_analysis_effort_node_passes_complete`: End-to-end: AnalysisEffortNode → [TaskAssessor, TaskAnalyzer] × N → TaskExecutor.
- `test_analysis_effort_node_assessor_no_tasks`: End-to-end: TaskAssessor selects no tasks → no TaskAnalyzer → back to AnalysisEffortNode.

### Manual Tests _(if applicable)_

- Verify AnalysisEffortNode queue shape visually with each effort level.
- Verify pass counting with debug logging enabled.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Planning documents | DONE | spec.md, design.md |
| TinyCUAAnalysisEffortNode class | DONE | analysis_effort.py |
| WorkerEffort enum | DONE | effort model |
| effort_to_pass_limit mapping | DONE | mapping function |
| TinyCUATaskAssessorNode class | DONE | task_assessor.py — effort-loop mode |
| WorkerNode route handler integration | DONE | Insert AnalysisEffortNode after TaskCreate/TaskAnalyzer |
| Unit tests | DONE | All acceptance scenarios |
| Integration tests | DONE | End-to-end worker → effort → executor flow |

---

## Open Questions _(optional)_

1. **Should WorkerEffort be a string enum or a plain string type?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-10
   - **Status**: Decided
   - **Decision**: Use a string enum (`WorkerEffort`) for type safety and IDE support, consistent with `WorkerRouteLabel` pattern
   - **Resolved**: 2026-06-09

2. **Should AnalysisEffortNode be owned by WorkerNode or standalone in the queue?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-10
   - **Status**: Decided
   - **Decision**: AnalysisEffortNode is standalone in the queue but inserted by WorkerNode route handlers. It is not "owned" in the sense of parent-child, but it is part of the WorkerNode's queue segment.
   - **Resolved**: 2026-06-09

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices) — domain entity names (e.g., WorkerEffort, TaskAssessor) are allowed
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
