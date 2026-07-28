# Implementation: Native Benchmark Tools

Implement seven native tools (`run_shell`, `read_file`, `write_file`, `edit_file`, `list_files`, `fetch_url`, `run_python`) as `@tool`-decorated functions in `tinycua/agent/tools/native/`. These tools provide the Task Executor agent with environment interaction capabilities: shell execution, file I/O (read/write/edit/list), web fetching, and Python code execution. All tools return structured, JSON-serializable output and handle errors gracefully.

## Context

- **Spec Reference**: [spec.md](./spec.md)
- **Design Reference**: [design.md](./design.md)
- **Priority**: P0
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [ ] **`.env.example`** must be updated to include LLM provider env vars (see Proposed Changes)
- [ ] **`.env.test.example`** must be created for integration test LLM config (see Proposed Changes)
- [ ] **`.env.test`** (gitignored) is created by the developer — copy from `.env.test.example` and customize

### Running Services

- [ ] **LLM server** (required for e2e integration tests): an OpenAI-compatible server at the URL configured in `.env.test`. Default: `http://localhost:1234/v1`

### Data / Fixtures

- [ ] **None** — no data or fixtures needed

### Access / Permissions

- [ ] **None** — tools run with the process's filesystem and network permissions

### Developer Tooling

- [ ] **Runtime**: Python 3.11+
- [ ] **Package manager**: uv
- [ ] **httpx** already declared in `pyproject.toml` (for `fetch_url`)

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: tests/integration/test_native_tools_shell.py
"""Integration tests for run_shell."""


def test_run_shell_echo():
    """Run a simple echo command and verify stdout, stderr, exit_code."""
    from tinycua.agent.tools.native.shell import run_shell

    result = run_shell("echo hello")
    assert result["stdout"].strip() == "hello"
    assert result["stderr"] == ""
    assert result["exit_code"] == 0
    assert result["timed_out"] is False
    assert result["error"] is None


def test_run_shell_invalid_command():
    """Verify error handling for a nonexistent command."""
    result = run_shell("nonexistent_command_xyz")
    assert result["exit_code"] != 0
    assert result["stderr"] != "" or result["error"] is not None


def test_run_shell_timeout():
    """Verify timeout kills a long-running process."""
    result = run_shell("sleep 60", timeout=1)
    assert result["timed_out"] is True
    assert result["exit_code"] == -1
    # stdout may contain partial output or be empty
```

```python
# Test file: tests/integration/test_native_tools_files.py
"""Integration tests for read_file, write_file, list_files."""

import tempfile
import os
from pathlib import Path


# --- read_file ---

def test_read_file_full():
    """Read entire file when start and offset are not set."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\nline 3\n")
        path = f.name
    try:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(path)
        assert result == "line 1\nline 2\nline 3\n"
    finally:
        os.unlink(path)


def test_read_file_start_only():
    """Read from start line to end of file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\nline 3\nline 4\n")
        path = f.name
    try:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(path, start=2)
        assert result == "line 2\nline 3\nline 4\n"
    finally:
        os.unlink(path)


def test_read_file_start_and_offset():
    """Read exactly offset lines from start."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\nline 3\nline 4\n")
        path = f.name
    try:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(path, start=2, offset=2)
        assert result == "line 2\nline 3\n"
    finally:
        os.unlink(path)


def test_read_file_start_plus_offset_exceeds_file():
    """Error when start+offset exceeds file line count."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("line 1\nline 2\nline 3\n")
        path = f.name
    try:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(path, start=2, offset=5)
        assert isinstance(result, dict)
        assert "error" in result
        assert "exceeds" in result["error"].lower()
    finally:
        os.unlink(path)


