# Tasks: Native Benchmark Tools

Implementation tasks for Native Benchmark Tools. Check off items as completed.

## TDD Phase (Tests First)

### Integration Tests (No LLM Required)

- [ ] Write integration tests for `run_shell` in `tests/integration/test_native_tools_shell.py` <!-- id: 0 -->
- [ ] Write integration tests for `read_file`, `write_file`, `list_files` in `tests/integration/test_native_tools_files.py` <!-- id: 1 -->
- [ ] Write integration tests for `fetch_url` in `tests/integration/test_native_tools_web.py` <!-- id: 2 -->
- [ ] Write integration tests for `run_python` in `tests/integration/test_native_tools_python.py` <!-- id: 3 -->
- [ ] Write SDK integration tests in `tests/integration/test_native_tools_sdk.py` <!-- id: 4 -->
- [ ] Run integration tests — expect RED (all failures) since no implementation yet <!-- id: 5 -->

### E2E Integration Tests (Live LLM Required)

- [ ] Write e2e Agent tests in `tests/integration/test_native_tools_e2e.py` <!-- id: 6 -->
  - [ ] `test_agent_reads_file_and_writes_result` — read → run_python → write pipeline
  - [ ] `test_agent_lists_and_reads_files` — list_files → read_file exploration
  - [ ] `test_agent_calls_run_shell` — run_shell command execution
- [ ] Run e2e integration tests — expect RED (import errors) since no implementation yet <!-- id: 7 -->

## Implementation Phase

### Test Infrastructure (Env Config)

- [ ] Create `.env.test.example` with LLM provider env vars (matching tinycua-sdk pattern) <!-- id: 8 -->
  - [ ] Set `OPENAI_CHAT_COMPLETIONS_BASE_URL=http://localhost:1234/v1`
  - [ ] Set `OPENAI_CHAT_COMPLETIONS_API_KEY=dummy`
  - [ ] Set `OPENAI_CHAT_COMPLETIONS_MODEL=qwen/qwen3.5-9b`
  - [ ] Add `LLM_BASE_URL` and `LLM_MODEL` as fallback vars
- [ ] Update `.env.example` to include LLM provider vars alongside existing tinycua config <!-- id: 9 -->
  - [ ] Add `LLM_MODEL` and `LLM_BASE_URL` as uncommented defaults
  - [ ] Add commented-out `OPENAI_CHAT_COMPLETIONS_*` override section
  - [ ] Deprecate legacy `TINYCUA_PROVIDER`/`TINYCUA_MODEL`/`TINYCUA_BASE_URL` with comments
- [ ] Update `pyproject.toml` with test deps and pytest config <!-- id: 10 -->
  - [ ] Add `python-dotenv>=1.0.0` to core dependencies
  - [ ] Add `pytest-cov>=4.1.0` and `pytest-httpx>=0.30.0` to dev dependencies
  - [ ] Add pytest markers (`integration`, `lm_studio`) and filterwarnings
- [ ] Create `tests/integration/conftest.py` with LLM config resolver and server probe <!-- id: 11 -->
  - [ ] Load `.env.test` or `.env.test.example` automatically via `python-dotenv`
  - [ ] Implement `resolve_integration_llm_config()` following SDK pattern
  - [ ] Implement `_probe_server()` to check LLM reachability
  - [ ] Auto-skip `@pytest.mark.integration` tests when server is unreachable

### Package Structure

- [ ] Create `tinycua/agent/tools/native/` package with `__init__.py` re-exporting all tool functions <!-- id: 12 -->
  - [ ] Create `tinycua/agent/tools/native/__init__.py`
  - [ ] Update `tinycua/agent/tools/__init__.py` to export all six tools

### Shell Tools

- [ ] Implement `run_shell` in `shell.py` <!-- id: 13 -->
  - [ ] Execute commands via `subprocess.Popen` + `threading.Timer` for timeout
  - [ ] Capture stdout and stderr separately
  - [ ] Return `{stdout, stderr, exit_code, timed_out, error}`
  - [ ] Handle invalid commands gracefully (exit_code != 0, error msg in stderr)
  - [ ] Handle timeout: kill process, set timed_out=True, exit_code=-1

### File Tools

