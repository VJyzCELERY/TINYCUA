# Feature Specification: WorkerNode Information-Digestion via QueryAnalyst

**Status**: Draft
**Created**: 2026-06-12
**Last Updated**: 2026-06-12
**Subproject(s) Affected**: tinycua (core)
**Milestone**: 3.7 — WorkerNode Information-Digestion via QueryAnalyst
**Design**: ./design.md

---

## Problem Statement _(mandatory)_

- **Goals**: Enable the WorkerNode — spawned by QueryAnalyst's `worker` route — to detect when task-planning context is insufficient and request context digestion via InformationDigesterNode before proceeding with task creation, analysis, or execution routing. This closes the gap between QueryAnalyst's worker classification and the WorkerNode's ability to make informed task-planning decisions.
- **Gaps**: Currently, when QueryAnalyst classifies user input as `worker`, it spawns a `TinyCUAWorkerNode` that immediately proceeds with deterministic task creation (`task_creation`) or LLM-assisted routing (`task_recreation`, `task_reanalysis`, `proceed_execution`). There is no mechanism for the WorkerNode to assess whether it has sufficient context to plan the task, nor any integration with InformationDigesterNode (Milestone 2.5) to request context digestion before making routing decisions. The WorkerNode's `_detect_task_exists()` precheck only checks whether a task object exists — it does not evaluate context sufficiency. For complex, multi-turn, or ambiguous worker inputs, the lack of context gathering before task planning leads to incomplete or poorly-informed task creation.
- **Non-Goals**:
  - Full context sufficiency analysis system (ResponseNode's three-phase sufficiency check is the pattern; WorkerNode uses a lighter mechanism)
  - InformationDigesterNode implementation (Milestone 2.5 — already implemented)
  - ResponseNode suspension path changes (Milestone 3.5 — already implemented)
  - QueryAnalyst classification changes (Milestone 2.1 — already implemented)
  - WorkerNode route label changes (existing five labels remain unchanged)
  - SDK API modifications
  - Streaming changes
- **Constraints**:
  - Must not modify QueryAnalyst's route dispatch or classification logic
  - Must not modify InformationDigesterNode's core contract or session model
  - Must not add new WorkerNode route labels (existing five: task_creation, task_recreation, task_reanalysis, passthrough, proceed_execution)
  - Must reuse existing InformationDigesterNode interface and `DigestedInformation` model
  - WorkerNode must remain a `DecisionNode` — the digestion request is a pre-processing step, not a new route
  - Must preserve deterministic precheck order: task existence check first, then context sufficiency check

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer creates a TinyCUA agent using `create_tinycua_agent(...)` and calls `.run("Help me debug this error: <stack trace>")`. QueryAnalyst classifies the input as `worker` and spawns a WorkerNode. WorkerNode's deterministic precheck detects no existing task and begins the task creation path. Before routing to `task_creation`, WorkerNode performs a context sufficiency check. It determines the stack trace alone lacks project context (language, framework, dependencies) and requests InformationDigesterNode to gather context from available session data. InformationDigesterNode produces `DigestedInformation` with key context. WorkerNode then proceeds with task creation using the enriched context, spawning TaskCreateNode with the digested information available in its session context.

### Acceptance Scenarios

1. **Given** a WorkerNode with no existing task and insufficient context for task planning, **When** it performs the context sufficiency check, **Then** it signals a digestion request through the node queue before proceeding to task creation.
2. **Given** WorkerNode signals a digestion request, **When** the queue processes the request, **Then** InformationDigesterNode is prepended to the queue before WorkerNode.
3. **Given** InformationDigesterNode produces `DigestedInformation`, **When** WorkerNode resumes after digestion completes, **Then** the digested information is available in WorkerNode's session context.
4. **Given** WorkerNode receives digested information in its session context, **When** it proceeds to task creation, **Then** TaskCreateNode receives the enriched session context including the digested information.
5. **Given** WorkerNode with sufficient context for task planning, **When** it performs the context sufficiency check, **Then** it skips digestion and proceeds directly to task creation.
6. **Given** WorkerNode with an existing task (deterministic task exists precheck passes), **When** WorkerNode does the context sufficiency check, **Then** it evaluates whether context is sufficient for the reanalysis/recreation decision and may still request digestion for the existing task context.
7. **Given** WorkerNode requests digestion but InformationDigesterNode returns no useful context (fallback continuation), **When** WorkerNode resumes, **Then** WorkerNode proceeds with task creation using the context it already has, treating the fallback as a no-op.
8. **Given** WorkerNode in `proceed_execution` route, **When** it has accumulated insufficient execution context, **Then** it may request digestion before spawning TaskExecutor.
9. **Given** WorkerNode requests digestion multiple times, **When** the digest attempt counter reaches a configurable maximum, **Then** WorkerNode falls through to its normal route without further digestion attempts (prevents infinite loops).

### Edge Cases

- What happens when InformationDigesterNode is not available (disabled in config)? → **Design**: WorkerNode proceeds with available context, logging a warning. [§Error Handling](./design.md#error-handling)
- What happens when the digestion request fails (node execution error)? → **Design**: WorkerNode retries per `NodeRetryPolicy`, then falls through to normal routing with available context. [§Error Handling](./design.md#error-handling)
- How does WorkerNode determine "sufficient context"? → **Design**: Via LLM-based sufficiency heuristics — a lightweight analysis prompt that evaluates available session context against the user's request. [§Architecture](./design.md#architecture)
- What is the behavior when digestion is requested for `task_recreation` or `task_reanalysis` routes? → **Design**: Same mechanism applies — digested information is prepended to WorkerNode's session context before the route completes. [§Implementation Phases](./design.md#implementation-phases)
- How does the system handle concurrent digestion requests? → **Design**: WorkerNode processes at most one digestion request per execution cycle. The digestion is synchronous from the queue perspective — InformationDigesterNode runs, then WorkerNode resumes. [§Error Handling](./design.md#error-handling)

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: WorkerNode MUST perform a context sufficiency check after the deterministic task-exists precheck and before LLM-based route decision.
- **FR-002**: WorkerNode MUST be able to request InformationDigesterNode for context gathering when it determines context is insufficient.
- **FR-003**: The context sufficiency check MUST use an LLM-based heuristic that evaluates available session context against the user's request.
- **FR-004**: When a digestion request is made, InformationDigesterNode MUST be prepended to the queue before WorkerNode so it executes first on the next iteration.
- **FR-005**: Digested information MUST be stored in WorkerNode's session context upon resumption, available for downstream nodes (TaskCreateNode, TaskAnalyzerNode, TaskExecutorNode, etc.).
- **FR-006**: WorkerNode MUST have a configurable maximum digestion attempt counter (default: 3) to prevent infinite digestion loops.
- **FR-007**: When InformationDigesterNode is disabled in configuration, WorkerNode MUST skip the context sufficiency check and proceed normally.
- **FR-008**: When InformationDigesterNode returns a no-useful-context fallback, WorkerNode MUST treat it as a no-op and proceed with available context.
- **FR-009**: WorkerNode MUST log all digestion requests, attempts, and outcomes for observability.
- **FR-010**: The digestion request MUST NOT modify existing WorkerNode route labels or route dispatch logic.
- **FR-011**: WorkerNode MUST support digestion for all routes: task_creation, task_recreation, task_reanalysis, and proceed_execution.
- **FR-012**: The digestion mechanism MUST NOT affect QueryAnalyst's routing or classification behavior.
- **FR-013**: WorkerNode MUST NOT request digestion when InformationDigesterNode is currently in the queue (prevents double-prepend).
- **FR-014**: WorkerNode MUST signal digestion requests through a mechanism compatible with the existing `NodeQueue` suspension/insertion API.
- **FR-015**: When request context is already sufficient, WorkerNode MUST skip the LLM sufficiency check to avoid unnecessary LLM calls (optimization for high-confidence cases).

### Key Entities _(include if feature involves data)_

- **TinyCUAWorkerNode (enhanced)**: WorkerNode with context sufficiency detection and digestion request capability. Integrates with InformationDigesterNode as a pre-processing step for task routing decisions. The node itself is not changed in routing behavior — only a new pre-processing step is added.
- **ContextSufficiency**: A lightweight evaluation result produced by the LLM sufficiency prompt. Contains a `sufficient: bool` flag and optional `reason: str`. Not stored as a persistent entity — only used transiently during worker execution.
- **InformationDigesterNode (existing)**: Unchanged from Milestone 2.5. Produces `DigestedInformation` from selected session context. WorkerNode's digestion request invokes this node through queue manipulation.
- **DigestedInformation (existing)**: Data model from Milestone 2.5 with fields: `context_summary`, `key_points`, `advisory_instructions`, `constraints`, `known_gaps`. WorkerNode makes these fields available in session context after digestion completes.
- **WorkerNodeConfig (extended)**: Configuration with new property `max_digest_attempts: int = 3` to limit digestion retries, and `digestion_enabled: bool = True` to allow disabling the feature.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **SC-001 — Acceptance Scenario 1** (Insufficient Context → Digestion): WorkerNode detects insufficient context and requests InformationDigesterNode before task creation.
- [ ] **SC-002 — Acceptance Scenario 2** (Digestion Queue Prepending): Queue correctly prepends InformationDigesterNode before WorkerNode.
- [ ] **SC-003 — Acceptance Scenario 3** (Digested Information in Context): Digested information is available in WorkerNode session context after digestion.
- [ ] **SC-004 — Acceptance Scenario 4** (TaskCreateNode Enriched Context): TaskCreateNode receives enriched session context including digested information.
- [ ] **SC-005 — Acceptance Scenario 5** (Sufficient Context Skip): WorkerNode skips digestion when context is already sufficient.
- [ ] **SC-006 — Acceptance Scenario 6** (Existing Task + Context Check): WorkerNode evaluates context sufficiency for routes other than task_creation.
- [ ] **SC-007 — Acceptance Scenario 7** (No-Useful-Context Fallback): WorkerNode proceeds with available context when InformationDigesterNode returns fallback.
- [ ] **SC-008 — Acceptance Scenario 8** (Proceed Execution Digestion): WorkerNode requests digestion for proceed_execution route when context is insufficient.
- [ ] **SC-009 — Acceptance Scenario 9** (Max Attempts Loop Prevention): WorkerNode stops requesting digestion after max_digest_attempts reached.
- [ ] **SC-010 — FR-001** (Context Sufficiency Check): WorkerNode performs context sufficiency check after task-exists precheck, before LLM decision.
- [ ] **SC-011 — FR-002** (Digestion Request): WorkerNode can request InformationDigesterNode for context gathering.
- [ ] **SC-012 — FR-003** (LLM-based Sufficiency Heuristic): Context sufficiency check uses LLM analysis of available context vs user request.
- [ ] **SC-013 — FR-007** (Disabled Digestion Behavior): WorkerNode skips context sufficiency check when digestion is disabled.
- [ ] **SC-014 — FR-010** (No Route Label Changes): Existing WorkerNode route labels are unchanged.
- [ ] **SC-015 — FR-013** (No Double Prepend): WorkerNode does not request digestion when InformationDigesterNode is already in the queue.
- [ ] **SC-016 — FR-015** (Skip LLM Check When Sufficient High-Confidence): WorkerNode skips LLM-based sufficiency check for high-confidence sufficient-context cases.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_worker_context_sufficiency_insufficient`: WorkerNode context sufficiency check detects insufficient context.
- `test_worker_context_sufficiency_sufficient`: WorkerNode context sufficiency check detects sufficient context (skips digestion).
- `test_worker_digestion_request_queue`: WorkerNode signals digestion request that prepends InformationDigesterNode to queue.
- `test_worker_digested_info_in_session_context`: Digested information is available in WorkerNode session context after digestion.
- `test_worker_max_digest_attempts`: WorkerNode stops requesting digestion after max_digest_attempts.
- `test_worker_digestion_disabled_skips_check`: WorkerNode skips context sufficiency check when digestion disabled.
- `test_worker_no_double_prepend`: WorkerNode does not request digestion when InformationDigesterNode already in queue.
- `test_worker_digestion_no_useful_context`: WorkerNode proceeds with available context on fallback.
- `test_worker_digestion_logging`: WorkerNode logs digestion requests, attempts, and outcomes.
- `test_worker_proceed_execution_digestion`: WorkerNode requests digestion for proceed_execution route.
- `test_worker_task_recreation_digestion`: WorkerNode requests digestion for task_recreation route.
- `test_worker_task_reanalysis_digestion`: WorkerNode requests digestion for task_reanalysis route.
- `test_worker_skip_llm_check_for_high_confidence`: WorkerNode skips LLM sufficiency check when context is trivially sufficient.
- `test_worker_digestion_retry_on_failure`: WorkerNode retries digestion per NodeRetryPolicy on failure.
- `test_worker_config_max_digest_attempts_default`: WorkerNodeConfig has correct default max_digest_attempts.

### Integration Tests

- `test_worker_digestion_full_flow`: End-to-end: QueryAnalyst → worker → WorkerNode (insufficient context) → InformationDigesterNode → WorkerNode (resumes with digest) → task_creation → TaskCreateNode (enriched context).
- `test_worker_digestion_then_proceed_execution`: End-to-end: worker route → task exists → context insufficient → InformationDigesterNode → WorkerNode resumes → proceed_execution → TaskExecutor with enriched context.
- `test_worker_digestion_max_attempts_integration`: Integration: WorkerNode max digests reached → falls through to normal routing.
- `test_worker_digestion_disabled_integration`: Integration: Digestion disabled → WorkerNode proceeds normally without context check.

### Manual Tests _(if applicable)_

- Verify queue state during WorkerNode digestion request/resume cycles via debug logging.
- Verify InformationDigesterNode prepend does not corrupt queue ordering for other nodes.
- Verify no regression in QueryAnalyst worker routing when digestion is enabled/disabled.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Context sufficiency check logic | TODO | WorkerNode enhancement |
| Digestion request mechanism | TODO | Queue integration |
| WorkerNodeConfig extension | TODO | max_digest_attempts, digestion_enabled |
| InformationDigesterNode integration | TODO | Queue prepend + session context injection |
| Unit tests | TODO | 15 tests |
| Integration tests | TODO | 4 tests |

---

## Open Questions _(optional)_

1. **Should the context sufficiency check be LLM-based or heuristic-based?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-14
   - **Status**: Proposed
   - **Proposed Answer**: LLM-based for accuracy; a lightweight analysis prompt that evaluates available context vs user request. Heuristic signals (e.g., message length thresholds) can be used as a pre-filter to skip unnecessary LLM calls when context is trivially sufficient.

2. **Should digestion be synchronous (queue-based) or asynchronous (event-driven)?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-14
   - **Status**: Proposed
   - **Proposed Answer**: Synchronous via queue manipulation, following the same pattern as ResponseNode's digestion suspension. InformationDigesterNode is prepended to the queue, executes on the next iteration, and WorkerNode resumes with the result.

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