def test_read_file_truncation():
    """Full-file read truncates when file exceeds internal limit."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        # Write ~150KB to exceed 100KB limit
        f.write("x" * 150 * 1024)
        path = f.name
    try:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(path)
        assert "[Truncated:" in result
    finally:
        os.unlink(path)


def test_read_file_range_no_truncation():
    """Range reads bypass truncation limit entirely."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("x" * 150 * 1024)
        path = f.name
    try:
        from tinycua.agent.tools.native.files import read_file

        # Read first 5 lines — should NOT be truncated even though file > 100KB
        result = read_file(path, start=1, offset=5)
        assert "[Truncated:" not in result
    finally:
        os.unlink(path)


def test_read_file_not_found():
    """Error dict returned for missing file."""
    from tinycua.agent.tools.native.files import read_file

    result = read_file("/nonexistent/path/file.txt")
    assert isinstance(result, dict)
    assert "error" in result
    assert "not found" in result["error"].lower()


def test_read_file_invalid_start_line():
    """Error dict returned when start exceeds file length."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("only one line\n")
        path = f.name
    try:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(path, start=100)
        assert isinstance(result, dict)
        assert "error" in result
        assert "range" in result["error"].lower()
    finally:
        os.unlink(path)


def test_read_file_empty():
    """Read an empty file returns empty string."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        path = f.name  # write nothing
    try:
        from tinycua.agent.tools.native.files import read_file

        result = read_file(path)
        assert result == ""
    finally:
        os.unlink(path)


def test_read_file_relative_path():
    """Relative path is resolved from CWD."""
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            Path("test.txt").write_text("hello world\n")

            from tinycua.agent.tools.native.files import read_file
            result = read_file("test.txt")
            assert result == "hello world\n"
    finally:
        os.chdir(original_cwd)


# --- write_file ---

def test_write_file_create():
    """Create a new file with content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "output.txt")
        from tinycua.agent.tools.native.files import write_file

        result = write_file(filepath, "hello world")
        assert result["success"] is True
        assert result["path"] == filepath
        assert result["chars_written"] == len("hello world")
        assert Path(filepath).read_text() == "hello world"


def test_write_file_overwrite():
    """Overwrite an existing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "existing.txt")
        Path(filepath).write_text("old content")
        from tinycua.agent.tools.native.files import write_file

        result = write_file(filepath, "new content")
        assert result["success"] is True
        assert Path(filepath).read_text() == "new content"


def test_write_file_rejects_missing_parent_dirs():
    """Missing parent directories fail without filesystem changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "deep/nested/dir/output.txt")
        from tinycua.agent.tools.native.files import write_file

        result = write_file(filepath, "deep content")
        assert result["success"] is False
        assert not Path(filepath).parent.exists()


def test_write_file_relative_path():
    """Relative path is resolved from CWD."""
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            from tinycua.agent.tools.native.files import write_file

            result = write_file("relative_output.txt", "hello")
            assert result["success"] is True
            assert Path(tmpdir, "relative_output.txt").read_text() == "hello"
    finally:
        os.chdir(original_cwd)


# --- edit_file ---

def test_edit_file_single_line():
    """Replace a single line at a given start position."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "edit.txt")
        Path(filepath).write_text("line 1\nline 2\nline 3\n")
        from tinycua.agent.tools.native.files import edit_file

        result = edit_file(filepath, start=2, content="REPLACED", offset=1)
        assert result["success"] is True
        assert result["start_line"] == 2
        assert result["lines_replaced"] == 1
        assert Path(filepath).read_text() == "line 1\nREPLACED\nline 3\n"


def test_edit_file_multiple_lines():
    """Replace multiple lines with offset parameter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "edit_multi.txt")
        Path(filepath).write_text("line 1\nline 2\nline 3\nline 4\n")
        from tinycua.agent.tools.native.files import edit_file

        result = edit_file(filepath, start=2, content="A\nB", offset=2)
        assert result["success"] is True
        assert result["lines_replaced"] == 2
        assert Path(filepath).read_text() == "line 1\nA\nB\nline 4\n"


def test_edit_file_to_end():
    """Replace from start to end of file when offset is None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "edit_end.txt")
        Path(filepath).write_text("line 1\nline 2\nline 3\n")
        from tinycua.agent.tools.native.files import edit_file

        result = edit_file(filepath, start=2, content="TAIL")
        assert result["success"] is True
        assert Path(filepath).read_text() == "line 1\nTAIL"


