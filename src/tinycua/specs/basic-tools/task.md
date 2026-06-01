# Tasks: Prototype M1 — Basic Tools

Implementation tasks for the basic tool layer (issue #70). Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for `register_all()`, SDK execution, todo list workflow, and context injection <!-- id: 1 -->
- [ ] Run integration tests — expect RED (failures) since implementation is not yet complete <!-- id: 2 -->

## Implementation Phase

### Phase 1 — Executor Context

- [ ] Create `tinycua/agent/tools/context.py` — `ExecutorConfig` and `ExecutorContext` dataclasses <!-- id: 3 -->
  - [ ] Define `ExecutorConfig` with shell_timeout, python_timeout, fetch_timeout, max_file_size, max_fetch_size, allowed_paths, enable_fetch, enable_python_exec
  - [ ] Define `ExecutorContext` with session (None for M1), todo_list, config

### Phase 2 — TodoList Tool

- [ ] Create `tinycua/agent/tools/todo/` package <!-- id: 4 -->
  - [ ] Create `tinycua/agent/tools/todo/__init__.py` with re-exports
  - [ ] Implement `todo_list.py` — `@tool`-decorated `todo_list` function with command routing (add/list/update/clear)
  - [ ] Implement `TodoList` class as in-memory list with add/list/update/clear methods
  - [ ] Update `tinycua/agent/tools/__init__.py` with todo tool export

### Phase 3 — Context Integration & register_all()

- [ ] Implement `register_all()` in `tinycua/agent/tools/__init__.py` <!-- id: 5 -->
  - [ ] Factory functions for each native tool that bind `ExecutorContext`
  - [ ] Optional context parameter (default: creates new `ExecutorContext` on first call)
  - [ ] Return all 8 tools (7 native + 1 todo)
- [ ] Update native tools to optionally accept context via factory wrappers (backward-compatible) <!-- id: 6 -->
  - [ ] `shell.py` — use context for `shell_timeout`
  - [ ] `files.py` — use context for `max_file_size`, `allowed_paths`
  - [ ] `web.py` — use context for `fetch_timeout`, `max_fetch_size`, `enable_fetch`
  - [ ] `python_exec.py` — use context for `python_timeout`, `enable_python_exec`

### Phase 4 — Unit Tests

- [ ] Write unit tests for `ExecutorContext` / `ExecutorConfig` <!-- id: 7 -->
- [ ] Write unit tests for `TodoList` class (add, list, update, clear, edge cases) <!-- id: 8 -->
- [ ] Write unit tests for context injection in native tools (shell, files, web, python_exec) <!-- id: 9 -->

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 10 -->
- [ ] Run unit tests for all new components <!-- id: 11 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 12 -->

## Verification Phase

- [ ] Verify all 7 native tools are importable and callable directly <!-- id: 13 -->
- [ ] Verify `todo_list` works through SDK `ToolExecutor` <!-- id: 14 -->
- [ ] Verify `register_all()` returns all 8 tools <!-- id: 15 -->

## Documentation Phase

- [ ] Update `tinycua/docs/` if applicable <!-- id: 16 -->
- [ ] Update `CHANGELOG.md` or release notes <!-- id: 17 -->

## Review and Merge

- [ ] Create pull request for `feat/m1-basic-tools` <!-- id: 18 -->
- [ ] Address review feedback <!-- id: 19 -->
- [ ] Merge to main branch <!-- id: 20 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-02*
