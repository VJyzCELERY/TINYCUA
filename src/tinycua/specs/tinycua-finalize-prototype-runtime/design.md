# Design Document: TinyCUA Final Prototype Runtime

**Spec**: `./spec.md`  
**Status**: Draft  
**Last Updated**: 2026-06-24

---

## Overview

This design repairs TinyCUA from a traceable scaffold into a usable prototype runtime. The key architectural decision is to implement the documented worker/task lifecycle as a state-driven runtime: decision nodes route through tools, task nodes own concrete behavior, tool results are fed back to the model, task state is session/workspace-scoped, and streaming separates final user-facing response tokens from internal debug events.

This document intentionally does not modify source-of-truth docs under `src/tinycua/docs/design/`; it translates that source of truth into an implementation design and validation plan.

---

## Architecture

### Component Overview

```text
SDK Agent.run(...)
  |
  v
TinyCUALoop
  |-- QueryAnalystDecision
  |     |-- route=passthrough ---------------------> ResponseNode
  |     |-- route=worker -> InformationDigester -> WorkerDecision
  |
  v
WorkerRuntimeController
  |-- task_creation -----> TaskCreate -> TaskAnalyzer -> AnalysisEffort loop
  |-- task_recreation ---> TaskAnalyzer(recreation) -> AnalysisEffort loop
  |-- task_reanalysis ---> TaskAnalyzer(reanalysis) -> AnalysisEffort loop
  |-- proceed_execution -> TaskExecutor -> ResultReviewer
  |-- passthrough -------> ResponseNode

Task lifecycle loop
  TaskAssessor <-> TaskAnalyzer       # effort/replan loops
       |
       v
  TaskExecutor -> ResultReviewer
       |             |-- accept -> next active task or ResultAggregation
       |             |-- retry  -> TaskExecutor(same active task)
       |             |-- replan -> TaskAssessor(local) -> TaskAnalyzer(local) -> TaskExecutor
       |             |-- open_question -> mandatory passthrough / user continuation
       v
  ResultAggregation -> ResponseNode
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.loops.tinycua_loop.TinyCUALoop` | Modified | Becomes orchestrator with shared sync/stream node execution, tool feedback, queue control, and state snapshots. |
| `tinycua.loops.worker.TinyCUAWorkerNode` | Modified | Routes only; no task mutation. Queue mutation delegated to controller. |
| `tinycua.loops.task_nodes.*` | Modified | Empty stubs replaced by concrete node classes with typed outputs and completion behavior. |
| `tinycua.loops.task_create.TinyCUATaskCreateNode` | Modified | Deterministic root task creation with validation and typed output. |
| `tinycua.models.task` | Modified | Full task tree, active task traversal, reviewer decisions, artifacts, status transitions. |
| `tinycua.tools.task_tools` | Modified | Session-bound task tools with typed results and structured errors. |
| `tinycua.tools.todo_tools` | Modified | Session-bound todo store; remove module-global state. |
| `tinycua.agent.tools.native.*` | Modified | Workspace-bound execution context for file/shell/python/web tools. |
| `tinycua.config.tool_scopes` | Modified | Least-privilege node scopes matching source-of-truth docs and actual native tool names. |
| `tinycua.models.stream_event` | Modified/New | Final/debug stream visibility helpers and route/tool-result events. |
| `notebooks/tinycua_agent_trace_demo.ipynb` | Modified | Acceptance demo with final response, task tree, artifacts, routes, tool results, and live streaming. |
| `tinycua.loops.lazy_templates` | New | v1 markdown templates, node→tool registry, and markdown parser for lazy retry (FR-087..FR-093). |
| `tinycua.loops.validation_retry_mixin.ValidationRetryMixin` | Modified | Adds `_maybe_lazy_recovery` and `_lazy_gate_passes` (lazy retry core + gate). |
| `tinycua.config.session_config.SessionConfig` | Modified | Adds `recovery_strategy: Literal["standard", "markdown_synthesis"]` (default `"standard"`). |
| `tinycua.loops.tinycua_loop.TinyCUALoop` | Modified | Wires lazy retry into `_call_node_with_retry` (sync in-loop path). |
| `tinycua.loops.orchestration_mixin` | Modified | Wires lazy retry into `_stream_llm_node_events` (stream in-loop) and `_execute_node` / `_stream_exhausted_node_events` (pre-`_unbounded_recovery`). |
| `tinycua.loops._loop_constants` | Modified | Adds `_LAZY_BUDGET = 3` constant. |
| `tinycua.cli.main` / `tinycua.cli.run` | Modified | Adds `--recovery-strategy {standard,markdown_synthesis}` CLI flag threaded into `SessionConfig`. |

