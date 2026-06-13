# Feature Specification: End-to-End TinyCUA Architecture Verification Gate

**Status**: Draft
**Created**: 2026-06-13
**Last Updated**: 2026-06-13
**Subproject(s) Affected**: tinycua (src/tinycua)
**Milestone**: 4.5 — End-to-End TinyCUA Architecture Verification Gate
**Tracking Issue**: https://github.com/VJyzCELERY/TINYCUA/issues/87

> **Path convention**: All paths in this document (e.g., `docs/design/`) are relative to the `tinycua` subproject root (`src/tinycua/`).

---

## Problem Statement _(mandatory)_

- **Goals**: Verify that the full TinyCUA target architecture flow works end-to-end across all documented paths before WildClawBench benchmark integration begins. This is a gate milestone — no benchmark work proceeds until all verification paths pass.
- **Gaps**: Prior milestones (1.1–4.4) implemented individual components (agent factory, loop, nodes, tools, propagation, retry, streaming), but no comprehensive verification has confirmed that these components compose correctly across the full architecture. There are no end-to-end tests exercising all documented paths with a local LLM.
- **Non-Goals**:
  - Implementing new architecture components or nodes (all are expected to exist from prior milestones).
  - WildClawBench integration, Docker images, or benchmark adapters (Milestone 5+).
  - Optimizing performance, latency, or token usage.
  - Production-quality error handling or UX.
  - Modifying `tinycua-sdk` public APIs.
- **Constraints**:
  - All verified paths MUST use local LLM configuration (no hosted model dependencies).
  - Verification MUST cover all paths documented in `docs/design/` without exception.
  - Gate failure blocks Milestone 5 — if any path fails, the PR does not merge.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer calls `create_tinycua_agent(...)` with local model configuration and runs the agent through a representative prompt. The agent exercises the full TinyCUA node flow — QueryAnalyst, Worker, TaskCreate, TaskAnalyzer, TaskAssessor, TaskExecutor, ResultReviewer, ResultAggregation, ResponseNode, and InformationDigester — completing successfully with correct task tree mutations, propagation, tool scoping, retry behavior, and streaming events.

### Acceptance Scenarios

1. **Given** a `create_tinycua_agent(...)` with local LLM config, **When** the agent receives a simple passthrough prompt, **Then** QueryAnalyst routes to passthrough and ResponseNode returns a result without entering the Worker path.

2. **Given** a `create_tinycua_agent(...)` with local LLM config, **When** the agent receives a task-creation prompt, **Then** QueryAnalyst routes to Worker, Worker creates a root task via TaskCreateNode, TaskAnalyzer performs initial analysis, TaskExecutor executes, ResultReviewer accepts, ResultAggregation consolidates, and ResponseNode returns the result.

3. **Given** an existing root task, **When** the agent receives a prompt that triggers task recreation, **Then** Worker routes to task_recreation, TaskAnalyzer receives TaskInit/TaskCreate tools, and the task tree is rebuilt.

4. **Given** an existing root task, **When** the agent receives a prompt that triggers task reanalysis, **Then** Worker routes to task_reanalysis, TaskAnalyzer refines the task without TaskInit/TaskCreate tools.

5. **Given** an existing root task with pending subtasks, **When** the agent receives a continuation prompt, **Then** Worker routes to proceed_execution and TaskExecutor resumes work on the active task.

6. **Given** a TaskAnalyzerNode with `analysis_effort=medium`, **When** the effort loop runs, **Then** TaskAssessor and TaskAnalyzer execute up to 2 passes before TaskExecutor is spawned.

7. **Given** a TaskExecutor that encounters a transient failure, **When** ResultReviewer assesses the result, **Then** ResultReviewer triggers a retry, TaskExecutor re-executes, and ResultReviewer eventually accepts.

8. **Given** a ResultReviewer that identifies a missing prerequisite, **When** it decides to replan, **Then** the queue routes back to TaskAnalyzer for local replanning.

9. **Given** a ResultReviewer that needs user input, **When** it decides `open_question`, **Then** the queue routes back to ResultReviewer deterministically.

10. **Given** a root task is accepted, **When** ResultAggregation runs, **Then** it traverses the task tree BFS right-to-left, consolidates results, and passes context to ResponseNode.

11. **Given** a ResponseNode that needs additional context, **When** it suspends to InformationDigester, **Then** InformationDigester gathers context, the digest propagates back, and ResponseNode resumes synthesis.

12. **Given** a QueryAnalyst that routes to Worker, **When** the Worker path includes an InformationDigester, **Then** the digest propagates to Worker's session_context before Worker enters.

13. **Given** any node execution, **When** context propagates between nodes, **Then** chat_history and session_context are separated correctly and duplicates are deduplicated.

14. **Given** any node execution, **When** tools are resolved, **Then** each node sees only its authorized tool scope (no cross-node tool leakage).