def test_edit_file_nonexistent_file():
    """Error when editing a file that does not exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "does_not_exist.txt")
        from tinycua.agent.tools.native.files import edit_file

        result = edit_file(filepath, start=1, content="content")
        assert result["success"] is False
        assert "error" in result


def test_edit_file_invalid_start_line():
    """Error when start line exceeds file length."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "short.txt")
        Path(filepath).write_text("only one line\n")
        from tinycua.agent.tools.native.files import edit_file

        result = edit_file(filepath, start=100, content="content")
        assert result["success"] is False
        assert "error" in result
        assert "range" in result.get("error", "").lower()


def test_edit_file_start_plus_offset_exceeds_file():
    """Error when start+offset exceeds file line count."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "short_multi.txt")
        # 3 lines: start=2, offset=5 → wants to replace 5 lines but only 2 exist (lines 2-3)
        Path(filepath).write_text("line 1\nline 2\nline 3\n")
        from tinycua.agent.tools.native.files import edit_file

        result = edit_file(filepath, start=2, content="A\nB\nC\nD\nE", offset=5)
        assert result["success"] is False
        assert "error" in result
        assert "exceeds" in result["error"].lower()


# --- list_files ---

def test_list_files_all():
    """List all files in a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "a.txt").touch()
        Path(tmpdir, "b.txt").touch()
        Path(tmpdir, "c.py").touch()
        from tinycua.agent.tools.native.files import list_files

        result = list_files(tmpdir)
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(os.path.join(tmpdir, f) in result for f in ["a.txt", "b.txt", "c.py"])


def test_list_files_with_pattern():
    """Filter files with a glob pattern."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "a.txt").touch()
        Path(tmpdir, "b.txt").touch()
        Path(tmpdir, "c.py").touch()
        from tinycua.agent.tools.native.files import list_files

        result = list_files(tmpdir, "*.py")
        assert len(result) == 1
        assert os.path.join(tmpdir, "c.py") in result


def test_list_files_directory_not_found():
    """Error dict returned for nonexistent directory."""
    from tinycua.agent.tools.native.files import list_files

    result = list_files("/nonexistent/path")
    assert isinstance(result, dict)
    assert "error" in result


def test_list_files_empty_directory():
    """Empty directory returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from tinycua.agent.tools.native.files import list_files

        result = list_files(tmpdir)
        assert result == []


def test_list_files_relative_path():
    """Relative path is resolved from CWD."""
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            Path("subdir").mkdir()
            Path("subdir", "file.txt").touch()
            from tinycua.agent.tools.native.files import list_files

            result = list_files("subdir")
            assert len(result) == 1
    finally:
        os.chdir(original_cwd)
```

```python
# Test file: tests/integration/test_native_tools_web.py
"""Integration tests for fetch_url."""

import pytest