---

## Data Model

### New / Modified Entities _(conceptual)_

```python
TaskStatus:
    PENDING
    IN_PROGRESS
    BLOCKED
    DONE
    FAILED

ReviewerDecision:
    ACCEPT
    RETRY
    REPLAN
    OPEN_QUESTION

TaskArtifact:
    path: Path
    kind: str
    producing_node_id: str
    metadata: dict[str, Any]

TaskResult:
    execution_status: str
    reviewer_decision: ReviewerDecision | None
    summary: str
    artifacts: list[TaskArtifact]
    tool_results: list[ToolExecutionResult]

Task:
    task_id: str
    title: str
    description: str
    status: TaskStatus
    parent_id: str | None
    children: list[str]
    active_child_id: str | None
    result: TaskResult | None
    metadata: dict[str, Any]

TaskStateStore:
    root_task_id: str | None
    active_task_id: str | None
    tasks: dict[str, Task]
    transition_log: list[TaskTransition]
```

### Schema Changes _(if applicable)_

- Existing `TaskStateStore` grows traversal, query, transition, serialization, and validation methods.
- `Session` owns task/todo/workspace state; no module-global task/todo state remains.
- Trace snapshots expose JSON-safe task state and transition summaries.

---

## API / Interface Contracts

### Modified Public Factory

```python
def create_tinycua_agent(
    session: Session | None = None,
    session_config: SessionConfig | None = None,
    enable_native_tools: bool = False,
    native_tool_policy: NativeToolPolicy | None = None,
    **agent_kwargs: Any,
) -> Agent:
    """Create an SDK Agent with TinyCUA loop and optional workspace-bound native tools."""
```

### Loop Observability

