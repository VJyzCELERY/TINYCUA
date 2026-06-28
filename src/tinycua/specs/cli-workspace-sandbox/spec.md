# Feature Specification: CLI Workspace Sandboxing

**Status**: In Progress
**Created**: 2026-06-18
**Last Updated**: 2026-06-18
**Subproject(s) Affected**: tinycua

---

## Problem Statement

- **Goals**: Fix the `tinycua run` CLI so it actually works (argparse crash), and ensure that workspace operations never mutate or destabilize the process's current working directory or other terminal sessions.
- **Gaps**:
  1. `tinycua run "hello" --dir ./tmp` crashes at argparse because the `run` subparser in `main.py` has no arguments defined — `parser.parse_args()` rejects `"hello" --dir ./tmp` as unrecognized arguments before `run_command` is ever reached.
  2. `benchmark.py` uses `os.chdir(workspace)` which mutates the process CWD, breaking relative path resolution for everything else in the process.
  3. `run_shell` executes shell commands with `cwd=str(workspace)` but `shell=True` gives the LLM unrestricted shell access inside the workspace directory, which can delete the workspace itself or escape it.
  4. `ContextVar` workspace binding (`_WORKSPACE_DIR`) doesn't propagate across `ThreadPoolExecutor` threads used by `_run_async_safely`, causing tools to fall back to CWD-relative behavior.
  5. The test conftest already works around `FileNotFoundError` from `Path.cwd()`, confirming the CWD-disappearing bug has been hit before.
- **Non-Goals**: Adding shell command sandboxing/filtering (LLM can delete workspace files — that's expected). Adding new features. Changing the `smoke-run` subcommand.
- **Constraints**: Must keep `--dir` defaulting to CWD (user wants workspace = current directory). Must not break existing test suite. `benchmark.py` is deprecated, not removed (keep the file but mark it).

---

## User Scenarios & Testing

### Primary Scenario

User runs `cd /some/project && tinycua run "list files" --dir ./tmp` and:
1. The CLI actually parses and executes (no argparse crash).
2. The workspace `./tmp` is used for all tool operations.
3. The user's terminal CWD (`/some/project`) is unaffected — other terminal sessions in `/some/project` continue working.
4. If `--dir` is omitted, CWD is used as workspace without mutating `os.getcwd()`.

### Acceptance Scenarios

1. **Given** a directory `/some/project`, **When** `tinycua run "hello" --dir ./tmp`, **Then** the CLI parses args correctly and invokes `run_command`.
2. **Given** no `--dir` flag, **When** `tinycua run "hello"`, **Then** workspace resolves to CWD without `os.chdir()`.
3. **Given** a running agent with workspace `/some/project/tmp`, **When** `run_shell` executes a command, **Then** it uses `cwd=/some/project/tmp` in the subprocess (not `os.chdir`).
4. **Given** a running agent with workspace bound, **When** `write_file("hello.txt", "hi")` is called, **Then** the file is created inside the workspace.
5. **Given** the agent is running, **When** any tool or subprocess finishes, **Then** the process CWD is unchanged.

### Edge Cases

- What happens when `--dir ./tmp` and `./tmp` doesn't exist? → It should be created.
- What happens when CWD is deleted externally while agent runs? → Agent should still work (workspace was resolved to absolute path at start).
- What happens when `ContextVar` is accessed from a ThreadPoolExecutor thread? → It should still see the workspace.

---

## Requirements

### Functional Requirements

- **FR-001**: `tinycua run` subcommand MUST parse all its arguments (prompt, --dir, --model, etc.) correctly via argparse.
- **FR-002**: The CLI MUST NOT call `os.chdir()` anywhere in the `run` command path.
- **FR-003**: `run_shell` MUST set `cwd=<workspace>` on subprocess calls, not rely on process CWD.
- **FR-004**: `run_python` MUST set `cwd=<workspace>` on subprocess calls.
- **FR-005**: `resolve_workspace_path` MUST use the bound workspace (not CWD) when workspace is set.
- **FR-006**: `ContextVar` workspace binding MUST propagate correctly into async/threaded execution contexts.
- **FR-007**: `benchmark.py` MUST be marked as deprecated (no `os.chdir` fix needed — it's being deprecated).
- **FR-008**: The `--dir` default MUST remain `Path.cwd()` but MUST be resolved to absolute immediately.

---

## Success Criteria

- [ ] **`tinycua run "hello" --dir ./tmp` parses and executes**: No argparse crash.
- [ ] **No `os.chdir()` in run path**: Process CWD is never mutated.
- [ ] **Other terminals unaffected**: Running tinycua doesn't break other shell sessions.
- [ ] **ContextVar propagates to async threads**: Workspace is bound correctly.
- [ ] **Existing tests pass**: `cd src/tinycua && uv run pytest` green.

---

## Testing Plan

### Unit Tests

- Test `main.py` dispatch with `run` subcommand args
- Test `resolve_workspace_path` with bound workspace vs None
- Test `run_shell` passes `cwd` to subprocess
- Test `run_python` passes `cwd` to subprocess

### Integration Tests

- Run `tinycua run` with a local LLM and verify workspace isolation
- Verify CWD is unchanged after a run

### Manual Tests

- `cd /some/dir && uv run tinycua run "hello" --dir ./tmp` works
- Check `pwd` in another terminal before and after — unchanged