def test_fetch_url_get_success(httpx_mock):
    """Successful GET request returns response body."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/data",
        text="response data",
        status_code=200,
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/data")
    assert result == "response data"


def test_fetch_url_post_with_headers(httpx_mock):
    """POST request with custom headers returns response body."""
    httpx_mock.add_response(
        method="POST",
        url="https://example.com/api",
        text='{"ok": true}',
        status_code=200,
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url(
        "https://example.com/api",
        method="POST",
        headers={"Authorization": "Bearer token"},
    )
    assert result == '{"ok": true}'


def test_fetch_url_http_error(httpx_mock):
    """HTTP 404 returns error dict."""
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/missing",
        status_code=404,
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/missing")
    assert isinstance(result, dict)
    assert "error" in result
    assert "404" in result["error"]


def test_fetch_url_truncation(httpx_mock):
    """Large response is truncated with indicator."""
    large_body = "x" * 150 * 1024  # 150KB
    httpx_mock.add_response(
        method="GET",
        url="https://example.com/large",
        text=large_body,
        status_code=200,
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/large", max_size=102400)
    assert "[truncated" in result.lower()


def test_fetch_url_timeout(httpx_mock):
    """Timeout returns error dict."""
    import httpx

    httpx_mock.add_exception(
        httpx.TimeoutException("timed out"),
        url="https://example.com/slow",
    )
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("https://example.com/slow", timeout=1)
    assert isinstance(result, dict)
    assert "error" in result


def test_fetch_url_invalid_url():
    """Invalid URL returns error dict."""
    from tinycua.agent.tools.native.web import fetch_url

    result = fetch_url("not-a-valid-url")
    assert isinstance(result, dict)
    assert "error" in result
```

```python
# Test file: tests/integration/test_native_tools_python.py
"""Integration tests for run_python."""


def test_run_python_hello():
    """Execute simple print statement and capture stdout."""
    from tinycua.agent.tools.native.python_exec import run_python

    result = run_python("print('hello world')")
    assert result["stdout"].strip() == "hello world"
    assert result["stderr"] == ""
    assert result["exit_code"] == 0
    assert result["timed_out"] is False
    assert result["error"] is None


def test_run_python_syntax_error():
    """Return stderr with traceback for invalid Python code."""
    from tinycua.agent.tools.native.python_exec import run_python

    result = run_python("print(undefined_var")
    assert result["exit_code"] != 0
    assert "error" in result["stderr"].lower() or "syntax" in result["stderr"].lower()


def test_run_python_timeout():
    """Infinite loop is terminated by timeout."""
    from tinycua.agent.tools.native.python_exec import run_python

    result = run_python("while True: pass", timeout=1)
    assert result["timed_out"] is True
    assert result["exit_code"] == -1


def test_run_python_empty_code():
    """Empty code returns success with no output."""
    from tinycua.agent.tools.native.python_exec import run_python

    result = run_python("")
    assert result["stdout"] == ""
    assert result["stderr"] == ""
    assert result["exit_code"] == 0
```

```python
# Test file: tests/integration/test_native_tools_sdk.py
"""Integration tests verifying tools work through the SDK's ToolExecutor and Agent."""

import pytest


def test_tool_registers_with_agent():
    """All seven tools can be registered with an SDK Agent."""
    from tinycua_sdk.tools.decorators import Tool
    from tinycua.agent.tools.native.shell import run_shell
    from tinycua.agent.tools.native.files import read_file, write_file, list_files
    from tinycua.agent.tools.native.web import fetch_url
    from tinycua.agent.tools.native.python_exec import run_python

    tools = [run_shell, read_file, write_file, list_files, fetch_url, run_python]
    for tool_func in tools:
        assert isinstance(tool_func, Tool), f"{tool_func.name} should be a Tool instance"
    assert all(hasattr(t, "name") and hasattr(t, "parameters") for t in tools)


def test_tool_schemas_valid_json_schema():
    """Each tool generates valid JSON Schema for function calling."""
    from tinycua.agent.tools.native.shell import run_shell
    from tinycua.agent.tools.native.files import read_file, write_file

    for tool in [run_shell, read_file, write_file]:
        params = tool.parameters
        assert params["type"] == "object"
        assert "properties" in params
        for prop in params["properties"].values():
            assert "type" in prop


def test_tool_executor_invokes_tool():
    """ToolExecutor.execute() successfully invokes a tool."""
    import tempfile
    import os
    from tinycua_sdk.agent.executor import ToolExecutor
    from tinycua.agent.tools.native.files import write_file

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "executor_test.txt")
        result = ToolExecutor.execute(
            write_file,
            {"path": filepath, "content": "executor test"},
        )
        assert result["success"] is True
        assert os.path.exists(filepath)