15. **Given** a node with `NodeRetryPolicy.max_attempts > 1`, **When** the node produces invalid output, **Then** it retries with assistant-role continuations until success or exhaustion.

16. **Given** a `stream=True` run, **When** the agent executes, **Then** lifecycle events are emitted and the final string is produced correctly.

### Edge Cases

- What happens when the local LLM endpoint is unreachable? (Verification should document the failure mode.)
- What happens when the task tree has deeply nested subtasks? (Aggregation should handle arbitrary depth.)
- What happens when propagation produces duplicate session context entries? (Dedupe must prevent redundancy.)
- What happens when a node exhausts its retry budget? (The loop should surface a clear error, not hang.)

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: `create_tinycua_agent(...).run(...)` MUST complete successfully across all 11 documented architecture paths using local LLM configuration.
- **FR-002**: The passthrough path MUST route through QueryAnalyst → ResponseNode without entering Worker or any downstream nodes.
- **FR-003**: The worker task creation path MUST route through QueryAnalyst → Worker → TaskCreateNode → TaskAnalyzer(initial_analysis) → TaskExecutor → ResultReviewer → ResultAggregation → ResponseNode.
- **FR-004**: The task recreation path MUST route through Worker → TaskAnalyzer(task_recreation) with TaskInit/TaskCreate tools available.
- **FR-005**: The task reanalysis path MUST route through Worker → TaskAnalyzer(task_reanalysis) without TaskInit/TaskCreate tools.
- **FR-006**: The proceed execution path MUST route through Worker → TaskExecutor for continuation prompts.
- **FR-007**: The effort loop path MUST run TaskAssessor and TaskAnalyzer up to the configured pass limit before spawning TaskExecutor.
- **FR-008**: The executor/reviewer accept path MUST complete with ResultReviewer accepting the task result.
- **FR-009**: The executor/reviewer retry path MUST trigger TaskExecutor re-execution after ResultReviewer rejection.
- **FR-010**: The executor/reviewer replan path MUST route back to TaskAnalyzer for local replanning.
- **FR-011**: The open_question path MUST route back to ResultReviewer deterministically.
- **FR-012**: The aggregation path MUST traverse the task tree and consolidate results into response-ready context.
- **FR-013**: The response path MUST synthesize a final string from aggregated context.
- **FR-014**: The response suspension/digestion path MUST suspend ResponseNode, run InformationDigester, and resume ResponseNode.
- **FR-015**: The worker suspension/digestion path MUST run InformationDigester before Worker and propagate digest to Worker's session_context.
- **FR-016**: Propagation MUST separate chat_history from session_context and deduplicate entries.
- **FR-017**: Tool scoping MUST enforce per-node tool visibility (verified through the full flow).
- **FR-018**: Retry MUST work with assistant-role continuations and respect `NodeRetryPolicy.max_attempts`.
- **FR-019**: Streaming MUST emit lifecycle events and produce correct final output.
- **FR-020**: All verification paths MUST use local LLM configuration (no hosted model dependencies).

### Key Entities

- **Verification Gate**: A pass/fail checkpoint that blocks Milestone 5 until all paths are confirmed working.
- **Architecture Path**: A documented end-to-end flow through the TinyCUA node graph (11 paths total).
- **Local LLM Configuration**: An OpenAI-compatible endpoint (vLLM, Ollama, LM Studio, etc.) used for all LLM calls during verification.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Passthrough path works**: Simple prompts route through QueryAnalyst → ResponseNode without Worker involvement.
- [ ] **Task creation path works**: Task-creating prompts produce a root task and complete through aggregation and response.
- [ ] **Task recreation path works**: Recreation triggers TaskAnalyzer with TaskInit/TaskCreate tools.
- [ ] **Task reanalysis path works**: Reanalysis triggers TaskAnalyzer without TaskInit/TaskCreate tools.
- [ ] **Proceed execution path works**: Continuation prompts resume work on the active task.
- [ ] **Effort loop path works**: Configured effort levels control assessment/analysis pass count.
- [ ] **Executor/reviewer accept path works**: Successful execution is accepted by ResultReviewer.
- [ ] **Executor/reviewer retry path works**: Transient failures trigger retry and eventual acceptance.
- [ ] **Executor/reviewer replan path works**: Missing prerequisites trigger local replanning.
- [ ] **Open question path works**: User input requests route back to ResultReviewer deterministically.
- [ ] **Aggregation path works**: Accepted root tasks enter aggregation and produce response-ready context.
- [ ] **Response path works**: Final response synthesis produces correct output.
- [ ] **Response suspension/digestion path works**: ResponseNode suspends, gathers context via InformationDigester, and resumes.
- [ ] **Worker suspension/digestion path works**: InformationDigester runs before Worker and digest propagates correctly.
- [ ] **Propagation/dedupe works**: Session context propagates without duplicates across all paths.
- [ ] **Tool scoping works**: Every node sees only its authorized tools throughout the full flow.
- [ ] **Retry/validation works**: Invalid output retries correctly and respects max_attempts.
- [ ] **Streaming works**: `stream=True` runs emit lifecycle events and produce correct final output.
- [ ] **Local LLM configuration works**: All paths execute against a local OpenAI-compatible endpoint.
- [ ] **Gate passes**: All above criteria are met — no failures in any architecture path.