```python
loop.get_execution_trace() -> list[dict[str, Any]]
loop.get_task_trace() -> list[dict[str, Any]]
loop.get_state_snapshot() -> dict[str, Any]
loop.get_final_response_events() -> list[dict[str, Any]]
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Required route tool not called | Validation retry, then node execution error or explicit invalid-route trace | No silent keyword fallback. With `recovery_strategy="markdown_synthesis"`, missing-state-tool failures additionally attempt one markdown-synthesis continuation (FR-088) before standard recovery. |
| Tool call outside scope | Tool rejection event + validation context | Must be visible to model and trace. |
| Tool path outside workspace | Permission/path error tool result | Must not mutate filesystem. |
| Task transition invalid | Structured task error and reviewer/replan path | No unchecked status changes. |
| ResponseNode emits no text | Contract failure in tests unless explicitly configured fallback mode | Notebook must flag synthetic fallback as failure. |

---

## Implementation Phases

### Phase 0 — Guardrails and Contract Tests

- [ ] Add tests that fail for blank API messages and wrong internal roles.
- [ ] Add tests that fail if any worker/task node class is empty or lacks behavior tests.
- [ ] Add tests that fail if source-of-truth docs are modified by runtime implementation PRs.
- [ ] Add route-tool-required tests with no keyword inference.

### Phase 1 — Task State Foundation

- [ ] Implement typed task tree, active task traversal, status transitions, artifacts, reviewer decisions.
- [ ] Session-bind task and todo stores.
- [ ] Add JSON-safe snapshots and transition logs.

### Phase 2 — Tool Execution and Feedback

- [ ] Implement provider-compatible tool result messages.
- [ ] Feed tool results back into node LLM continuation when needed.
- [ ] Bind native tools to `SessionConfig.workspace_dir`.
- [ ] Add scoped tool rejection and error feedback.

### Phase 3 — Concrete Worker/Task Nodes

- [ ] Implement TaskCreate concrete behavior.
- [ ] Implement TaskAnalyzer modes.
- [ ] Implement AnalysisEffort effort loop.
- [ ] Implement TaskAssessor active-task selection/reanalysis decisions.
- [ ] Implement TaskExecutor active-task execution.
- [ ] Implement ResultReviewer accept/retry/replan/open-question decisions.
- [ ] Implement ResultAggregation structured aggregation.

### Phase 4 — Dynamic Queue Runtime

- [ ] Replace forced worker chain with state-driven queue mutation.
- [ ] Implement reviewer retry/replan loops.
- [ ] Implement mandatory passthrough/user-continuation behavior.
- [ ] Implement ResponseNode digester suspension/resumption if context is insufficient.

### Phase 5 — Streaming and Demo Usability

- [ ] Provide final-response-only streaming mode.
- [ ] Emit route-decision and tool-result events.
- [ ] Keep debug stream available but separate from final response tokens.
- [ ] Update notebook into a live acceptance demo.
- [ ] Add CLI transcript/task-tree/artifact export.

### Phase 6 — Live LLM Acceptance

- [ ] Add live local LLM tests for passthrough, worker task lifecycle, tool use, streaming, and notebook execution.
- [ ] Gate PR completion on passing deterministic tests and documented live validation.

### Phase 7 — Markdown-Synthesis Retry (Lazy Retry)

Runtime reliability follow-up — see `runtime-reliability-implementation-plan.md` for the full design and `spec.md` FR-087..FR-093.

- [ ] Add `SessionConfig.recovery_strategy` toggle (default `standard`) and `_LAZY_BUDGET` constant.
- [ ] Implement `loops/lazy_templates.py`: v1 templates + node→tool registry + markdown parser.
- [ ] Implement `_maybe_lazy_recovery` + `_lazy_gate_passes` on `ValidationRetryMixin`.
- [ ] Wire lazy retry into `_call_node_with_retry` (sync in-loop), `_stream_llm_node_events` (stream in-loop), and `_execute_node` / `_stream_exhausted_node_events` (pre-`_unbounded_recovery`).
- [ ] Add `--recovery-strategy` CLI flag.
- [ ] Deterministic regression: existing recovery tests pass unchanged with `recovery_strategy="standard"`; new lazy tests pass with `"markdown_synthesis"`.

---

## Technical Decisions

1. **Decision**: Replace node-id string lifecycle markers with node-owned typed outputs and controller-owned state transitions.
   - **Reason**: String markers hide missing behavior and make stubs look implemented.
   - **Alternatives Considered**: Keep loop-level markers — rejected because it caused the current linear scaffold.

2. **Decision**: Tool results must become LLM-visible messages, not metadata-only trace records.
   - **Reason**: Agentic tool reasoning requires observing tool outputs.
   - **Alternatives Considered**: Metadata-only trace — rejected because it is unusable by the model.

3. **Decision**: Streaming should have two views: final-response stream and debug/internal stream.
   - **Reason**: Users need readable token streaming; developers need traces.
   - **Alternatives Considered**: Single stream with all events — rejected because it creates notebook noise.

4. **Decision**: Live LLM tests are required for acceptance but deterministic tests remain primary for CI reliability.
   - **Reason**: The prototype explicitly targets a local LLM endpoint; mock-only validation previously hid runtime failures.

5. **Decision** (FR-087..FR-093): When a node's required state tool is missing, attempt one no-tools markdown-synthesis continuation before standard tool-exposed retries.
   - **Reason**: Experiment data shows retry is the dominant latency cost; the model has usually done the work but simply did not emit the state tool. A single no-tools continuation that asks the model to fill a small markdown template is far cheaper than N tool-exposed retries (25 in-loop + 30 recovery) and lands the call in ~2 LLM round-trips.
   - **Alternatives Considered**: More tool-exposed retries (rejected — rarely land and dominate latency); force-approve after exhaustion (rejected — loses task-state reliability).

6. **Decision** (FR-091): A lazy call that returns `None` (parse fail / empty response / exec error) does not consume a lazy attempt slot.
   - **Reason**: A parse failure tells us nothing useful and falls through to standard retry for the same attempt; burning a lazy slot on it would waste budget. Only a lazy call that actually ran and returned non-None counts toward the 3-attempt budget.
   - **Alternatives Considered**: Count every lazy attempt including `None` (rejected — 3 bad markdown parses would eat the entire lazy budget without ever trying standard retry).

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Scope grows too large | High | High | Phase implementation; each phase must have acceptance tests and can be reviewed independently. |
| Live LLM nondeterminism | Medium | High | Use exact environment contract, deterministic prompts, route tool requirements, and separate unit mocks. |
| Native tool safety | Medium | High | Workspace confinement, allowlists, permission policy, path traversal tests. |
| Streaming regressions | Medium | Medium | Snapshot event contract tests and notebook execution tests. |
| Hidden stubs reintroduced | High | High | Static tests for empty node classes and behavior coverage gates. |

---

## Open Questions _(optional)_

1. Should shell/python native tools be disabled by default and enabled only in demos/benchmarks?
2. Should live LLM tests be required in CI or documented as maintainer-run release gates?
3. Should task tree exports be JSON, Markdown, or both for notebooks/CLI?

---

## References

- Spec: `./spec.md`
- Source of truth: `../../docs/design/`
- Worker design: `../../docs/design/loops/worker.md`
- Task model design: `../../docs/design/models/task.md`
- Tool scoping design: `../../docs/design/constants/tools.md`
