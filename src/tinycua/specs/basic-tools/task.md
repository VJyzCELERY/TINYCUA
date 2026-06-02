# Tasks: M1 — Basic Tools

Implementation tasks for M1 Basic Tools. Check off items as completed.

**Scope change**: M1 now delivers only stateless tool primitives — ToolResult model, native execution tools (shell, file, web, python), and minimal non-session-dependent tool constants. Session-dependent tools (TodoList, digester interface, per-agent `*_BASE_TOOLS`) are **deferred to M2**.

---

## TDD Phase (Tests First)

- [ ] Write integration tests (defined in `implementation-plan.md` — `tests/unit/test_basic_tools_e2e.py`) <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

### Phase 1 — Native Tool Result Model

- [ ] Create `tinycua/tools/__init__.py` — public exports <!-- id: 2 -->
  - [ ] Export `ToolResult` from `tinycua.tools.result`
  - [ ] Export all native tool functions from their modules
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

### Phase 3 — Tool Constants (M1-scoped)

- [ ] Create `tinycua/constants/__init__.py` <!-- id: 10 -->
- [ ] Create `tinycua/constants/tools.py` — M1-scoped constants only <!-- id: 11 -->
  - [ ] `NATIVE_BASE_TOOLS` — list of the six native execution tools (run_shell, read_file, write_file, list_files, fetch_url, run_python)
  - [ ] `READ_ONLY_TASK_TOOLS` — forward reference to M2 (placeholder, not implemented yet)
  - [ ] Note: per-agent `*_BASE_TOOLS` (SHARED_AGENT_BASE_TOOLS, TASK_EXECUTOR_BASE_TOOLS, etc.) are deferred to M2
- [ ] Write unit tests: `tests/unit/test_tool_constants.py` <!-- id: 12 -->
  - [ ] Test `NATIVE_BASE_TOOLS` contains expected native tool functions
  - [ ] Test `READ_ONLY_TASK_TOOLS` exists as a forward reference

### Phase 4 — Update Existing Package Exports

- [ ] Update `tinycua/agent/tools/__init__.py` — add native tool imports for backward compat <!-- id: 13 -->
- [ ] Update `tinycua/tools/__init__.py` — ensure all native tools are publicly exported <!-- id: 14 -->

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 15 -->
- [ ] Write additional unit tests for edge cases discovered during implementation <!-- id: 16 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 17 -->

## Verification Phase

- [ ] Verify all native tools importable from `tinycua.tools` <!-- id: 18 -->
- [ ] Verify all native tools register with SDK Agent via `AgentExecutor` <!-- id: 19 -->
- [ ] Verify native tools work end-to-end: write → read → list → shell → python <!-- id: 20 -->
- [ ] Verify `NATIVE_BASE_TOOLS` constant is importable and correct <!-- id: 21 -->
- [ ] Verify no session-dependent tools (TodoList, digester) are present in M1 <!-- id: 22 -->

## Documentation Phase

- [ ] Update `src/tinycua/README.md` if needed (optional) <!-- id: 23 -->

## Review and Merge

- [ ] Create pull request for code review <!-- id: 24 -->
- [ ] Address review feedback <!-- id: 25 -->
- [ ] Merge to main branch <!-- id: 26 -->

---

## M2 Forward Reference

The following are **deferred to M2** (see `src/tinycua/specs/basic-tools/spec.md` and `#71`):

- **TodoList tool**: `tinycua/tools/todo.py` with sub-commands add/read/mark/delete/clear — depends on `session.todo_list`
- **Digester tool interface**: `tinycua/tools/digester.py` with `create_enhanced_context_retrieval` + `digest_information` — depends on session context cache
- **Per-agent `*_BASE_TOOLS`**: SHARED_AGENT_BASE_TOOLS, TASK_EXECUTOR_BASE_TOOLS, RESULT_REVIEWER_BASE_TOOLS, QUERY_ANALYST_BASE_TOOLS, INFORMATION_DIGESTER_BASE_TOOLS, TASK_ANALYZER_BASE_TOOLS, TASK_ASSESSOR_BASE_TOOLS, PRIMARY_AGENT_BASE_TOOLS, CONTEXT_CACHE_TOOLS, EXPLORATION_TOOL
- **Task tools**: ReadActiveTask, ReadTask, ListTask, TaskInit, SetSubTask, AddSubTask, DeleteSubTask, EditSubTask, SwapTask, UpdateTaskResult, UpdateActiveTaskResult — depend on Task/TaskResult state objects

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-02*
