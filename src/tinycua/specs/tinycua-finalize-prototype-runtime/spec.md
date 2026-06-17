# Feature Specification: TinyCUA Final Prototype Runtime

**Status**: Draft  
**Created**: 2026-06-15  
**Last Updated**: 2026-06-15  
**Subproject(s) Affected**: `tinycua`

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a complete TinyCUA prototype runtime so notebook, CLI, SDK, and benchmark users can run a real task-oriented agent flow with correct routing, scoped tools, session-owned task state, dynamic worker decisions, final response streaming, and inspectable task artifacts.
- **Gaps**: The current prototype exposes node names and traces, but key runtime behavior remains shallow or stubbed: task nodes are mostly empty, worker routing is linear, tool results are not fed back to the model, task trees are not executed dynamically, streaming is noisy and can fall back to synthetic responses, notebook demos do not prove usable agent behavior, and tool scoping is not consistently tied to session/workspace safety.
- **Non-Goals**:
  - Do not rewrite the TinyCUA SDK public API unless required to preserve the documented TinyCUA contract.
  - Do not change source-of-truth design documents in `src/tinycua/docs/design/` as part of this planning work.
  - Do not accept mock-only proof as final runtime completion; mocks are allowed only as deterministic unit/integration coverage.
  - Do not implement placeholder/stub behavior and mark it complete.
- **Constraints**:
  - The implementation MUST honor `src/tinycua/docs/design/` semantics.
  - Python commands MUST run via `uv run` from `src/tinycua`.
  - Live LLM validation MUST use the local OpenAI-compatible test endpoint when `TINYCUA_LIVE_LLM=1`.
  - File/system tools MUST be workspace-bound and least-privilege scoped.
  - Streaming MUST remain SDK-compatible and usable for final response display.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A notebook user configures a workspace and artifact directory, creates a TinyCUA agent with native tools, asks it to build a small app, watches a final-response stream, and then inspects a non-empty task tree showing planning, execution, review, aggregation, artifacts, and final response evidence. The run must not rely on synthetic fallback output.

### Acceptance Scenarios

1. **Given** a fresh TinyCUA agent and a complex task prompt, **When** the user runs `agent.run(prompt, stream=True)`, **Then** QueryAnalyst routes through `select_query_route`, Worker routes through `select_worker_route`, a task tree is created, active tasks are executed/reviewed, aggregation occurs only after completion, and final response tokens stream from ResponseNode.
2. **Given** a simple conversational prompt, **When** the user runs the default agent, **Then** QueryAnalyst routes to passthrough through the route tool, worker/task nodes are not spawned, and ResponseNode streams a real final answer.
3. **Given** task tools produce results, **When** a node calls a tool, **Then** the tool output is fed back to the LLM as provider-compatible tool result/context before the node finalizes or continues.
4. **Given** a task is rejected by review, **When** ResultReviewer decides retry or replan, **Then** the queue follows retry/replan behavior instead of always moving linearly to aggregation.
5. **Given** the notebook demo, **When** it is run against the live local model, **Then** it displays final response text, task tree snapshots, route decisions, tool calls/results, artifact paths, and clear failure diagnostics if any contract is not met.

### Edge Cases

- Empty or whitespace node outputs MUST NOT be sent to the API as `{"role": "user", "content": "\n\n"}` or equivalent blank messages.
- Internal node outputs MUST NOT masquerade as external user prompts.
- A model that fails to call required route tools MUST trigger retry/validation failure and must not silently fall back to keyword inference.
- Tool-call failures MUST be visible to the model and to the trace.
- Two agents with different workspaces MUST not share file artifacts, todo state, or task state.
- Streaming consumers MUST be able to select final-response-only output without losing trace/debug observability.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: QueryAnalyst MUST perform lightweight analysis and route via `select_query_route` when the tool is available; no keyword inference or hardcoded prompt-pattern routing is allowed.
- **FR-002**: Worker MUST route via `select_worker_route` when the tool is available and MUST not execute or mutate tasks directly.
- **FR-003**: The worker runtime MUST be state-driven, not a forced linear chain. Queue transitions MUST depend on task state and reviewer decisions.
- **FR-004**: TaskCreate MUST create the root task tree through session-owned task state and validate that the root task exists before advancing.
- **FR-005**: TaskAnalyzer MUST implement mode-specific task analysis/decomposition/refinement and MUST mutate task structure only through scoped tools/helpers.
- **FR-006**: AnalysisEffort MUST implement documented effort-loop behavior and MUST not be a raw LLM text marker.
- **FR-007**: TaskAssessor MUST select work for additional analysis or execution using task state, not a string metadata flag.
- **FR-008**: TaskExecutor MUST execute the current active task, may use selected workspace-bound native tools, and MUST not mutate task tree structure.
- **FR-009**: ResultReviewer MUST produce structured decisions (`accept`, `retry`, `replan`, `open_question`) and drive queue mutation accordingly.
- **FR-010**: ResultAggregation MUST run only after the root task is done and MUST produce structured aggregated output with task summaries, results, artifacts, and final response continuation.
- **FR-011**: Task state MUST include a typed task tree, active task traversal, status transitions, reviewer decisions, artifact references, and serialization for traces/notebook display.
- **FR-012**: Tool calls MUST execute against session/workspace-scoped state and feed results back to the LLM in the same node lifecycle when continuation is required.
- **FR-013**: Todo state MUST be session-owned, not module-global.
- **FR-014**: File/native tools MUST resolve relative paths against `SessionConfig.workspace_dir` and MUST be denied outside the workspace unless explicitly configured.
- **FR-015**: Tool scoping MUST be least-privilege and test-verified for every node.
- **FR-016**: Message construction MUST remove blank messages, preserve correct roles, dedupe safely, and separate external user input from internal assistant/context output.
- **FR-017**: Streaming MUST support final response token streaming, internal debug streaming, route-decision events, tool-call/result events, and final-response-only mode.
- **FR-018**: The notebook MUST be an executable acceptance demo against the local live LLM endpoint, not a trace-only smoke demo.
- **FR-019**: All currently stubbed node classes MUST have concrete behavior or be removed/replaced by a concrete component. Empty semantic subclasses are not acceptable.
- **FR-020**: CI/test commands MUST include deterministic mock tests and opt-in live LLM integration tests.

