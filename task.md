# Tasks: Tool Scoping (Milestone 4.2)

Implementation tasks for Tool Scoping. Check off items as completed.

> **Path convention**: All paths in this document are Python module paths relative to the `tinycua` package root (`src/tinycua/tinycua/`). For example, `tinycua/tools/task_tools.py` maps to `src/tinycua/tinycua/tools/task_tools.py`.

## TDD Phase (Tests First)

- [x] Create integration test file `tests/integration/test_tool_scoping_integration.py` with all test scenarios from implementation-plan.md <!-- id: 0 -->
- [x] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

### Phase 1 — Tool Scope Definitions

- [x] Create `tinycua/tools/task_tools.py` with TaskInit, TaskCreate, TaskInspect, TaskUpdate, TaskDecompose, TaskResultUpdate stubs <!-- id: 3 -->
  - [x] Implement TaskInitTool stub
  - [x] Implement TaskCreateTool stub
  - [x] Implement TaskInspectTool stub
  - [x] Implement TaskUpdateTool stub
  - [x] Implement TaskDecomposeTool stub
  - [x] Implement TaskResultUpdateTool stub
- [x] Create `tinycua/tools/todo_tools.py` with TodoRead, TodoWrite stubs <!-- id: 4 -->
  - [x] Implement TodoReadTool stub
  - [x] Implement TodoWriteTool stub
- [x] Create `tinycua/tools/enhanced_context_retrieval.py` with scoped cache + ReAct search stub <!-- id: 5 -->
  - [x] Implement cache file lifecycle (create on first call, reuse on subsequent)
  - [x] Implement ReAct-style search within cache
  - [x] Implement per-invocation scope isolation
- [x] Create `tinycua/tools/digest_information.py` with structured digest output stub <!-- id: 6 -->
- [x] Create `tinycua/config/tool_scopes.py` with factory functions for all 11 node types <!-- id: 7 -->
  - [x] Implement query_analyst_tool_scope()
  - [x] Implement information_digester_tool_scope()
  - [x] Implement worker_tool_scope()
  - [x] Implement task_create_tool_scope()
  - [x] Implement task_analyzer_tool_scope(mode) with mode-dependent TaskInit/TaskCreate
  - [x] Implement task_assessor_tool_scope()
  - [x] Implement task_executor_tool_scope()
  - [x] Implement result_reviewer_tool_scope()
  - [x] Implement result_aggregation_tool_scope()
  - [x] Implement response_tool_scope(allow_digest) with optional digest request
- [x] Wire tool scopes into node initialization in TinyCUALoop <!-- id: 8 -->
  - [x] Update _prepare_node() to use tool_scopes factory functions
  - [x] Ensure mode parameter is passed for TaskAnalyzerNode

### Phase 2 — Unit Tests

- [x] Create `tests/unit/test_tool_scopes.py` <!-- id: 9 -->
  - [x] Test query_analyst_tool_scope() matches design
  - [x] Test information_digester_tool_scope() matches design
  - [x] Test worker_tool_scope() matches design
  - [x] Test task_create_tool_scope() matches design
  - [x] Test task_analyzer_tool_scope() in all three modes
  - [x] Test task_assessor_tool_scope() matches design
  - [x] Test task_executor_tool_scope() matches design
  - [x] Test result_reviewer_tool_scope() matches design
  - [x] Test result_aggregation_tool_scope() matches design
  - [x] Test response_tool_scope() with allow_digest=True and False
  - [x] Test enhanced_context_retrieval cache creation and isolation
  - [x] Test digest_information output format

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 10 -->
- [x] Run unit tests for tool_scopes module <!-- id: 11 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 12 -->
- [ ] Verify no regressions in existing tests <!-- id: 13 -->

## Verification Phase

- [x] Verify TaskExecutor receives correct tools via _prepare_node() <!-- id: 14 -->
- [x] Verify TaskAnalyzerNode path-specific scoping (creation, recreation, reanalysis) <!-- id: 15 -->
- [x] Verify enhanced_context_retrieval cache isolation per invocation scope <!-- id: 16 -->
- [x] Verify deny-wins-over-allow behavior for outer tools <!-- id: 17 -->
- [x] Verify node tools always included even if denied <!-- id: 18 -->

## Documentation Phase

- [ ] Add docstrings to all factory functions in `tinycua/config/tool_scopes.py` and update `src/tinycua/docs/design/constants/tools.md` <!-- id: 19 -->
- [ ] Create or update `src/tinycua/README.md` tool scoping section <!-- id: 20 -->
- [ ] Create `CHANGELOG.md` if it doesn't exist, then add entry under Unreleased > Added <!-- id: 21 -->

## Review and Merge

- [ ] Create pull request <!-- id: 22 -->
- [ ] Address review feedback <!-- id: 23 -->
- [ ] Merge to main branch <!-- id: 24 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-13*
