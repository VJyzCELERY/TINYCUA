# Design Document: Native Benchmark Tools

**Spec**: `./spec.md`
**Status**: In Progress
**Last Updated**: 2026-05-30

---

## Overview

Implement six native tools as `tinycua_sdk` `@tool`-decorated functions in the `src/tinycua/tinycua/agent/tools/` package. These tools give the Task Executor agent the ability to interact with the environment: execute shell commands, read/write/list files, fetch URLs, and run Python code. They are the execution-layer tools in the TINYCUA architecture.

---

## Architecture

### Component Overview

```
tinycua/tinycua/agent/tools/
├── __init__.py          # Public exports (all tool functions)
└── native/
    ├── __init__.py      # Re-exports from individual modules
    ├── shell.py         # run_shell
    ├── files.py         # read_file, write_file, list_files
    ├── web.py           # fetch_url
    └── python_exec.py   # run_python
```

All tools are decorated with `@tool` from `tinycua_sdk`. The `native/` subpackage keeps tools organized by category. The top-level `tools/__init__.py` re-exports everything for convenient `from tinycua.agent.tools import run_shell, read_file, ...` access.

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/agent/tools/__init__.py` | New/Modified | Public exports |
| `tinycua/agent/tools/native/` | New | Tool modules |
| `tinycua/agent/tools/cua/` | Existing | Unchanged — separate concern |

---

## Data Model

### Tool Result Shapes

Each tool returns a structured result:

#### `run_shell`
```python
{
    "stdout": str,       # captured stdout
    "stderr": str,       # captured stderr
    "exit_code": int,    # process exit code (0 = success)
    "timed_out": bool,   # True if timeout killed the process
    "error": str | None, # error message if execution failed
}
```

#### `read_file`
```python
# Returns file contents as string.
# On error: {"error": "File not found: /path/to/file"}
# If truncated: "<content>...\n[truncated at 100KB]"
```

#### `write_file`
```python
{
    "success": bool,
    "path": str,
    "bytes_written": int,
    "error": str | None,
}
```

#### `list_files`
```python
# Returns list of matching paths.
# On error: {"error": "Directory not found: /path/to/dir"}
# ["file1.txt", "subdir/file2.py", ...]
```

#### `fetch_url`
```python
# Returns response body as string.
# On error: {"error": "HTTP 404: Not Found"}
# If truncated: "<content>...\n[truncated at 100KB]"
```

#### `run_python`
```python
{
    "stdout": str,
    "stderr": str,
    "exit_code": int,
    "timed_out": bool,
    "error": str | None,
}
```

---

## API / Interface Contracts

### Tool Signatures

```python
@tool
def run_shell(command: str, timeout: int = 30) -> dict:
    """Execute a shell command and return stdout, stderr, and exit code.
    
    Args:
        command: The shell command to execute.
        timeout: Maximum execution time in seconds.
    """

@tool
def read_file(path: str, max_size: int = 102400) -> str | dict:
    """Read the contents of a file.
    
    Args:
        path: Path to the file.
        max_size: Maximum bytes to read before truncating.
    """

@tool
def write_file(path: str, content: str) -> dict:
    """Write content to a file, creating parent directories if needed.
    
    Args:
        path: Path to the file.
        content: Content to write.
    """

@tool
def list_files(path: str, pattern: str = "*") -> list[str] | dict:
    """List files in a directory matching a glob pattern.
    
    Args:
        path: Directory path.
        pattern: Glob pattern to match (e.g., "*.py", "**/*.txt").
    """

@tool
def fetch_url(url: str, method: str = "GET", headers: dict | None = None, 
              timeout: int = 30, max_size: int = 102400) -> str | dict:
    """Fetch content from a URL.
    
    Args:
        url: The URL to fetch.
        method: HTTP method (GET, POST, etc.).
        headers: Optional HTTP headers.
        timeout: Request timeout in seconds.
        max_size: Maximum bytes to read before truncating.
    """

@tool
def run_python(code: str, timeout: int = 30) -> dict:
    """Execute Python code in a subprocess and return stdout, stderr, and exit code.
    
    Args:
        code: Python code to execute.
        timeout: Maximum execution time in seconds.
    """
