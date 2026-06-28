# Design Document: TinyCUA Source-of-Truth Runtime Closure

**Spec**: `./spec.md`
**Status**: In Progress
**Last Updated**: 2026-06-16

---

## Overview

This closes the remaining gap between TinyCUA’s implementation and its source-of-truth context-decomposition design. The runtime must be an SDK-compatible node queue where LLMs choose routes and tool actions, deterministic code only enforces contracts/orchestrates documented control flow, and every successful worker path is backed by actual task tools, workspace/research tools, reviewer decisions, aggregation, and final synthesis.

---

## Architecture

### Component Overview

```text
SDK Agent.run(...)
  -> TinyCUALoop
     -> QueryAnalyst (DecisionNode; select_query_route required)
        -> passthrough/uncertain -> ResponseNode
        -> worker -> InformationDigester -> Worker (DecisionNode; select_worker_route required)
             -> TaskCreate (task_init required)
             -> TaskAnalyzer (task structure tools)
             -> AnalysisEffort (deterministic effort controller)
                -> [TaskAssessor, TaskAnalyzer] repeated pass_limit times
             -> TaskExecutor (workspace/research tools + task_result_update required)
             -> ResultReviewer (task_review_decision required)
             -> ResultAggregation (task_inspect + actual task state)
             -> ResponseNode (final synthesis from actual context/evidence)
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.loops.tinycua_loop` | Modified | Central validation, streaming parity, trace visibility, no fallback outcomes. |
| `tinycua.loops.route_classifier` | Modified | Exact route validation only; no fallback label. |
| `tinycua.loops.query_analyst` | Modified | Fail/retry route tool contracts; no keyword fallback. |
| `tinycua.loops.worker` | Modified | Queue shapes and effort-driven planning must match docs. |
| `tinycua.loops.task_create` | Modified | Tool-owned root task creation guidance and validation. |
| `tinycua.loops.task_nodes` | Modified | Task analyzer/assessor/executor/reviewer/aggregation must not infer success from prose. |
| `tinycua.tools.task_tools` | Modified | Task mutation tools provide the only task-state mutation API exposed to LLM nodes. |
| `tinycua.config.tool_scopes` | Modified | Least-privilege tool exposure per docs. |
| `notebooks/tinycua_agent_trace_demo.ipynb` | Modified | Natural prompts, large context, no tiny iteration cap, visible state/trace/workspace. |
| Tests | Modified/New | Guardrails and live/deterministic contracts. |

---

## Data Model

### Schema Changes

- `SessionConfig.worker_effort` controls AnalysisEffort pass limits.
- Task tool results remain in LLM/tool metadata for traceability.
- `TaskStateStore` remains the authoritative task tree. Task tools mutate it.
- `TaskReviewDecisionTool` records reviewer decisions explicitly.

No SDK schema changes are allowed.

---

## API / Interface Contracts

### Modified Functions / Contracts

```python
SessionConfig(worker_effort: Literal["none", "low", "medium", "high"] = "medium")
```

`worker_effort` maps to upfront planning passes:

| Effort | Passes |
|--------|--------|
| none | 0 |
| low | 1 |
| medium | 2 |
| high | 3 |

```python
TaskReviewDecisionTool(task_id: str | None, decision: str, rationale: str = "") -> dict
```

Records a `ReviewerDecision` for the active or specified task.

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Missing route tool call | `ValidationResult(is_valid=False)` then retry/exhaustion trace | No route fallback. |
| Missing task-state tool | `ValidationResult(is_valid=False)` then retry/exhaustion trace | No prose-derived task state. |
| Planner-only TaskExecutor output | Retry/exhaustion trace | No scaffold fallback. |
| Empty final text | Empty output remains visible | No synthetic terminal filler. |
| Live model cannot satisfy tools | Visible diagnostics/trace | Do not fake completion. |

---

## Implementation Phases

### Phase 1 — Documentation and Audit

- [x] Re-read source-of-truth architecture docs.
- [x] Capture zero-shortcut closure spec and design.
- [ ] Create a task checklist for iterative implementation/self-review.
- [ ] Audit runtime against forbidden shortcut categories.

