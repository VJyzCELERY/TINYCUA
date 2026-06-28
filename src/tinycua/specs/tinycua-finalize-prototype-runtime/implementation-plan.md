# Implementation: TinyCUA Final Prototype Runtime

Implement the full TinyCUA prototype runtime described by `src/tinycua/docs/design/` with zero tolerance for stubs, shortcuts, synthetic success, or trace-only validation. Every implementation unit below includes its own testing and validation gate; a task is not complete until those gates pass.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P0
- **Estimated Effort**: XL

## Environment Pre-requisites

### Configuration

- [ ] **Local LLM env file** — `src/tinycua/.env.test` or equivalent must provide:
  ```bash
  TINYCUA_LIVE_LLM=1
  OPENAI_CHAT_COMPLETIONS_BASE_URL=http://localhost:1234/v1
  OPENAI_CHAT_COMPLETIONS_MODEL=qwen/qwen3.5-4b
  OPENAI_CHAT_COMPLETIONS_API_KEY=tinycua-local-test
  TINYCUA_BASE_URL=http://localhost:1234/v1
  TINYCUA_MODEL=qwen/qwen3.5-4b
  TINYCUA_API_KEY=tinycua-local-test
  ```

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| Local OpenAI-compatible LLM | Yes for live acceptance | Start local server outside tests | `curl http://localhost:1234/v1/models` |

### Data / Fixtures

- [ ] Deterministic fake LLM fixtures for route/tool/task/reviewer paths.
- [ ] Temporary workspace fixtures under `src/tinycua/tmp/`.

### Access / Permissions

- [ ] Local filesystem workspace access under configured `workspace_dir`.
- [ ] No network access required except local LLM and optional `fetch_url` tests with mocked/local URL.

### Developer Tooling

- [ ] **Runtime**: Python 3.11+ / 3.12 supported by project.
- [ ] **Package manager**: `uv`.
- [ ] **Notebook validation**: `nbclient` or existing project-supported notebook execution tooling.

---

## Success Criteria — Integration Tests (TDD First)

```python
# Test file: tests/integration/test_final_prototype_runtime.py
"""End-to-end tests for the finalized TinyCUA prototype runtime."""


async def test_worker_prompt_creates_executes_reviews_and_aggregates_task_tree():
    """Complex prompts produce a real task tree and final response, not a linear trace shell."""


async def test_reviewer_retry_reexecutes_same_active_task():
    """Reviewer retry keeps active task and routes back to TaskExecutor."""


async def test_reviewer_replan_runs_local_assessor_analyzer_before_execution():
    """Reviewer replan follows local replan path, not full upfront pipeline."""


async def test_tool_results_are_visible_to_followup_llm_call():
    """Tool output is fed back to the model before the node finalizes or continues."""


async def test_final_response_stream_contains_only_response_node_tokens_by_default():
    """User-facing streaming is readable and excludes internal routing noise."""
```

### Key Test Scenarios

- [ ] **Dynamic worker lifecycle**: Complex prompt creates, decomposes, executes, reviews, and aggregates real task state.
- [ ] **Retry path**: ResultReviewer rejects output and retries same active task.
- [ ] **Replan path**: ResultReviewer triggers local TaskAssessor/TaskAnalyzer path.
- [ ] **Multi-task traversal**: Accepted active task advances to next unfinished task until root completion.
- [ ] **Tool feedback**: LLM can observe `task_init`, `task_decompose`, file write/read, and error results.
- [ ] **Streaming UX**: Final stream is readable; debug stream remains available.
- [ ] **Notebook live contract**: Notebook passes against local LLM and displays task tree/artifacts/final answer.

## Verification Plan

### Automated Tests

- [ ] Unit tests per phase listed below.
- [ ] Integration tests per feature listed below.
- [ ] Live LLM tests:
  ```bash
  cd src/tinycua && TINYCUA_LIVE_LLM=1 uv run pytest tests/integration/test_default_agent_flow_live.py tests/integration/test_final_prototype_live.py -q
  ```
- [ ] Notebook contract:
  ```bash
  cd src/tinycua && TINYCUA_LIVE_LLM=1 uv run pytest tests/integration/test_notebook_contract_live.py -q
  ```
- [ ] Existing suite:
  ```bash
  cd src/tinycua && uv run pytest -q
  ```

