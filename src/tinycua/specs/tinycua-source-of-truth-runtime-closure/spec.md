# Feature Specification: TinyCUA Source-of-Truth Runtime Closure

**Status**: In Progress
**Created**: 2026-06-16
**Last Updated**: 2026-06-16
**Subproject(s) Affected**: tinycua

---

## Problem Statement _(mandatory)_

- **Goals**: Provide an end-to-end TinyCUA prototype runtime that follows the documented context-decomposition architecture with real LLM decisions, real tool use, isolated node context, explicit task state, and visible failure when the model cannot satisfy a contract.
- **Gaps**: Previous runtime paths contained or permitted hardcoded outcome shortcuts, synthetic success, implicit task-state mutation from prose, insufficient live-LLM guidance for task tools, and incomplete alignment with source-of-truth docs in `docs/design/` and `docs/architecture/`.
- **Non-Goals**:
  - Do not guarantee that the LLM-created application/research answer is semantically perfect.
  - Do not modify `src/tinycua-sdk/`.
  - Do not hardcode routing, task decomposition shape, app files, research conclusions, or success outcomes.
  - Do not make display sanitization responsible for hiding broken runtime state.
- **Constraints**:
  - LLM must choose routes via route tools and fail/retry visibly if it does not.
  - LLM must create/mutate task state through task tools, not prose parsing.
  - Runtime may enforce contracts and deterministic control flow, but must not fabricate work.
  - Native tools must remain workspace-confined and available to allowed nodes by policy.
  - Worker effort defaults to `medium`, meaning two upfront assessment/decomposition passes before execution unless configured otherwise.
  - The notebook prompt must stay natural; it must not instruct the user/model to “use worker mode” or call route tools.
  - The prototype must work with the provided real local LLM and its 262144-token context window without hardcoded behavioral shortcuts.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A user prompts TinyCUA once with a complex task such as creating a small app or doing research. QueryAnalyst routes to Worker via `select_query_route`, InformationDigester produces focused context, Worker chooses a task route via `select_worker_route`, TaskCreate initializes a root task via `task_init`, TaskAnalyzer/TaskAssessor refine the task tree according to `worker_effort`, TaskExecutor uses workspace/research tools and records a result via `task_result_update`, ResultReviewer records a review decision via `task_review_decision`, ResultAggregation produces response-ready context, and ResponseNode synthesizes the final answer.

### Acceptance Scenarios

1. **Given** a direct conversational prompt, **When** the agent runs, **Then** QueryAnalyst may route passthrough and ResponseNode answers without creating a fake task tree.
2. **Given** a complex actionable prompt, **When** the agent runs with the real local LLM, **Then** Worker path reaches task creation, analysis, execution, review, aggregation, and response using tools rather than hardcoded files/outcomes.
3. **Given** a model returns planner/refusal prose instead of required tools, **When** a contract-required node validates, **Then** the runtime retries and records a visible failure instead of synthesizing artifacts or success.
4. **Given** streaming mode, **When** worker execution runs, **Then** streaming path enforces the same validation and tool-owned state contracts as non-streaming.

### Edge Cases