### Phase 2 — Runtime Contract Closure

- [ ] Ensure DecisionNode/loop route validation retries and fails closed while giving the LLM actionable tool-use retry instructions.
- [ ] Ensure TaskCreate requires `task_init` and gives the model enough context to choose its own root title/description.
- [ ] Ensure TaskAnalyzer/TaskAssessor use task tools for decomposition/assessment and do not require hardcoded titles.
- [ ] Implement AnalysisEffort as the documented pass controller rather than pre-spawning fixed analyzer nodes.
- [ ] Ensure TaskExecutor can one-shot simple workspace/research tasks by guiding tool use and result recording, not by forcing outcomes.
- [ ] Ensure ResultReviewer records explicit decisions through tools and drives retry/replan/aggregation by task state.
- [ ] Ensure ResultAggregation does not mark root complete when prerequisite task state is missing.
- [ ] Make streaming/non-streaming validation equivalent.

### Phase 3 — Tests and Live Validation

- [ ] Add/adjust deterministic tests for direct response, worker app creation, planner-only failure, and streaming parity.
- [ ] Extend no-stub/no-shortcut guardrails.
- [ ] Run broad deterministic suite with `uv run`.
- [ ] Run live notebook contract against local LLM.
- [ ] Run manual live prompts: direct response, app creation, deep research.

---

## Technical Decisions

1. **Decision**: Runtime may require certain tools for nodes (`select_*_route`, `task_init`, `task_result_update`, `task_review_decision`) but may not choose their arguments/outcomes.
   - **Reason**: This enforces architecture contracts without hardcoding model decisions.
   - **Alternatives Considered**: Parse prose into state — rejected because it fabricates state and hides failures.

2. **Decision**: AnalysisEffort pass count is deterministic control flow.
   - **Reason**: Source docs define effort as an orchestration parameter, not an LLM decision.
   - **Alternatives Considered**: Ask the LLM how many passes to run — rejected because `worker_effort` explicitly configures pass limits.

3. **Decision**: Failures remain visible in trace/diagnostics and can still proceed to final response only as failure reporting, not success.
   - **Reason**: Research prototype needs truthful observability.
   - **Alternatives Considered**: Continue with synthetic aggregate success — rejected as shortcut behavior.

4. **Decision**: Notebook cleans its demo workspace by default but does not create demo files itself.
   - **Reason**: Prevents stale artifact confusion while preserving LLM-owned creation.
   - **Alternatives Considered**: Leave stale files — rejected because it can look like success from previous runs.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Local LLM ignores tools | High | Worker path fails | Stronger node instructions, retry continuations, visible failure; no fake success. |
| Tool schema is unclear to model | Medium | Tool calls malformed | Improve tool descriptions/schemas where available; deterministic validation. |
| Streaming path bypasses validation | Medium | Inconsistent behavior | Shared validation helpers and streaming tests. |
| Overcorrection makes deterministic tests brittle | Medium | False failures | Test contracts and evidence, not exact prose. |
| Stale notebook artifacts confuse live validation | High | False success | Clean workspace by default and list files after run. |

---

## Open Questions _(optional)_

None. The user explicitly prioritized source-of-truth correctness over shortcut “working” behavior.

---

## References

- Spec: `./spec.md`
- Source docs:
  - `src/tinycua/docs/architecture/overview.md`
  - `src/tinycua/docs/design/loops/overview.md`
  - `src/tinycua/docs/design/loops/expected_scenarios.md`
  - `src/tinycua/docs/design/loops/query_analyst.md`
  - `src/tinycua/docs/design/loops/worker.md`
  - `src/tinycua/docs/design/loops/task_create.md`
  - `src/tinycua/docs/design/loops/task_analyzer.md`
  - `src/tinycua/docs/design/loops/analysis_effort.md`
  - `src/tinycua/docs/design/loops/task_executor.md`
  - `src/tinycua/docs/design/loops/result_reviewer.md`
  - `src/tinycua/docs/design/loops/result_aggregation.md`
  - `src/tinycua/docs/design/constants/tools.md`