### Manual Verification

- [ ] Run notebook and verify final answer, task tree, artifacts, route/tool decisions, and no fallback-as-success.
- [ ] Run CLI with workspace/output dirs and verify transcript, task tree export, artifacts, and final stream.

### Performance Considerations

- [ ] Worker prompt emits bounded event volume with final-response-only mode.
- [ ] Task tree snapshots are summarized/paginated for large trees.
- [ ] Tool-result feedback does not duplicate unbounded context.

## Proposed Changes

### Phase 0 — Contract Guardrails

#### [NEW] `tests/unit/test_no_runtime_stubs.py`

- **Description**: Static/behavioral tests that fail if semantic runtime node classes are empty subclasses without concrete behavior or tests.
- **Rationale**: Prevent repeating the scaffold-without-runtime failure.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest tests/unit/test_no_runtime_stubs.py -q
  ```

#### [NEW] `tests/unit/test_message_contract.py`

- **Description**: Capture LLM request messages and assert no blank content, correct roles, correct dedupe, and no internal outputs as user prompts.
- **Rationale**: Prevent blank `{"role":"user","content":"\n\n"}` API payloads.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest tests/unit/test_message_contract.py -q
  ```

#### [NEW] `tests/unit/test_route_contracts.py`

- **Description**: Assert route tools are required; no keyword route inference exists; route source is tool-call for tool-capable models.
- **Rationale**: Keep routing model-owned without silent hardcoded inference.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest tests/unit/test_route_contracts.py -q
  ```

### Phase 1 — Task State Foundation

#### [MODIFY] `tinycua/models/task.py`

- **Description**: Implement typed task tree, active task ID, traversal helpers, transition validation, reviewer decisions, artifacts, serialization, and query helpers.
- **Rationale**: Worker runtime must execute a task tree, not only mark root metadata.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest tests/unit/test_task_state_store.py -q
  ```

#### [MODIFY] `tinycua/models/session.py`

- **Description**: Session owns task store, todo store, workspace/artifact context, and transition traces.
- **Rationale**: Avoid global state and cross-agent leakage.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest tests/unit/test_session_state_isolation.py -q
  ```

### Phase 2 — Tool Execution and Feedback

#### [MODIFY] `tinycua/loops/tinycua_loop.py`

- **Description**: Replace metadata-only tool execution with provider-compatible tool-result feedback and continuation calls. Support sync and streaming paths through shared execution lifecycle.
- **Rationale**: LLM must observe tool results to reason and continue.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest tests/unit/test_tool_result_feedback.py tests/integration/test_tool_feedback_integration.py -q
  ```

#### [MODIFY] `tinycua/tools/task_tools.py`

- **Description**: Make task tools session-bound, typed, error-safe, and active-task-aware.
- **Rationale**: Task tools are the primary mutation boundary.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest tests/unit/test_task_tools_session_bound.py -q
  ```

#### [MODIFY] `tinycua/tools/todo_tools.py`

- **Description**: Remove module-global todo singleton and bind todo tools to session state.
- **Rationale**: Todo state must be isolated per run/session.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest tests/unit/test_todo_tools_session_bound.py -q
  ```

#### [MODIFY] `tinycua/agent/tools/native/*`

- **Description**: Bind file/shell/python/web tools to workspace execution context and deny out-of-workspace file paths.
- **Rationale**: Native tool access must be safe and deterministic.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest tests/unit/test_native_tool_workspace.py tests/integration/test_workspace_isolation.py -q
  ```

### Phase 3 — Concrete Task Nodes

#### [MODIFY] `tinycua/loops/task_create.py`

- **Description**: Deterministically create root task from user/digest context; validate task exists; output typed task creation event.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest tests/unit/test_task_create_node.py -q
  ```

#### [MODIFY] `tinycua/loops/task_nodes.py` or split into dedicated files

- **Description**: Replace empty classes with concrete implementations:
  - `TinyCUATaskAnalyzerNode`
  - `TinyCUAAnalysisEffortNode`
  - `TinyCUATaskAssessorNode`
  - `TinyCUATaskExecutorNode`
  - `TinyCUAResultReviewerNode`
  - `TinyCUAResultAggregationNode`
