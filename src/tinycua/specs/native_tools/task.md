# Tasks: Native Benchmark Tools

Implementation tasks for Native Benchmark Tools. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for `run_shell` in `tests/integration/test_native_tools_shell.py` <!-- id: 0 -->
- [ ] Write integration tests for `read_file`, `write_file`, `list_files` in `tests/integration/test_native_tools_files.py` <!-- id: 1 -->
- [ ] Write integration tests for `fetch_url` in `tests/integration/test_native_tools_web.py` <!-- id: 2 -->
- [ ] Write integration tests for `run_python` in `tests/integration/test_native_tools_python.py` <!-- id: 3 -->
- [ ] Write SDK integration tests in `tests/integration/test_native_tools_sdk.py` <!-- id: 4 -->
- [ ] Run integration tests — expect RED (all failures) since no implementation yet <!-- id: 5 -->

## Implementation Phase

### Package Structure

- [ ] Create `tinycua/agent/tools/native/` package with `__init__.py` re-exporting all tool functions <!-- id: 6 -->
  - [ ] Create `tinycua/agent/tools/native/__init__.py`
  - [ ] Update `tinycua/agent/tools/__init__.py` to export all six tools

### Shell Tools

- [ ] Implement `run_shell` in `shell.py` <!-- id: 7 -->
  - [ ] Execute commands via `subprocess.Popen` + `threading.Timer` for timeout
  - [ ] Capture stdout and stderr separately
  - [ ] Return `{stdout, stderr, exit_code, timed_out, error}`
  - [ ] Handle invalid commands gracefully (exit_code != 0, error msg in stderr)
  - [ ] Handle timeout: kill process, set timed_out=True, exit_code=-1

### File Tools

- [ ] Implement `read_file` in `files.py` <!-- id: 8 -->
  - [ ] Resolve path: absolute if starts with `/`, else relative to `os.getcwd()`
  - [ ] Full-file mode (start=None, offset=None): read entire file, truncate at internal 100KB limit
  - [ ] Truncation message: `[Truncated: N lines remaining, ~X bytes not shown]`
  - [ ] Range mode (start and/or offset set): read specified line range, no truncation
  - [ ] Handle file not found, permission denied, invalid start line as error dicts
  - [ ] Handle empty files (return empty string)
- [ ] Implement `write_file` in `files.py` <!-- id: 9 -->
  - [ ] Resolve path: absolute if starts with `/`, else relative to `os.getcwd()`
  - [ ] Create/overwrite mode (start=None): write content, create parent dirs if needed
  - [ ] Patch mode (start set): read existing file, replace lines start..start+offset, write back
  - [ ] Return `{success, path, bytes_written, mode, start_line, lines_replaced, error}`
  - [ ] Handle partial replace on nonexistent file, invalid start line as error dicts
- [ ] Implement `list_files` in `files.py` <!-- id: 10 -->
  - [ ] Resolve path: absolute if starts with `/`, else relative to `os.getcwd()`
  - [ ] Use `pathlib.Path.glob()` for pattern matching
  - [ ] Return list of absolute paths as strings
  - [ ] Handle directory not found, permission denied as error dicts
  - [ ] Handle empty directories (return empty list)

### Web Tools

- [ ] Implement `fetch_url` in `web.py` <!-- id: 11 -->
  - [ ] Use `httpx` for HTTP requests
  - [ ] Support GET (default), POST, and other methods via `method` parameter
  - [ ] Support custom headers via `headers` parameter (dict or None)
  - [ ] Truncate response body at `max_size` bytes with `[truncated at N KB]` indicator
  - [ ] Handle HTTP errors (4xx/5xx) as error dicts
  - [ ] Handle timeout as error dict
  - [ ] Handle invalid URL as error dict

### Python Execution Tools

- [ ] Implement `run_python` in `python_exec.py` <!-- id: 12 -->
  - [ ] Execute code via `subprocess.run(["python", "-c", code], timeout=timeout, capture_output=True, text=True)`
  - [ ] Handle `subprocess.TimeoutExpired` → kill process, set timed_out=True, exit_code=-1
  - [ ] Handle syntax/runtime errors → stderr contains traceback, exit_code=1
  - [ ] Handle empty code (return success with empty stdout/stderr)

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 13 -->
- [ ] Write unit tests for `shell.py` — mock subprocess for edge cases (empty command, large output) <!-- id: 14 -->
- [ ] Write unit tests for `files.py` — test truncation logic, path resolution, line counting edge cases <!-- id: 15 -->
- [ ] Write unit tests for `web.py` — mock httpx for all HTTP error codes, timeout, invalid URLs <!-- id: 16 -->
- [ ] Write unit tests for `python_exec.py` — mock subprocess for timeout, syntax error, runtime error <!-- id: 17 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` — all tests must pass <!-- id: 18 -->

## Verification Phase

- [ ] Import all six tools from `tinycua.agent.tools` and verify `Tool` instances <!-- id: 19 -->
- [ ] Manually test `run_shell("echo hello")` — verify stdout capture <!-- id: 20 -->
- [ ] Manually test `read_file` with a temp file — full read, range read, relative path <!-- id: 21 -->
- [ ] Manually test `write_file` — create, overwrite, patch, parent dir creation <!-- id: 22 -->
- [ ] Manually test `fetch_url("https://httpbin.org/get")` — verify response body <!-- id: 23 -->
- [ ] Manually test `run_python("print(1+1)")` — verify stdout capture <!-- id: 24 -->
- [ ] Verify tool JSON Schema output matches expected function-calling format <!-- id: 25 -->

## Documentation Phase

- [ ] Update `tinycua/agent/tools/__init__.py` docstring with usage examples <!-- id: 26 -->
- [ ] Add module-level docstrings to each tool module explaining purpose and usage <!-- id: 27 -->
- [ ] Update CHANGELOG with new native tools addition <!-- id: 28 -->

## Review and Merge

- [ ] Create pull request using `.agents/scripts/gh.py` with PR body from template <!-- id: 29 -->
- [ ] Address review feedback and run `/review-loop` <!-- id: 30 -->
- [ ] Merge to main branch <!-- id: 31 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-30*
