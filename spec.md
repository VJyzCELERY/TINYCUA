# Feature Specification: TinyCUAResponseNode

**Status**: Implemented (Milestone 3.5)
**Created**: 2026-06-12
**Last Updated**: 2026-06-12 (review findings addressed)
**Subproject(s) Affected**: tinycua

---

## Problem Statement _(mandatory)_

- **Goals**: Provide the full `TinyCUAResponseNode` as a concrete `ProcessNode` that serves as the terminal node of the TinyCUALoop. It steers final response synthesis from aggregated results and accumulated context, producing a normalized user-facing answer. It must support context sufficiency checks, fallback to direct tool use or InformationDigester suspension, and consolidated continuation behavior.
- **Gaps**: The current `ResponseNode` is a minimal stub that only captures LLM output content. It lacks:
  - Context sufficiency analysis before synthesis
  - InformationDigesterNode suspension path for additional context gathering
  - Direct tool access for context-gathering
  - Consolidated continuation behavior (user continuation routing)
  - Terminal output normalization to string
- **Non-Goals**:
  - Task execution or result review (handled by TaskExecutor/ResultReviewer nodes)
  - Detailed task traversal or task-tree search (belongs to ResultAggregation and task helpers)
  - InformationDigesterNode implementation (handled in milestone 2.5)
  - AggregatedResult construction (handled in milestone 3.4)
  - SDK API modifications outside TinyCUA prototype
- **Constraints**:
  - Must extend `ProcessNode` base class
  - Must preserve `is_terminal=True` contract
  - Must work within existing `NodeQueue` bootstrap (terminal at end of queue)
  - Must integrate with TinyCUALoop's existing response handling
  - Must support both streamed and non-streamed output modes (streaming wiring deferred to a future milestone)
  - Must use `NodeRetryPolicy` for retry behavior

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

The TinyCUALoop completes its execution path (e.g., task executor → result reviewer → result aggregation) and reaches the terminal ResponseNode. ResponseNode receives aggregated context, analyzes sufficiency, and produces a final user-facing response.

### Acceptance Scenarios

1. **Given** a queue with only the terminal ResponseNode remaining, **When** ResponseNode executes with sufficient context, **Then** it produces a final string response without invoking tools or digester.
2. **Given** a ResponseNode with insufficient context and InformationDigester enabled, **When** executing, **Then** it suspends, prepends an InformationDigesterNode, and resumes after digest returns to produce the final response.
3. **Given** a ResponseNode with insufficient context and no digester configured, **When** executing, **Then** it uses allowed tools directly to gather context before producing the final response.
4. **Given** a user continuation directed at the ResponseNode session, **When** executing, **Then** consolidated continuation behavior delivers the continuation without LLM rerouting.

### Edge Cases

- What happens when aggregated context is empty?
- What happens when the digester returns no useful context?
- How does the system handle retry exhaustion during response synthesis? (Resolved: return a configurable fallback message rather than raising, to maintain graceful terminal behavior — see design.md OQ 2.)
- What is the behavior with null/empty NodeInput?
- How does terminal output normalization handle non-string LLM results?

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: `TinyCUAResponseNode` MUST extend `ProcessNode` and be marked as terminal (`is_terminal=True`).
- **FR-002**: ResponseNode MUST perform a context sufficiency check on every call before producing output.
- **FR-003**: When context is sufficient, ResponseNode MUST synthesize and return the final response string directly.
- **FR-004**: When context is insufficient and InformationDigester is enabled, ResponseNode MUST suspend execution, prepend an InformationDigesterNode to the queue, and resume after digestion completes.
- **FR-005**: When context is insufficient and the digester path is unavailable, ResponseNode MAY use allowed tools directly to gather additional context.
- **FR-006**: ResponseNode MUST normalize terminal output to a string.
- **FR-007**: ResponseNode MUST support consolidated continuation behavior — user continuation routing must reach the active ResponseNode session without LLM rerouting. "Consolidated" means the continuation is delivered via the existing `MandatoryPassthrough` mechanism (M3.3): a deterministic directive stored on the loop that routes the next user input directly to the target node (ResponseNode), bypassing QueryAnalyst classification. This avoids redundant LLM calls and ensures the continuation reaches the same session context.
- **FR-008**: ResponseNode MUST respect `NodeRetryPolicy` for retry behavior during synthesis.
- **FR-009**: ResponseNode MUST use the same base toolset as `TaskExecutor` (as specified by `NodeToolPolicy`).