### Key Entities _(include if feature involves data)_

- **TaskTree**: Session-owned root task graph with active task traversal and typed status transitions.
- **TaskNodeState**: Individual task with title, description, status, parent/children, execution result, reviewer decision, artifacts, and metadata.
- **WorkerDecision**: Structured route decision from Worker, including route label, source, reason, relevant task IDs, and trace metadata.
- **ReviewerDecision**: Structured result review decision controlling accept/retry/replan/open-question queue transitions.
- **AggregatedResult**: Structured final result containing task summaries, accepted results, artifact paths, final context, and response continuation.
- **ToolExecutionResult**: Provider-compatible tool result plus TinyCUA trace metadata.
- **StreamEvent**: SDK-compatible event with node metadata and explicit final/internal visibility.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **No stubs remain**: All worker/task node classes have concrete behavior, tests, and validation. Empty semantic subclasses fail review.
- [ ] **Worker runtime is dynamic**: Tests prove retry, replan, proceed-execution, passthrough, and aggregation paths are state-driven.
- [ ] **Task tree is real**: A complex prompt creates a task tree, executes active tasks, records results/reviewer decisions, and aggregates only when complete.
- [ ] **Tools are integrated**: Tool results are visible to the model and trace, and tool side effects are session/workspace scoped.
- [ ] **Streaming is usable**: Final response tokens stream cleanly; debug/internal events are available but not mixed into final response text.
- [ ] **Notebook is authoritative demo**: Live notebook run shows final answer, task tree, route/tool decisions, artifacts, and no synthetic fallback unless explicitly labeled as failure.
- [ ] **No blank API messages**: Captured API requests contain no blank/whitespace-only messages and preserve internal assistant roles.
- [ ] **Live LLM test passes**: `TINYCUA_LIVE_LLM=1 uv run pytest tests/integration/test_default_agent_flow_live.py tests/integration/test_notebook_contract_live.py -q` passes against the local endpoint.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Route tool validation for QueryAnalyst and Worker.
- Node-specific behavior for TaskCreate, TaskAnalyzer, AnalysisEffort, TaskAssessor, TaskExecutor, ResultReviewer, ResultAggregation.
- Task tree traversal/status transition helpers.
- Workspace path resolution and file tool containment.
- Message construction: no blanks, correct roles, correct dedupe, correct external/internal separation.
- Tool execution: allowlist enforcement, result formatting, error propagation, session-bound task/todo state.
- Stream event filtering and final-response-only behavior.

### Integration Tests

- End-to-end worker task creation with deterministic fake LLM/tool calls.
- End-to-end retry/replan/review loops.
- End-to-end native file artifact creation inside workspace.
- Two-agent workspace/session isolation.
- Live local LLM passthrough routing.
- Live local LLM worker routing and task lifecycle.
- Notebook execution contract using `nbclient` or equivalent with local LLM.

### Manual Tests _(if applicable)_

- Run `uv run jupyter notebook notebooks/tinycua_agent_trace_demo.ipynb` from `src/tinycua` against the local server and verify visible final response, task tree, artifact files, route/tool decisions, and clean streaming.
- Run CLI with workspace/output dirs and verify transcript, usage, artifacts, and task tree export.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Runtime architecture repair | TODO | Must replace linear scaffold with state-driven worker loop. |
| Stub node implementation | TODO | Zero tolerance for empty classes with semantic names. |
| Tool-result feedback | TODO | Required for usable ReAct behavior. |
| Streaming UX | TODO | Must distinguish final response from internal/debug events. |
| Live notebook contract | TODO | Must pass against local LLM server. |

---

## Open Questions _(optional)_

1. **Should shell/python execution tools be available by default in notebook demos?**
   - **Owner**: TinyCUA maintainers
   - **Target**: Before implementation begins
   - **Status**: Proposed
   - **Proposed Answer**: Enable only in explicit demo/test agents with workspace confinement and visible permission policy.
2. **Should final-response-only streaming be the notebook default?**
   - **Owner**: TinyCUA maintainers
   - **Target**: Before implementation begins
   - **Status**: Proposed
   - **Proposed Answer**: Yes; expose an optional debug stream panel for internal events.

---

## Review Checklist

- [x] No implementation details in requirements beyond contract-level behavior
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
