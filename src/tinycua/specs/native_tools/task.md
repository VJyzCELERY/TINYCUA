# Tasks: Native Benchmark Tools

Implementation tasks for Native Benchmark Tools. Check off items as completed.

## TDD Phase (Tests First)

### Integration Tests (No LLM Required)

- [x] Write integration tests for `run_shell` in `tests/integration/test_native_tools_shell.py` <!-- id: 0 -->
- [x] Write integration tests for `read_file`, `write_file`, `list_files` in `tests/integration/test_native_tools_files.py` <!-- id: 1 -->
- [x] Write integration tests for `fetch_url` in `tests/integration/test_native_tools_web.py` <!-- id: 2 -->
- [x] Write integration tests for `run_python` in `tests/integration/test_native_tools_python.py` <!-- id: 3 -->
- [x] Write SDK integration tests in `tests/integration/test_native_tools_sdk.py` <!-- id: 4 -->
- [x] Run integration tests — expect GREEN (all pass) <!-- id: 5 -->

### E2E Integration Tests (Live LLM Required)

- [x] Write e2e Agent tests in `tests/integration/test_native_tools_e2e.py` <!-- id: 6 -->
  - [x] `test_agent_reads_file_and_writes_result` — read → run_python → write pipeline
  - [x] `test_agent_lists_and_reads_files` — list_files → read_file exploration
  - [x] `test_agent_calls_run_shell` — run_shell command execution
- [x] Run e2e integration tests — expect GREEN (all pass with live LLM) <!-- id: 7 -->

## Implementation Phase

### Test Infrastructure (Env Config)

- [x] Create `.env.test.example` with LLM provider env vars (matching tinycua-sdk pattern) <!-- id: 8 -->
  - [x] Set `OPENAI_CHAT_COMPLETIONS_BASE_URL=http://localhost:1234/v1`
  - [x] Set `OPENAI_CHAT_COMPLETIONS_API_KEY=dummy`
  - [x] Set `OPENAI_CHAT_COMPLETIONS_MODEL=qwen/qwen3.5-9b`
  - [x] Add `LLM_BASE_URL` and `LLM_MODEL` as fallback vars
- [x] Update `.env.example` to include LLM provider vars alongside existing tinycua config <!-- id: 9 -->
  - [x] Add `LLM_MODEL` and `LLM_BASE_URL` as uncommented defaults
  - [x] Add commented-out `OPENAI_CHAT_COMPLETIONS_*` override section
  - [x] Deprecate legacy `TINYCUA_PROVIDER`/`TINYCUA_MODEL`/`TINYCUA_BASE_URL` with comments
- [x] Update `pyproject.toml` with test deps and pytest config <!-- id: 10 -->
  - [x] Add `python-dotenv>=1.0.0` to core dependencies
  - [x] Add `pytest-cov>=4.1.0` and `pytest-httpx>=0.30.0` to dev dependencies
  - [x] Add pytest markers (`integration`, `lm_studio`) and filterwarnings
- [x] Create `tests/integration/conftest.py` with LLM config resolver and server probe <!-- id: 11 -->
  - [x] Load `.env.test` or `.env.test.example` automatically via `python-dotenv`
  - [x] Implement `resolve_integration_llm_config()` following SDK pattern
  - [x] Implement `_probe_server()` to check LLM reachability
  - [x] Auto-skip `@pytest.mark.integration` tests when server is unreachable

### Package Structure

- [x] Create `tinycua/agent/tools/native/` package with `__init__.py` re-exporting all tool functions <!-- id: 12 -->
  - [x] Create `tinycua/agent/tools/native/__init__.py`
  - [x] Update `tinycua/agent/tools/__init__.py` to export all six tools

### Shell Tools

- [x] Implement `run_shell` in `shell.py` <!-- id: 13 -->
  - [x] Execute commands via `subprocess.Popen` + `threading.Timer` for timeout
  - [x] Capture stdout and stderr separately
  - [x] Return `{stdout, stderr, exit_code, timed_out, error}`
  - [x] Handle invalid commands gracefully (exit_code != 0, error msg in stderr)
  - [x] Handle timeout: kill process, set timed_out=True, exit_code=-1

### File Tools

- [x] Implement `read_file` in `files.py` <!-- id: 14 -->
  - [x] Resolve path: absolute if starts with `/`, else relative to `os.getcwd()`
  - [x] Full-file mode (start=None, offset=None): read entire file, truncate at internal 100KB limit
  - [x] Truncation message: `[Truncated: N lines remaining, ~X bytes not shown]`
  - [x] Range mode (start and/or offset set): read specified line range, no truncation
  - [x] Handle file not found, permission denied, invalid start line as error dicts
  - [x] Handle empty files (return empty string)