- [ ] Implement `read_file` in `files.py` <!-- id: 14 -->
  - [ ] Resolve path: absolute if starts with `/`, else relative to `os.getcwd()`
  - [ ] Full-file mode (start=None, offset=None): read entire file, truncate at internal 100KB limit
  - [ ] Truncation message: `[Truncated: N lines remaining, ~X bytes not shown]`
  - [ ] Range mode (start and/or offset set): read specified line range, no truncation
  - [ ] Handle file not found, permission denied, invalid start line as error dicts
  - [ ] Handle empty files (return empty string)
- [ ] Implement `write_file` in `files.py` <!-- id: 15 -->
  - [ ] Resolve path: absolute if starts with `/`, else relative to `os.getcwd()`
  - [ ] Create/overwrite mode (start=None): write content, create parent dirs if needed
  - [ ] Patch mode (start set): read existing file, replace lines start..start+offset, write back
  - [ ] Return `{success, path, bytes_written, mode, start_line, lines_replaced, error}`
  - [ ] Handle partial replace on nonexistent file, invalid start line as error dicts
- [ ] Implement `list_files` in `files.py` <!-- id: 16 -->
  - [ ] Resolve path: absolute if starts with `/`, else relative to `os.getcwd()`
  - [ ] Use `pathlib.Path.glob()` for pattern matching
  - [ ] Return list of absolute paths as strings
  - [ ] Handle directory not found, permission denied as error dicts
  - [ ] Handle empty directories (return empty list)

### Web Tools

- [ ] Implement `fetch_url` in `web.py` <!-- id: 17 -->
  - [ ] Use `httpx` for HTTP requests
  - [ ] Support GET (default), POST, and other methods via `method` parameter
  - [ ] Support custom headers via `headers` parameter (dict or None)
  - [ ] Truncate response body at `max_size` bytes with `[truncated at N KB]` indicator
  - [ ] Handle HTTP errors (4xx/5xx) as error dicts
  - [ ] Handle timeout as error dict
  - [ ] Handle invalid URL as error dict

### Python Execution Tools

- [ ] Implement `run_python` in `python_exec.py` <!-- id: 18 -->
  - [ ] Execute code via `subprocess.run(["python", "-c", code], timeout=timeout, capture_output=True, text=True)`
  - [ ] Handle `subprocess.TimeoutExpired` → kill process, set timed_out=True, exit_code=-1
  - [ ] Handle syntax/runtime errors → stderr contains traceback, exit_code=1
  - [ ] Handle empty code (return success with empty stdout/stderr)

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 19 -->
- [ ] Run e2e integration tests — expect GREEN (all pass with live LLM) <!-- id: 20 -->
- [ ] Write unit tests for `shell.py` — mock subprocess for edge cases (empty command, large output) <!-- id: 21 -->
- [ ] Write unit tests for `files.py` — test truncation logic, path resolution, line counting edge cases <!-- id: 22 -->
- [ ] Write unit tests for `web.py` — mock httpx for all HTTP error codes, timeout, invalid URLs <!-- id: 23 -->
- [ ] Write unit tests for `python_exec.py` — mock subprocess for timeout, syntax error, runtime error <!-- id: 24 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` — all tests must pass <!-- id: 25 -->

## Verification Phase

- [ ] Import all six tools from `tinycua.agent.tools` and verify `Tool` instances <!-- id: 26 -->
- [ ] Manually test `run_shell("echo hello")` — verify stdout capture <!-- id: 27 -->
- [ ] Manually test `read_file` with a temp file — full read, range read, relative path <!-- id: 28 -->
- [ ] Manually test `write_file` — create, overwrite, patch, parent dir creation <!-- id: 29 -->
- [ ] Manually test `fetch_url("https://httpbin.org/get")` — verify response body <!-- id: 30 -->
- [ ] Manually test `run_python("print(1+1)")` — verify stdout capture <!-- id: 31 -->
- [ ] Verify tool JSON Schema output matches expected function-calling format <!-- id: 32 -->
- [ ] Run e2e tests with live LLM — verify Agent calls correct native tools for multi-step tasks <!-- id: 33 -->

## Documentation Phase

- [ ] Update `tinycua/agent/tools/__init__.py` docstring with usage examples <!-- id: 34 -->
- [ ] Add module-level docstrings to each tool module explaining purpose and usage <!-- id: 35 -->
- [ ] Update CHANGELOG with new native tools addition <!-- id: 36 -->

## Review and Merge

- [ ] Create pull request using `.agents/scripts/gh.py` with PR body from template <!-- id: 37 -->
- [ ] Address review feedback and run `/review-loop` <!-- id: 38 -->
- [ ] Merge to main branch <!-- id: 39 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-30*