```

### Error Handling

| Error Case | Return Value |
|------------|-------------|
| File not found | `read_file`: `{"error": "File not found: ..."}`; `list_files`: `{"error": "..."}` |
| Directory not found | `list_files`: `{"error": "..."}` |
| Permission denied | `{"error": "Permission denied: ..."}` |
| Command timeout | `{"stdout": "...", "stderr": "...", "exit_code": -1, "timed_out": true}` |
| Python execution error | `{"stdout": "", "stderr": "<traceback>", "exit_code": 1, "timed_out": false}` |
| HTTP error (4xx/5xx) | `{"error": "HTTP 404: Not Found"}` |
| HTTP timeout | `{"error": "Request timed out after 30s"}` |
| Invalid URL | `{"error": "Invalid URL: ..."}` |

All tools catch exceptions internally and return error dicts — no unhandled exceptions propagate to the agent loop.

---

## Implementation Phases

### Phase 1 — All Six Tools

- [ ] Create `tinycua/agent/tools/native/` package
- [ ] Implement `shell.py` — `run_shell` with `subprocess.run`, timeout via `subprocess.Popen` + `Timer`
- [ ] Implement `files.py` — `read_file`, `write_file`, `list_files` using `pathlib` and `glob`
- [ ] Implement `web.py` — `fetch_url` using `httpx` (already a project dependency)
- [ ] Implement `python_exec.py` — `run_python` using `subprocess.run` with timeout
- [ ] Update `tinycua/agent/tools/__init__.py` to export all tools
- [ ] Write unit tests for each tool (happy path + error cases + edge cases)
- [ ] Write integration tests verifying tools work through SDK's `ToolExecutor`

---

## Technical Decisions

1. **Decision**: Use `httpx` for `fetch_url`.
   - **Reason**: Already a declared dependency in `pyproject.toml`. Supports async, timeouts, and all HTTP methods.
   - **Alternatives Considered**: `requests` — simpler but no async support. `aiohttp` — unnecessary dependency.

2. **Decision**: Use `subprocess.Popen` + `threading.Timer` for shell timeouts instead of `subprocess.run(timeout=...)`.
   - **Reason**: `subprocess.run` timeout raises `TimeoutExpired` but doesn't always kill child processes cleanly. `Popen` + `kill()` gives us explicit control.
   - **Alternatives Considered**: `subprocess.run(timeout=N)` — simpler but less reliable for process cleanup.

3. **Decision**: Organize tools in a `native/` subpackage rather than flat files.
   - **Reason**: Keeps tools grouped by category (shell, files, web, python). Easy to add more categories later (e.g., `git/`, `docker/`). The top-level `tools/__init__.py` provides a flat import surface.
   - **Alternatives Considered**: Flat `tools/shell.py`, `tools/files.py` — works but doesn't scale with future tool categories.

4. **Decision**: Return structured dicts for execution tools (`run_shell`, `write_file`, `run_python`) and raw strings for data tools (`read_file`, `fetch_url`, `list_files`).
   - **Reason**: Execution tools need status information (exit code, timed_out). Data tools return the data itself — wrapping in a dict adds indirection the LLM must parse.
   - **Alternatives Considered**: Always return dicts — consistent but adds unnecessary nesting for simple data returns.

5. **Decision**: Default truncation at 100KB for `read_file` and `fetch_url`.
   - **Reason**: Prevents context-window pollution. 100KB is generous enough for any benchmark task file while protecting against accidental large reads.
   - **Alternatives Considered**: 10KB, 1MB — 10KB too restrictive for code files, 1MB risks context bloat.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `run_shell` could execute dangerous commands | Medium | High | Scope: benchmarks run in controlled environments. Future: sandboxing. |
| `run_python` could have infinite loops | Medium | Medium | Configurable timeout (default 30s) enforced by subprocess kill. |
| `fetch_url` could hit internal services | Low | Medium | Only HTTP/HTTPS URLs; no file:// or internal IP ranges in prototype. |
| Large file reads could exhaust memory | Low | Medium | Truncation at 100KB default. Configurable `max_size` parameter. |