```

```python
# Test file: tests/integration/test_native_tools_e2e.py
"""End-to-end integration tests: Agent uses native tools through the SDK loop.

These tests require a live LLM server. Copy .env.test.example to .env.test
and configure your LLM settings. Tests are auto-skipped when no server is reachable.
"""

import os
import tempfile
from pathlib import Path

import pytest
from tinycua_sdk import Agent, LanguageModel
from tests.integration.conftest import resolve_integration_llm_config


def _build_language_model() -> LanguageModel:
    cfg = resolve_integration_llm_config()
    return LanguageModel(
        provider=cfg.provider, model_name=cfg.model,
        base_url=cfg.base_url, api_key=cfg.api_key,
    )


class TestNativeToolsE2E:
    """Agent uses native tools through the full SDK pipeline."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_reads_file_and_writes_result(self):
        """Agent reads numbers.txt, sums with run_python, writes result.txt."""
        from tinycua.agent.tools.native.files import read_file, write_file, list_files
        from tinycua.agent.tools.native.python_exec import run_python

        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                Path("numbers.txt").write_text("10\n10\n10\n10\n10\n")

                agent = Agent(
                    name="e2e-native-tools-agent",
                    instructions=(
                        "You are a helpful assistant with file tools. "
                        "Use read_file, write_file, run_python, and list_files."
                    ),
                    llm_model=_build_language_model(),
                    tools=[read_file, write_file, run_python, list_files],
                )

                response = await agent.run(
                    "Read 'numbers.txt', sum all numbers using Python, "
                    "and write the total to 'result.txt'."
                )

                assert Path("result.txt").exists()
                assert "50" in Path("result.txt").read_text()
                assert isinstance(response, str) and len(response) > 0
            finally:
                os.chdir(original_cwd)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_lists_and_reads_files(self):
        """Agent lists files with list_files then reads relevant ones."""
        from tinycua.agent.tools.native.files import list_files, read_file

        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                Path("data").mkdir()
                Path("data/a.csv").write_text("id,name\n1,Alice\n")
                Path("data/b.csv").write_text("id,name\n2,Bob\n")
                Path("data/readme.txt").write_text("CSV data\n")

                agent = Agent(
                    name="e2e-listing-agent",
                    instructions="Use list_files to explore directories.",
                    llm_model=_build_language_model(),
                    tools=[list_files, read_file],
                )

                response = await agent.run(
                    "List files in 'data' and tell me how many CSV files there are."
                )

                assert isinstance(response, str)
                assert "2" in response
            finally:
                os.chdir(original_cwd)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_calls_run_shell(self):
        """Agent calls run_shell to execute a shell command."""
        from tinycua.agent.tools.native.shell import run_shell

        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                agent = Agent(
                    name="e2e-shell-agent",
                    instructions="Use run_shell to execute commands.",
                    llm_model=_build_language_model(),
                    tools=[run_shell],
                )

                response = await agent.run(
                    "Run 'pwd' and tell me the current directory path."
                )

                assert isinstance(response, str) and len(response) > 0
                assert tmpdir in response
            finally:
                os.chdir(original_cwd)
```

### Key Test Scenarios

- [ ] **Scenario 1 — All tools function**: Each tool executes its primary happy path and returns the expected result shape.
- [ ] **Scenario 2 — Error handling**: Every error case (file not found, timeout, syntax error, HTTP 404, invalid range) returns an error dict, never raises.
- [ ] **Scenario 3 — SDK integration**: Tools register with an SDK Agent, generate valid JSON Schema, and execute through ToolExecutor.
- [ ] **Scenario 4 — E2E Agent loop (read → compute → write)**: Agent uses native tools through the full SDK pipeline with a live LLM. Agent reads a file, runs Python to compute, and writes the result — all tool calls are dispatched by the LLM, not hardcoded.
- [ ] **Scenario 5 — E2E Agent loop (list → read)**: Agent explores a directory with list_files and reads relevant files based on LLM decisions.
- [ ] **Scenario 6 — E2E Agent loop (shell)**: Agent calls run_shell through a live LLM and reports the output correctly.
- [ ] **Edge case — Truncation bypass**: `read_file` with `start`/`offset` set bypasses the internal truncation limit entirely.
- [ ] **Edge case — edit_file partial**: `edit_file` with `start`/`offset` correctly replaces a line range within an existing file. Errors returned for nonexistent file or invalid start line.
- [ ] **Edge case — Range out of bounds**: `read_file` and `edit_file` return an error when `start+offset` exceeds the file's line count, with a message showing the file's total lines. Silently clamping to available lines would hide mistakes.
- [ ] **Edge case — Relative paths**: All file tools resolve relative paths against `os.getcwd()`.

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for each module — test error handling, edge cases, mock external dependencies
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Import all seven tools from `tinycua.agent.tools` and verify they are `Tool` instances
- [ ] Run `run_shell("echo hello")` manually — verify stdout capture
- [ ] Create a temp file, read it with `read_file`, patch it with `write_file(start=N)`, verify result

### Performance Considerations

- [ ] `read_file` full-file reads should not load entire 1GB files into memory — internal truncation guards this
- [ ] `run_shell` timeout enforcement must reliably kill child processes (use `Popen` + `Timer`)

## Proposed Changes

### Package: `tinycua/agent/tools/native/`

#### [NEW] `tinycua/tinycua/agent/tools/native/__init__.py`

- **Description**: Re-export all tool functions from submodules for convenient imports.
- **Dependencies**: `shell`, `files`, `web`, `python_exec` submodules.

#### [NEW] `tinycua/tinycua/agent/tools/native/shell.py`

- **Description**: Implements `run_shell(command, timeout=30)` using `subprocess.Popen` + `threading.Timer` for reliable timeout enforcement. Returns `{stdout, stderr, exit_code, timed_out, error}`.
- **Rationale**: Shell execution is the primary tool for benchmark task automation.

#### [NEW] `tinycua/tinycua/agent/tools/native/files.py`

- **Description**: Implements `read_file(path, start=None, offset=None)`, `write_file(path, content)`, `edit_file(path, start, content, offset=None)`, `list_files(path, pattern="*")`. Uses `pathlib` for path resolution (absolute vs relative-to-CWD). `read_file` applies internal 100KB truncation only for full-file reads (start/offset both None). `write_file` creates or overwrites files only when the parent directory exists. `edit_file` replaces a line range in an existing file using `start`/`offset`. `list_files` uses `pathlib.glob()`.
- **Rationale**: File I/O is essential for any agent that reads data, writes results, and explores directories.

#### [NEW] `tinycua/tinycua/agent/tools/native/web.py`

- **Description**: Implements `fetch_url(url, method="GET", headers=None, timeout=30, max_size=102400)` using `httpx`. Truncates large responses with indicator. Handles HTTP errors (4xx/5xx), timeouts, and invalid URLs as error dicts.
- **Rationale**: Agents need web access for benchmark tasks that involve API calls or data fetching.

#### [NEW] `tinycua/tinycua/agent/tools/native/python_exec.py`

- **Description**: Implements `run_python(code, timeout=30)` using `subprocess.run(["python", "-c", code], timeout=timeout)`. Captures stdout/stderr and returns `{stdout, stderr, exit_code, timed_out, error}`.
- **Rationale**: Python execution enables the agent to perform data computation, transformation, and analysis within benchmarks.

#### [MODIFY] `tinycua/tinycua/agent/tools/__init__.py`

- **Description**: Add imports and re-exports for all seven tool functions: `run_shell`, `read_file`, `write_file`, `edit_file`, `list_files`, `fetch_url`, `run_python`.
- **Rationale**: Provides a flat import surface (`from tinycua.agent.tools import read_file`) for convenience.

### Tests

#### [NEW] `tests/integration/test_native_tools_shell.py`

- **Description**: Integration tests for `run_shell` — echo, invalid command, timeout.

#### [NEW] `tests/integration/test_native_tools_files.py`

- **Description**: Integration tests for `read_file`, `write_file`, `list_files` — full reads, range reads, truncation, create/overwrite/patch, glob filtering, relative paths, all error cases.

#### [NEW] `tests/integration/test_native_tools_web.py`

- **Description**: Integration tests for `fetch_url` — GET, POST with headers, HTTP errors, truncation, timeout, invalid URL. Uses `pytest-httpx` or `httpx_mock` for mocking.

#### [NEW] `tests/integration/test_native_tools_python.py`

- **Description**: Integration tests for `run_python` — print, syntax error, infinite loop timeout, empty code.

#### [NEW] `tests/integration/test_native_tools_sdk.py`

- **Description**: Integration tests verifying all tools work through the SDK's `ToolExecutor` and generate valid JSON Schema for function calling.

#### [NEW] `tests/unit/` — per-tool unit tests

- **Description**: Unit tests for each tool module with mocked external dependencies. Test edge cases: empty file, empty directory, empty URL, empty command/code, permission denied simulation.

#### [NEW] `tests/integration/test_native_tools_e2e.py`

- **Description**: End-to-end integration tests that create a real SDK `Agent` with native tools and run it through the BaseLoop against a live LLM. Tests cover: (1) read → run_python → write pipeline, (2) list_files → read_file exploration, (3) run_shell command execution. Skipped automatically when no LLM server is reachable.

#### [NEW] `tests/integration/conftest.py`

- **Description**: Integration test configuration with LLM server probing. Resolves provider config from environment variables (following the tinycua-sdk pattern), probes server reachability at collection time, and auto-skips integration tests when the server is down. Loads `.env.test` or `.env.test.example` automatically.

### Test Infrastructure

#### [NEW] `.env.test.example`

- **Description**: Template environment file for integration tests. Follows the `src/tinycua-sdk/.env.test.example` pattern. Developers copy this to `.env.test` (gitignored) and customize their LLM endpoint.
- **Content**:
  ```ini
  # Provider-specific env vars for OpenAI Chat Completions (take highest priority)
  OPENAI_CHAT_COMPLETIONS_BASE_URL=http://localhost:1234/v1
  OPENAI_CHAT_COMPLETIONS_API_KEY=dummy
  OPENAI_CHAT_COMPLETIONS_MODEL=qwen/qwen3.5-9b

  # Generic fallback env vars (used when no provider-specific var is set)
  LLM_BASE_URL=http://localhost:1234/v1
  LLM_MODEL=qwen/qwen3.5-9b

  # Backend (not required for native tool tests)
  TINYCUA_BACKEND_URL=http://localhost:8000
  ```

#### [MODIFY] `.env.example`

- **Description**: Update `src/tinycua/.env.example` to include LLM provider environment variables matching the SDK's scheme. Keep existing tinycua-specific vars but add `LLM_MODEL`, `LLM_BASE_URL`, and provider-specific override sections (commented out by default). Deprecate legacy `TINYCUA_PROVIDER`/`TINYCUA_MODEL`/`TINYCUA_BASE_URL` vars.
- **Expected content**:
  ```ini
  # TINYCUA Configuration

  # Backend Configuration
  TINYCUA_BACKEND_URL=http://localhost:8000
  TINYCUA_API_KEY=
  TINYCUA_DATABASE_URL=sqlite:///./tinycua.db
  TINYCUA_ENV=dev

  # Default Model Configuration (fallback for all providers)
  # LLM_BASE_URL and LLM_MODEL are shared fallbacks for all providers.
  LLM_MODEL=qwen/qwen3.5-9b
  LLM_BASE_URL=http://localhost:1234/v1

  # Provider-specific overrides (take precedence over LLM_* env vars)
  # OpenAI Chat Completions provider (chat/completions endpoint)
  # OPENAI_CHAT_COMPLETIONS_BASE_URL=https://api.openai.com/v1
  # OPENAI_CHAT_COMPLETIONS_API_KEY=sk-...
  # OPENAI_CHAT_COMPLETIONS_MODEL=gpt-4o-mini

  # Legacy (deprecated — use LLM_* or provider-specific vars instead)
  # TINYCUA_PROVIDER=openai-compatible
  # TINYCUA_MODEL=qwen/qwen3.5-9b
  # TINYCUA_BASE_URL=http://localhost:1234/v1
  ```

#### [MODIFY] `pyproject.toml`

- **Description**: Add `python-dotenv>=1.0.0` to core dependencies (needed by conftest.py to load `.env.test`). Add `pytest-cov>=4.1.0` and `pytest-httpx>=0.30.0` to dev dependencies. Add pytest markers (`integration`, `lm_studio`) and filterwarnings for httpx resource cleanup in `[tool.pytest.ini_options]`.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/agent/tools/native/` | New | Package with four modules (shell, files, web, python_exec) |
| `tinycua/agent/tools/__init__.py` | Modify | Add re-exports for all seven native tools |
| `tinycua/agent/tools/cua/` | Unchanged | Separate concern — no changes needed |
| `tinycua-sdk` | Unchanged | Tools use existing `@tool` decorator and `ToolExecutor` |
| `tests/` | New | Test suite with integration tests and e2e LLM tests |
| `.env.test.example` | New | LLM config template for integration tests (mirrors SDK pattern) |
| `.env.example` | Modify | Added LLM provider env vars |
| `pyproject.toml` | Modify | Added test deps, markers, filterwarnings |

## Data Model Changes

```python
# No new data models — tools use existing SDK Tool and LLMToolSpec.
# Tool return values follow the shapes defined in design.md:
#   run_shell:    {stdout, stderr, exit_code, timed_out, error}
#   read_file:    str (or dict on error)
#   write_file:   {success, path, chars_written, error}
#   edit_file:    {success, path, start_line, lines_replaced, bytes_written, error}
#   list_files:   list[str] (or dict on error)
#   fetch_url:    str (or dict on error)
#   run_python:   {stdout, stderr, exit_code, timed_out, error}
```

## API Changes

### New Tool Functions

| Name | Module | Purpose |
|------|--------|---------|
| `run_shell` | `shell.py` | Execute shell commands |
| `read_file` | `files.py` | Read file contents with range support |
| `write_file` | `files.py` | Create/overwrite files |
| `edit_file` | `files.py` | Replace lines in existing files |
| `list_files` | `files.py` | List directory contents with glob |
| `fetch_url` | `web.py` | HTTP fetch with truncation |
| `run_python` | `python_exec.py` | Execute Python code in subprocess |

No modified or removed endpoints (this is a library addition, not an API service).

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| httpx | ^0.28 (existing) | HTTP client for `fetch_url` |
| pytest-httpx | latest | Mock HTTP for `fetch_url` tests (dev dependency) |

### Internal Dependencies

- [ ] Depends on `tinycua-sdk` — tools use `@tool` decorator, `ToolExecutor`, `LLMToolSpec` from SDK
- [ ] Blocks no other features — this is a standalone addition

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `run_shell` could execute dangerous commands | High | Scope: benchmarks run in controlled environments. Future: sandboxing. |
| `run_python` infinite loops | Medium | Configurable timeout (default 30s) enforced by subprocess kill. |
| `fetch_url` hitting internal services | Low | Only HTTP/HTTPS URLs; restrict to public endpoints in prototype. |
| Large file reads exhausting memory | Medium | Internal truncation at 100KB for full-file reads. Agent bypasses via `start`/`offset`. |
| Partial `write_file` line mismatch | Low | `start`/`offset` validated against file line count before replacement. Errors returned as dicts. |
| `pathlib` glob inconsistent across platforms | Low | `pathlib.Path.glob()` is platform-independent. Tests run on Linux (CI) and local. |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-30*