---

## Testing Plan _(mandatory)_

### Unit Tests

- [ ] Test `create_tinycua_agent(...)` factory returns correct Agent with TinyCUALoop and local LLM config.
- [ ] Test each node can be instantiated and called with `NodeInputLike`.
- [ ] Test `NodeToolPolicy.resolve_tools()` returns correct tools for each node type.
- [ ] Test `NodeRetryPolicy` retry exhaustion behavior.
- [ ] Test `PropagationRule` dedupe logic.
- [ ] Test `CompactionStrategy.compact()` produces valid summary.

### Integration Tests

- [ ] **Passthrough path**: End-to-end test from agent.run() through QueryAnalyst → ResponseNode.
- [ ] **Task creation path**: End-to-end test producing a root task and completing through aggregation.
- [ ] **Task recreation path**: End-to-end test with existing task triggering TaskAnalyzer(task_recreation).
- [ ] **Task reanalysis path**: End-to-end test with existing task triggering TaskAnalyzer(task_reanalysis).
- [ ] **Proceed execution path**: End-to-end test resuming work on a pending task.
- [ ] **Effort loop path**: End-to-end test with `analysis_effort=medium` running multiple passes.
- [ ] **Retry path**: End-to-end test with intentional transient failure triggering retry.
- [ ] **Replan path**: End-to-end test with ResultReviewer triggering local replanning.
- [ ] **Open question path**: End-to-end test with open_question routing back to ResultReviewer.
- [ ] **Aggregation path**: End-to-end test with accepted root task entering aggregation.
- [ ] **Response suspension/digestion path**: End-to-end test with ResponseNode suspending to InformationDigester.
- [ ] **Worker suspension/digestion path**: End-to-end test with InformationDigester running before Worker.
- [ ] **Full propagation flow**: Test that chat_history and session_context are correctly separated and deduplicated across nodes.
- [ ] **Full tool scoping flow**: Test that each node receives only its authorized tools throughout the path.
- [ ] **Streaming lifecycle events**: Test that `stream=True` runs emit expected events.

### Manual Tests

- [ ] Run `create_tinycua_agent(...).run("What is 2 + 2?")` with local LLM and verify passthrough.
- [ ] Run `create_tinycua_agent(...).run("Create a plan to build a todo app")` with local LLM and verify task creation.
- [ ] Verify local LLM endpoint is reachable and responding before running automated tests.
- [ ] Inspect transcript/log output for correctness after each path verification.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Passthrough path | TODO | |
| Task creation path | TODO | |
| Task recreation path | TODO | |
| Task reanalysis path | TODO | |
| Proceed execution path | TODO | |
| Effort loop path | TODO | |
| Executor/reviewer accept path | TODO | |
| Executor/reviewer retry path | TODO | |
| Executor/reviewer replan path | TODO | |
| Open question path | TODO | |
| Aggregation path | TODO | |
| Response path | TODO | |
| Response suspension/digestion path | TODO | |
| Worker suspension/digestion path | TODO | |
| Propagation/dedupe | TODO | |
| Tool scoping | TODO | |
| Retry/validation | TODO | |
| Streaming | TODO | |
| Local LLM config | TODO | |
| Gate criteria document | TODO | |

---

## Open Questions _(optional)_

1. **Should verification tests use a mock LLM or real local LLM?**
   - **Owner**: @VJyzCELERY
   - **Status**: Discussion
   - **Proposed Answer**: Use real local LLM for primary verification (tests the full stack). Mock LLM as a fast-fallback unit test option.

2. **What is the minimum local LLM capability required for verification?**
   - **Owner**: @VJyzCELERY
   - **Status**: Discussion
   - **Proposed Answer**: A model capable of tool calling and structured output (e.g., Llama 3, Mistral, Qwen 2.5 via vLLM or Ollama).

3. **Should the gate include a minimum pass rate (e.g., 100% of paths) or a threshold (e.g., 90%)?**
   - **Owner**: @VJyzCELERY
   - **Status**: Discussion
   - **Proposed Answer**: 100% — this is a gate before benchmark integration. All paths must pass.

---

## Review Checklist

- [ ] No implementation details beyond what the design docs specify
- [ ] All mandatory sections completed
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
- [ ] Exit criteria match Milestone 4.5 from the roadmap issue
- [ ] All 11 architecture paths are covered in acceptance scenarios
- [ ] Gate criteria are explicitly defined (pass/fail for each path)