- **Rationale**: Semantic node names must represent actual behavior.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest \
    tests/unit/test_task_analyzer_node.py \
    tests/unit/test_analysis_effort_node.py \
    tests/unit/test_task_assessor_node.py \
    tests/unit/test_task_executor_node.py \
    tests/unit/test_result_reviewer_node.py \
    tests/unit/test_result_aggregation_node.py -q
  ```

### Phase 4 — Dynamic Worker Runtime

#### [NEW] `tinycua/loops/worker_runtime.py`

- **Description**: Controller for worker-owned queue mutation based on task state, route decisions, active task status, reviewer decisions, retry counts, replans, and aggregation readiness.
- **Rationale**: Worker mode must be state-driven instead of hardcoded linear enqueue.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest tests/unit/test_worker_runtime_controller.py tests/integration/test_worker_runtime_paths.py -q
  ```

#### [MODIFY] `tinycua/loops/worker.py`

- **Description**: Keep Worker as route decision node only; delegate task lifecycle queue transitions to worker runtime controller.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest tests/unit/test_worker_node_routes.py -q
  ```

### Phase 5 — Streaming Runtime

#### [MODIFY] `tinycua/loops/tinycua_loop.py`

- **Description**: Unify sync/stream node execution; emit final-response stream separately from debug/internal stream; expose route and tool-result events; fail tests if fallback is treated as successful model output.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest tests/unit/test_stream_event_contract.py tests/integration/test_final_response_streaming.py -q
  ```

#### [MODIFY] `tinycua/cli/run.py`

- **Description**: Capture final stream, debug trace, task tree, artifacts, and usage separately.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest tests/integration/test_cli_runtime_outputs.py -q
  ```

### Phase 6 — Notebook Acceptance Demo

#### [MODIFY] `notebooks/tinycua_agent_trace_demo.ipynb`

- **Description**: Turn notebook into executable acceptance demo: configure workspace/artifact dirs, run simple and worker prompts, stream final response, show route decisions, show task tree, show artifacts, show tool results, and flag contract failures.
- **Validation**:
  ```bash
  cd src/tinycua && uv run pytest tests/integration/test_notebook_contract.py -q
  cd src/tinycua && TINYCUA_LIVE_LLM=1 uv run pytest tests/integration/test_notebook_contract_live.py -q
  ```

### Phase 7 — Live LLM Acceptance Gate

#### [NEW] `tests/integration/test_final_prototype_live.py`

- **Description**: Live local model tests for passthrough, worker task lifecycle, tool-result feedback, final streaming, and artifact output.
- **Validation**:
  ```bash
  cd src/tinycua && TINYCUA_LIVE_LLM=1 uv run pytest tests/integration/test_final_prototype_live.py -q
  ```

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| Task nodes | Modify | Replace empty stubs with concrete behavior and typed outputs. |
| Worker runtime | New | State-driven queue controller. |
| Tool execution | Modify | Tool results fed back to LLM and trace. |
| Task model | Modify | Full tree lifecycle and traversal. |
| Streaming | Modify | Separate final response stream from debug/internal events. |
| Notebook | Modify | Live acceptance demo with task tree/artifacts. |

## Data Model Changes

See `./design.md` Data Model section.

## API Changes

### New / Modified Functions

| Function | Change |
|----------|--------|
| `create_tinycua_agent(...)` | Add optional native tool/workspace helpers while preserving existing kwargs. |
| `TinyCUALoop.get_task_trace()` | New observability method. |
| `TinyCUALoop.get_state_snapshot()` | New state snapshot method. |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Existing notebook execution dependency or `nbclient` | project-compatible | Notebook acceptance tests. |

### Internal Dependencies

- [ ] Depends on source-of-truth docs in `src/tinycua/docs/design/` remaining stable during implementation.
- [ ] Blocks any claim that TinyCUA prototype runtime is complete.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Implementing everything in one oversized PR | High | Use this plan as the parent PR; implementation may be split by phase but cannot claim completion until all gates pass. |
| Mock tests pass while live LLM fails | High | Live local LLM acceptance required before final merge. |
| Reintroducing stubs | High | Static no-stub tests and review checklist. |
| Streaming remains noisy | Medium | Event contract tests and notebook contract tests. |
| Tool safety regressions | High | Workspace isolation and permission tests. |

---

*Generated from spec.md and design.md*  
*Last updated: 2026-06-15*