- [x] Implement `write_file` in `files.py` <!-- id: 15 -->
  - [x] Resolve path: absolute if starts with `/`, else relative to `os.getcwd()`
  - [x] Create/overwrite a file only when its parent directory exists
  - [x] Return `{success, path, chars_written, error}`
  - [x] Handle permission denied as error dict
- [x] Implement `edit_file` in `files.py` <!-- id: 16 -->
  - [x] Resolve path: absolute if starts with `/`, else relative to `os.getcwd()`
  - [x] Read existing file, replace lines start..start+offset, write back
  - [x] Return `{success, path, start_line, lines_replaced, bytes_written, error}`
  - [x] Handle file not found, invalid start line as error dicts
  - [x] offset=None replaces to end of file from start
- [x] Implement `list_files` in `files.py` <!-- id: 17 -->
  - [x] Resolve path: absolute if starts with `/`, else relative to `os.getcwd()`
  - [x] Use `pathlib.Path.glob()` for pattern matching
  - [x] Return list of absolute paths as strings
  - [x] Handle directory not found, permission denied as error dicts
  - [x] Handle empty directories (return empty list)

### Web Tools

- [x] Implement `fetch_url` in `web.py` <!-- id: 18 -->
  - [x] Use `httpx` for HTTP requests
  - [x] Support GET (default), POST, and other methods via `method` parameter
  - [x] Support custom headers via `headers` parameter (dict or None)
  - [x] Truncate response body at `max_size` bytes with `[truncated at N KB]` indicator
  - [x] Handle HTTP errors (4xx/5xx) as error dicts
  - [x] Handle timeout as error dict
  - [x] Handle invalid URL as error dict

### Python Execution Tools

- [x] Implement `run_python` in `python_exec.py` <!-- id: 19 -->
  - [x] Execute code via `subprocess.run(["python", "-c", code], timeout=timeout, capture_output=True, text=True)`
  - [x] Handle `subprocess.TimeoutExpired` → kill process, set timed_out=True, exit_code=-1
  - [x] Handle syntax/runtime errors → stderr contains traceback, exit_code=1
  - [x] Handle empty code (return success with empty stdout/stderr)

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass, 44/44) <!-- id: 20 -->
- [x] Run e2e integration tests — expect GREEN (all pass with live LLM) <!-- id: 21 -->
- [x] Write unit tests for `shell.py` — mock subprocess for edge cases (empty command, large output) <!-- id: 22 -->
- [x] Write unit tests for `files.py` — test truncation logic, path resolution, line counting edge cases, edit_file line replacement <!-- id: 23 -->
- [x] Write unit tests for `web.py` — mock httpx for all HTTP error codes, timeout, invalid URLs <!-- id: 24 -->
- [x] Write unit tests for `python_exec.py` — mock subprocess for timeout, syntax error, runtime error <!-- id: 25 -->
- [x] Run full test suite: `cd src/tinycua && uv run pytest` — all tests must pass (71/71) <!-- id: 26 -->

## Verification Phase

- [x] Import all seven tools from `tinycua.agent.tools` and verify `Tool` instances <!-- id: 27 -->
- [x] Manually test `run_shell("echo hello")` — verify stdout capture <!-- id: 28 -->
- [x] Manually test `read_file` with a temp file — full read, range read, relative path <!-- id: 29 -->
- [x] Manually test `write_file` — create, overwrite, missing-parent failure <!-- id: 30 -->
- [x] Manually test `edit_file` — single line, multiple lines, replace to end, relative path <!-- id: 31 -->
- [x] Manually test `fetch_url("https://httpbin.org/get")` — verify response body (via httpx mock) <!-- id: 32 -->
- [x] Manually test `run_python("print(1+1)")` — verify stdout capture <!-- id: 33 -->
- [x] Verify tool JSON Schema output matches expected function-calling format <!-- id: 34 -->
- [x] Run e2e tests with live LLM — verify Agent calls correct native tools for multi-step tasks <!-- id: 35 -->

## Documentation Phase

- [x] Update `tinycua/agent/tools/__init__.py` docstring with usage examples <!-- id: 36 -->
- [x] Add module-level docstrings to each tool module explaining purpose and usage <!-- id: 37 -->
- [ ] Update CHANGELOG with new native tools addition (no CHANGELOG exists yet) <!-- id: 38 -->

## Review and Merge

- [ ] Create pull request using `.agents/scripts/gh.py` with PR body from template <!-- id: 39 -->
- [ ] Address review feedback and run `/review-loop` <!-- id: 40 -->
- [ ] Merge to main branch <!-- id: 41 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-30*
