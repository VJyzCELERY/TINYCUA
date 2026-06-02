# Tasks: M1 — Basic Tools

Implementation tasks for M1 Basic Tools. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests (defined in `implementation-plan.md` — `tests/integration/test_basic_tools_e2e.py`) <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

### Phase 1 — Native Tool Result Model

- [ ] Create `tinycua/tools/__init__.py` — public exports <!-- id: 2 -->
  - [ ] Export `ToolResult` from `tinycua.tools.result`
  - [ ] Export all tool functions from their modules
- [ ] Create `tinycua/tools/result.py` — `ToolResult` dataclass <!-- id: 3 -->
  - [ ] Fields: `success` (bool), `output` (str), `error` (str | None), `metadata` (dict | None), `duration` (float)
  - [ ] `.to_dict()` method for JSON serialization
- [ ] Write unit tests: `tests/unit/test_tool_result.py` <!-- id: 4 -->
  - [ ] Test all fields with default values
  - [ ] Test `.to_dict()` serialization

### Phase 2 — Native Execution Tools

- [ ] Create `tinycua/tools/native/__init__.py` — re-exports <!-- id: 5 -->
- [ ] Create `tinycua/tools/native/shell.py` — `run_shell` (adapted from `agent/tools/native/shell.py`) <!-- id: 6 -->
  - [ ] Verify `@tool` decorator, JSON-serializable return
  - [ ] Error paths: command not found, timeout, subprocess error
- [ ] Create `tinycua/tools/native/files.py` — `read_file`, `write_file`, `list_files` (adapted from `agent/tools/native/files.py`) <!-- id: 7 -->
  - [ ] `read_file`: full-file with truncation, line-range support, error paths
  - [ ] `write_file`: parent dir creation, success/error returns
  - [ ] `list_files`: glob pattern, error paths
  - [ ] Note: `edit_file` stays in `agent/tools/native/` (not part of basic tools spec)
- [ ] Create `tinycua/tools/native/web.py` — `fetch_url` (adapted from `agent/tools/native/web.py`) <!-- id: 8 -->
  - [ ] Support GET/POST, configurable headers, timeout, max_size truncation
- [ ] Create `tinycua/tools/native/python_exec.py` — `run_python` (adapted from `agent/tools/native/python_exec.py`) <!-- id: 9 -->
  - [ ] Subprocess execution with timeout, syntax error handling, infinite loop protection

### Phase 3 — Task Mutation Helpers

- [ ] Create `tinycua/tools/task/__init__.py` — re-exports <!-- id: 10 -->
- [ ] Create `tinycua/tools/task/_mutation.py` — internal helpers <!-- id: 11 -->
  - [ ] `_apply_task_mutation(session, mutator)` — clone → mutate → re-index → atomic swap
  - [ ] `_reindex_tree(root)` — DFS re-indexing with task ID encoding (`T-0`, `T-0.1`, etc.)
  - [ ] `_reindex_children(parent, prefix)` — recursive child re-indexing
  - [ ] `_remove_by_id(parent, target_id, collect)` — DFS removal with cascading delete
  - [ ] `_collect_ids(task, collect)` — collect task + descendant IDs
  - [ ] `_find_parent_and_child(parent, target_id)` — DFS search for task and its parent
  - [ ] `_is_ancestor(ancestor, target_id)` — recursive ancestor check
- [ ] Write unit tests: `tests/unit/test_task_mutation.py` <!-- id: 12 -->
  - [ ] Test `_reindex_tree` on simple and nested trees
  - [ ] Test `_remove_by_id` leaf, branch, and root (forbidden)
  - [ ] Test `_collect_ids` on nested tree
  - [ ] Test `_find_parent_and_child` on sibling and descendant targets
  - [ ] Test `_is_ancestor` true/false cases
  - [ ] Test `_apply_task_mutation` atomic swap behavior

### Phase 4 — Task Read Tools

- [ ] Create `tinycua/tools/task/read.py` — read-only task tools <!-- id: 13 -->
  - [ ] `ReadActiveTask()` — DFS pre-order traversal, return next non-completed leaf, None if no task tree
  - [ ] `ReadTask(task_id)` — lookup by ID, return dict or None
  - [ ] `ListTask()` — markdown tree with status markers: `[ ]` not_started, `[*]` inprogress, `[x]` completed, `[-]` failed, `[/]` blocked
  - [ ] Shared `_task_to_dict(task)` helper
- [ ] Write unit tests: `tests/unit/test_task_tools_read.py` <!-- id: 14 -->
  - [ ] Test `ReadActiveTask` with various tree states (no tree, all completed, active available)
  - [ ] Test `ReadTask` existing, missing, and invalid IDs
  - [ ] Test `ListTask` empty tree, populated tree, completed tree

### Phase 5 — Task Write Tools

- [ ] Create `tinycua/tools/task/write.py` — all 8 task mutation tools <!-- id: 15 -->
  - [ ] `TaskInit(primary_task_data, sub_task)` — replace entire tree
  - [ ] `SetSubTask(parent_task_id, sub_task)` — replace parent's children
  - [ ] `AddSubTask(parent_task_id, sub_task)` — append children
  - [ ] `DeleteSubTask(task_id)` — delete task + descendants (root forbidden)
  - [ ] `EditSubTask(task_id, task_data)` — edit metadata only
  - [ ] `SwapTask(task_id_1, task_id_2)` — swap with ancestor circularity check
  - [ ] `UpdateTaskResult(task_id, result_data)` — update any task's result
  - [ ] `UpdateActiveTaskResult(result_data)` — update only active leaf's result
