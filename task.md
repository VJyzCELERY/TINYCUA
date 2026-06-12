# Tasks: Tool Scoping (Milestone 4.2)

Implementation tasks for Tool Scoping. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Create integration test file `tests/integration/test_tool_scoping_integration.py` with all test scenarios from implementation-plan.md <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

### Phase 1 — Tool Scope Definitions

- [ ] Create `tinycua/tools/task_tools.py` with TaskInit, TaskCreate, TaskInspect, TaskUpdate, TaskDecompose, TaskResultUpdate stubs <!-- id: 3 -->
  - [ ] Implement TaskInitTool stub
  - [ ] Implement TaskCreateTool stub
  - [ ] Implement TaskInspectTool stub
  - [ ] Implement TaskUpdateTool stub
  - [ ] Implement TaskDecomposeTool stub
  - [ ] Implement TaskResultUpdateTool stub
- [ ] Create `tinycua/tools/todo_tools.py` with TodoRead, TodoWrite stubs <!-- id: 4 -->
  - [ ] Implement TodoReadTool stub
  - [ ] Implement TodoWriteTool stub
- [ ] Create `tinycua/tools/enhanced_context_retrieval.py` with scoped cache + ReAct search stub <!-- id: 5 -->
  - [ ] Implement cache file lifecycle (create on first call, reuse on subsequent)
  - [ ] Implement ReAct-style search within cache
  - [ ] Implement per-invocation scope isolation
- [ ] Create `tinycua/tools/digest_information.py` with structured digest output stub <!-- id: 6 -->
- [ ] Create `tinycua/config/tool_scopes.py` with factory functions for all 11 node types <!-- id: 7 -->
  - [ ] Implement query_analyst_tool_scope()
  - [ ] Implement information_digester_tool_scope()
  - [ ] Implement worker_tool_scope()
  - [ ] Implement task_create_tool_scope()
  - [ ] Implement task_analyzer_tool_scope(mode) with mode-dependent TaskInit/TaskCreate
  - [ ] Implement task_assessor_tool_scope()
  - [ ] Implement task_executor_tool_scope()
  - [ ] Implement result_reviewer_tool_scope()
  - [ ] Implement result_aggregation_tool_scope()
  - [ ] Implement response_tool_scope(allow_digest) with optional digest request
- [ ] Wire tool scopes into node initialization in TinyCUALoop <!-- id: 8 -->
  - [ ] Update _prepare_node() to use tool_scopes factory functions
  - [ ] Ensure mode parameter is passed for TaskAnalyzerNode

### Phase 2 — Unit Tests

- [ ] Create `tests/unit/test_tool_scopes.py` <!-- id: 9 -->
  - [ ] Test query_analyst_tool_scope() matches design
  - [ ] Test information_digester_tool_scope() matches design
  - [ ] Test worker_tool_scope() matches design
  - [ ] Test task_create_tool_scope() matches design
  - [ ] Test task_analyzer_tool_scope() in all three modes
  - [ ] Test task_assessor_tool_scope() matches design
  - [ ] Test task_executor_tool_scope() matches design
  - [ ] Test result_reviewer_tool_scope() matches design
  - [ ] Test result_aggregation_tool_scope() matches design
  - [ ] Test response_tool_scope() with allow_digest=True and False
  - [ ] Test enhanced_context_retrieval cache creation and isolation
  - [ ] Test digest_information output format

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 10 -->
- [ ] Run unit tests for tool_scopes module <!-- id: 11 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 12 -->
- [ ] Verify no regressions in existing tests <!-- id: 13 -->

## Verification Phase

- [ ] Verify TaskExecutor receives correct tools via _prepare_node() <!-- id: 14 -->
- [ ] Verify TaskAnalyzerNode path-specific scoping (creation, recreation, reanalysis) <!-- id: 15 -->
- [ ] Verify enhanced_context_retrieval cache isolation per invocation scope <!-- id: 16 -->
- [ ] Verify deny-wins-over-allow behavior for outer tools <!-- id: 17 -->
- [ ] Verify node tools always included even if denied <!-- id: 18 -->

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