### Key Entities

- **TinyCUAResponseNode**: Terminal ProcessNode that produces final user-facing responses from aggregated context. Supports sufficiency checking, digester suspension, and direct tool fallback.
- **AggregatedResult**: The structured output from `TinyCUAResultAggregationNode` that contains consolidated task context, results, artifacts, and reviewer decisions.
- **InformationDigesterNode**: Optional sub-node that gathers additional context when the ResponseNode determines available information is insufficient.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

Objective, measurable checks that prove the problem is solved.

- [x] **ResponseNode produces final string response**: `TinyCUAResponseNode` produces a normalized string output from sufficient aggregated context.
- [x] **Context sufficiency check works**: Sufficient context leads to direct synthesis; insufficient context triggers tool use or digester suspension.
- [x] **Digester suspension/resume works**: Suspension prepends InformationDigesterNode, digest propagates back, and ResponseNode resumes successfully.
- [x] **Direct tool fallback works**: When digester is unavailable, ResponseNode uses allowed tools to gather context before synthesis.
- [x] **Continuation routing works**: User continuation reaches ResponseNode session without LLM rerouting.
- [x] **Retry policy respected**: ResponseNode retries according to NodeRetryPolicy on failure.
- [x] **Same base toolset as TaskExecutor**: ResponseNode shares the same tool scope as TaskExecutor.
- [x] **No SDK API modifications**: All changes stay within the TinyCUA prototype boundary.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_response_node_initialization` — Verify node_id, config, is_terminal defaults
- `test_response_node_context_sufficiency_check` — Test sufficiency analysis logic
- `test_response_node_direct_synthesis` — Verify direct synthesis with sufficient context
- `test_response_node_digester_suspension` — Verify suspension and prepend behavior
- `test_response_node_tool_fallback` — Verify direct tool use when digester unavailable
- `test_response_node_continuation_routing` — Verify consolidated continuation delivery
- `test_response_node_retry_behavior` — Verify retry policy adherence
- `test_response_node_terminal_normalization` — Verify output normalized to string
- `test_response_node_base_toolset` — Verify same toolset as TaskExecutor

### Integration Tests

- `test_response_node_queue_integration` — End-to-end with NodeQueue and TinyCUALoop
- `test_response_node_digester_integration` — Full suspension/digestion/resume flow
- `test_response_node_with_aggregation` — Integration with ResultAggregationNode
- `test_response_node_continuation_integration` — Full continuation routing end-to-end

### Manual Tests _(if applicable)_

- Verify response output in both streamed and non-streamed modes

---

## Open Questions _(optional)_

1. **What constitutes "sufficient" context?**
   - **Owner**: @agent
   - **Target**: 2026-06-13
   - **Status**: Decided
   - **Answer**: Sufficiency is determined by checking if `aggregated_result` is not None and contains at least one of `task_summaries` or `final_context`. This provides a clear, testable criterion for implementation.

2. **Should the digester suspension be opt-in or default behavior?**
   - **Owner**: @agent
   - **Target**: 2026-06-13
   - **Status**: Decided
   - **Answer**: Default-enabled, configurable via NodeConfig. The digester provides valuable additional context gathering when needed, so it should be on by default but allow explicit opt-out.

---

## References

- **Roadmap Issue**: [#87 - Roadmap: TinyCUA Prototype for WildClawBench Harness Evaluation](https://github.com/VJyzCELERY/TINYCUA/issues/87) — Milestone 3.5: TinyCUAResponseNode

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