- [ ] Write unit tests: `tests/unit/test_task_tools_write.py` <!-- id: 16 -->
  - [ ] Test `TaskInit` with and without sub_tasks
  - [ ] Test `SetSubTask` replace, empty (toggle to leaf), invalid parent
  - [ ] Test `AddSubTask` append to existing, append to leaf (container toggle)
  - [ ] Test `DeleteSubTask` single, multiple, root (forbidden), branch
  - [ ] Test `EditSubTask` valid metadata fields, structural fields (rejected)
  - [ ] Test `SwapTask` siblings, cross-parent, ancestor circularity (rejected)
  - [ ] Test `UpdateTaskResult` valid/arbitrary task
  - [ ] Test `UpdateActiveTaskResult` with active task, without active task

### Phase 6 — TodoList Tool

- [ ] Create `tinycua/tools/todo.py` — TodoList tool <!-- id: 17 -->
  - [ ] Sub-commands: `add`, `read`, `mark_complete`, `mark_incomplete`, `edit`, `delete`, `clear`
  - [ ] Store on `session.todo_list`
  - [ ] Pre-initialization behavior: auto-init on first add
  - [ ] Formatted markdown checklist output
- [ ] Write unit tests: `tests/unit/test_todo.py` <!-- id: 18 -->
  - [ ] Test all 7 sub-commands
  - [ ] Test pre-init behavior (read/delete/clear on None)
  - [ ] Test empty list handling
  - [ ] Test invalid index handling

### Phase 7 — Digester Retrieval Tool Interface

- [ ] Create `tinycua/tools/digester.py` <!-- id: 19 -->
  - [ ] `create_enhanced_context_retrieval(cache_path, model, exploration_tools)` — factory returning a Tool
  - [ ] `digest_information(context_summary, key_points, advisory_instructions, constraints, known_gaps)` — structured digest (prefixes with `DIGEST_INFO::`)
- [ ] Write unit tests: `tests/unit/test_digester.py` <!-- id: 20 -->
  - [ ] Test `digest_information` output format
  - [ ] Test `create_enhanced_context_retrieval` returns a Tool

### Phase 8 — Tool Constants

- [ ] Create `tinycua/constants/__init__.py` <!-- id: 21 -->
- [ ] Create `tinycua/constants/tools.py` — all `*_BASE_TOOLS` constants <!-- id: 22 -->
  - [ ] `SHARED_AGENT_BASE_TOOLS`
  - [ ] `READ_ONLY_TASK_TOOLS`
  - [ ] `WRITE_TASK_TOOLS`
  - [ ] `TASK_EXECUTOR_BASE_TOOLS`
  - [ ] `RESULT_REVIEWER_BASE_TOOLS`
  - [ ] `QUERY_ANALYST_BASE_TOOLS`
  - [ ] `INFORMATION_DIGESTER_BASE_TOOLS`
  - [ ] `TASK_ANALYZER_BASE_TOOLS`
  - [ ] `TASK_ASSESSOR_BASE_TOOLS`
  - [ ] `PRIMARY_AGENT_BASE_TOOLS`
  - [ ] `CONTEXT_CACHE_TOOLS`
  - [ ] `EXPLORATION_TOOL`
- [ ] Write unit tests: `tests/unit/test_tool_constants.py` <!-- id: 23 -->
  - [ ] Test each constant is a list
  - [ ] Test each list contains expected tool instances

### Phase 9 — Update Existing Package Exports

- [ ] Update `tinycua/agent/tools/__init__.py` — add new tool imports for backward compat <!-- id: 24 -->
- [ ] Update `tinycua/tools/__init__.py` — ensure all tools are publicly exported <!-- id: 25 -->

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 26 -->
- [ ] Write additional unit tests for edge cases discovered during implementation <!-- id: 27 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 28 -->
- [ ] Run specific test suite: `cd src/tinycua && uv run pytest tests/test_tools* tests/test_task_tools* tests/test_todo*` <!-- id: 29 -->

## Verification Phase

- [ ] Verify all tools importable from `tinycua.tools` <!-- id: 30 -->
- [ ] Verify all tools register with SDK Agent via `ToolExecutor` <!-- id: 31 -->
- [ ] Verify native tools work end-to-end: write → read → list → delete cycle <!-- id: 32 -->
- [ ] Verify task tools work end-to-end: init → set → add → swap → delete → re-read <!-- id: 33 -->
- [ ] Verify TodoList tool works end-to-end: add → read → mark → edit → delete → clear <!-- id: 34 -->

## Documentation Phase

- [ ] Update `src/tinycua/README.md` if needed (optional) <!-- id: 35 -->

## Review and Merge

- [ ] Create pull request for code review <!-- id: 36 -->
- [ ] Address review feedback <!-- id: 37 -->
- [ ] Merge to main branch <!-- id: 38 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-02*
