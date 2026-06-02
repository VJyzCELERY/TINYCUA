# Tasks: Prototype M1 — Basic Tools

Implementation tasks for the basic tool layer (issue #70). Check off items as completed.

## Prerequisites

- [x] Verify native tools are implemented from `native_tools/spec.md` (FR-001–FR-009) before starting M1 modifications <!-- id: 0 -->

## TDD Phase (Tests First)

- [x] Write integration tests for `register_all()`, SDK execution, todo list workflow, and context injection <!-- id: 1 -->
- [x] Write unit tests for `ExecutorContext` / `ExecutorConfig` <!-- id: 7 -->
- [x] Write unit tests for `TodoList` class (add, list, update, clear, edge cases) <!-- id: 8 -->
- [x] Write unit tests for context injection in native tools (shell, files, web, python_exec) <!-- id: 9 -->
- [x] Run all new tests — expect RED (failures) since implementation is not yet complete <!-- id: 2 -->

## Implementation Phase

### Phase 1 — Executor Context & Native Tools

- [x] Create `tinycua/agent/tools/context.py` — `ExecutorConfig` and `ExecutorContext` dataclasses <!-- id: 3 -->
  - [x] Define `ExecutorConfig` with shell_timeout, python_timeout, fetch_timeout, max_file_size, max_fetch_size, allowed_paths, enable_fetch, enable_python_exec
  - [x] Define `ExecutorContext` with session (None for M1), todo_list, config
- [x] Modify `shell.py` — `run_shell` to accept `ExecutorContext` for configurable timeout <!-- id: 3b -->
- [x] Modify `files.py` — `read_file`, `write_file`, `edit_file`, `list_files` to use `ExecutorContext` for max_file_size, allowed_paths <!-- id: 3c -->
- [x] Modify `web.py` — `fetch_url` to use `ExecutorContext` for fetch_timeout, max_fetch_size, enable_fetch <!-- id: 3d -->
- [x] Modify `python_exec.py` — `run_python` to use `ExecutorContext` for python_timeout, enable_python_exec <!-- id: 3e -->
- [x] Update `tinycua/agent/tools/__init__.py` with native tool exports <!-- id: 3f -->

### Phase 2 — TodoList Tool

- [x] Create `tinycua/agent/tools/todo/` package <!-- id: 4 -->
  - [x] Create `tinycua/agent/tools/todo/__init__.py` with re-exports
  - [x] Implement `todo_list.py` — `@tool`-decorated `todo_list` function with command routing (add/list/update/clear)
  - [x] Implement `TodoList` class as in-memory list with add/list/update/clear methods
  - [x] Update `tinycua/agent/tools/__init__.py` with todo tool export

### Phase 3 — Context Integration & register_all()

- [x] Implement `register_all()` in `tinycua/agent/tools/__init__.py` <!-- id: 5 -->
  - [x] Factory functions for each native tool that bind `ExecutorContext`
  - [x] Optional context parameter (default: creates new `ExecutorContext` on first call)
  - [x] Return all 8 tools (7 native + 1 todo)
- [x] Update native tools to optionally accept context via factory wrappers (backward-compatible) <!-- id: 6 -->
  - [x] `shell.py` — use context for `shell_timeout`
  - [x] `files.py` — use context for `max_file_size`, `allowed_paths`
  - [x] `web.py` — use context for `fetch_timeout`, `max_fetch_size`, `enable_fetch`
  - [x] `python_exec.py` — use context for `python_timeout`, `enable_python_exec`

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 10 -->
- [x] Run unit tests for all new components <!-- id: 11 -->
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 12 -->

## Verification Phase

- [x] Verify all 7 native tools are importable and callable directly <!-- id: 13 -->
- [x] Verify `todo_list` works through SDK `ToolExecutor` <!-- id: 14 -->
- [x] Verify `register_all()` returns all 8 tools <!-- id: 15 -->

## Documentation Phase

- [x] Update `tinycua/docs/` if applicable — N/A: no structural docs changes needed for this feature <!-- id: 16 -->
- [x] Update `CHANGELOG.md` or release notes — N/A: changelog not yet established for prototype <!-- id: 17 -->

## Review and Merge

- [x] Create pull request for `feat/m1-basic-tools` (PR #82) <!-- id: 18 -->
- [ ] Address review feedback <!-- id: 19 -->
- [ ] Merge to `feat/tinycua-prototype` branch <!-- id: 20 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-02*