- Missing route tool call: retry according to `NodeRetryPolicy`; fail closed without keyword fallback.
- Missing `task_init`, `task_result_update`, or `task_review_decision`: retry and record failure; do not infer state from prose.
- Empty terminal response: remain empty/visible; do not fill synthetic content.
- Prompt echo or planner prose: do not store bad context as task state or artifacts.
- Existing task follow-up: Worker may choose reanalysis, recreation, passthrough, or proceed execution based on task state and tool-selected route.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: QueryAnalyst MUST use route-selection tools for `worker`, `uncertain`, or `passthrough`; no content/keyword fallback may select a route.
- **FR-002**: Worker MUST use route-selection tools for Worker routes; no hardcoded route selection may replace the LLM route decision.
- **FR-003**: TaskCreate MUST create the root task through `task_init`; runtime may require this tool but MUST NOT hardcode a title/tree shape.
- **FR-004**: TaskAnalyzer and TaskAssessor MUST mutate task structure/metadata only through task tools; runtime MUST NOT parse arbitrary LLM lines into tasks.
- **FR-005**: AnalysisEffort MUST implement documented effort pass limits (`none=0`, `low=1`, `medium=2`, `high=3`) as deterministic orchestration, not as outcome fabrication.
- **FR-006**: TaskExecutor MUST use tools for actionable work and MUST record task results through `task_result_update`; it MUST NOT create scaffold files or substitute a hardcoded app.
- **FR-007**: ResultReviewer MUST record decisions through `task_review_decision`; it MUST NOT infer accept/retry/replan/open-question from raw prose.
- **FR-008**: ResultAggregation MUST use task inspection and actual task state/results/artifacts to produce `AggregatedResult`; it MUST NOT claim missing work succeeded.
- **FR-009**: ResponseNode MUST synthesize from actual direct-response context, digested context, or aggregated worker context; it MUST NOT fabricate execution evidence.
- **FR-010**: Streaming and non-streaming loop paths MUST enforce equivalent validation, task-state, tool-use, and trace contracts.
- **FR-011**: Runtime trace/state snapshots MUST expose validation failures, retry exhaustion, tool calls/results, and task state sufficient for debugging.
- **FR-012**: Guardrail tests MUST reject hardcoded scaffold strings, synthetic terminal fallback, route fallback labels, keyword action heuristics, and implicit fallback tasks.

### Key Entities

- **NodeInput**: Compact handoff payload passed between isolated nodes.
- **DecisionResult**: Validated route decision from route tool calls.
- **TaskStateStore**: Session-local task tree and lifecycle state mutated only through task tools or deterministic lifecycle helpers explicitly documented as state ownership.
- **TaskResult**: Execution result recorded by TaskExecutor through task tools.
- **ReviewerDecision**: Review gate decision recorded by ResultReviewer through task tools.
- **AggregatedResult**: Response-ready summary of actual accepted task results and artifacts.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **No hardcoded runtime outcomes**: grep/guardrail tests find no scaffold, synthetic success, fallback route, keyword-action, or fallback-task implementation markers in runtime modules.
- [ ] **Direct response works**: a simple prompt can complete without Worker and without fake task state.
- [ ] **Worker app prompt exercises full architecture**: live LLM run reaches Worker, task creation, analysis effort, execution, review, aggregation, and response with visible tool/state evidence.
- [ ] **Planner-only failure is visible**: deterministic tests prove planner prose cannot create files or task success.
- [ ] **Streaming parity**: streaming contract produces the same validation/state behavior as non-streaming.
- [ ] **Docs/design parity**: implementation aligns with `docs/design/loops/*.md`, `docs/design/constants/tools.md`, and `docs/architecture/overview.md`.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Route tools fail closed and retry without content fallback.
- Task tools own creation/result/review state mutation.
- No runtime stubs/shortcuts/forbidden markers.
- Worker effort maps to documented pass counts.
- Message contract preserves context isolation and assistant-role handoff.

### Integration Tests

- Deterministic app-creation script uses `task_init`, workspace tools, `task_result_update`, `task_review_decision`, aggregation, and response.
- Planner-only/prompt-echo scripts fail visibly without hardcoded artifacts.
- Notebook deterministic contract remains natural and exposes trace/state/workspace outputs.
- Streaming worker path enforces the same contracts.

### Manual / Live Tests

- Live notebook contract against local OpenAI-compatible LLM.
- Live direct-response prompt.
- Live complex app-creation prompt.
- Live deep-research prompt using web/retrieval tools where available.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Source-of-truth re-read | In Progress | Architecture and loop docs re-read; implementation audit continues. |
| Documentation | In Progress | This spec/design/task set records closure requirements. |
| Runtime closure implementation | TODO | Next step after docs. |
| Deterministic validation | TODO | Must pass before live validation. |
| Live validation | TODO | Must prove real LLM path. |

---

## Open Questions _(optional)_

None currently. User has explicitly authorized continuing implementation and iterative self-review without additional clarification.

---

## Review Checklist

- [x] No implementation details that prescribe hardcoded outputs
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
