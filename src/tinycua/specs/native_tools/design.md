# Design Document: Native Benchmark Tools

**Spec**: `./spec.md`
**Status**: In Progress
**Last Updated**: 2026-05-30

---

## Overview

Implement seven native tools as `tinycua_sdk` `@tool`-decorated functions in the `src/tinycua/tinycua/agent/tools/` package. These tools give the Task Executor agent the ability to interact with the environment: execute shell commands, read/write/edit/list files, fetch URLs, and run Python code. They are the execution-layer tools in the TINYCUA architecture.

---

## Architecture

### Component Overview

```
tinycua/tinycua/agent/tools/
├── __init__.py          # Public exports (all tool functions)
└── native/
    ├── __init__.py      # Re-exports from individual modules
    ├── shell.py         # run_shell
    ├── files.py         # read_file, write_file, edit_file, list_files
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
# Full-file mode (start=None, offset=None): reads entire file up to an internal
#   size limit (100KB default). If file exceeds the limit, content is truncated
#   with a summary message.
# Range mode (start and/or offset set): reads exactly the requested line range
#   with no automatic truncation.
#
# On error: {"error": "File not found: /path/to/file"}
# On invalid range: {"error": "Start line 500 exceeds file length (42 lines). Range out of bounds."}
# On range beyond file: {"error": "Start line 40 + offset 20 exceeds file length (42 lines). Range out of bounds."}
# If truncated: "...\n[Truncated: 843 lines remaining, ~48KB not shown]"
```

#### `write_file`
```python
{
    "success": bool,
    "path": str,
    "chars_written": int,
    "error": str | None,
}
```

#### `edit_file`
```python
{
    "success": bool,
    "path": str,
    "start_line": int,       # line where replacement began
    "lines_replaced": int,   # number of lines replaced
    "bytes_written": int,    # total bytes written to file
    "error": str | None,
}
# On error (file not found): {"error": "File not found: /path/to/file"}
# On error (invalid start): {"error": "Start line 500 exceeds file length (42 lines). Range out of bounds."}
# On error (start+offset beyond file): {"error": "Start line 40 + offset 20 exceeds file length (42 lines). Range out of bounds."}
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
def read_file(path: str, start: int | None = None, offset: int | None = None) -> str | dict:
    """Read the contents of a file.
    
    Paths starting with '/' are treated as absolute. All other paths are resolved
    relative to the agent's current working directory (e.g., read_file("file.txt")
    reads ./file.txt).
    
    When start and offset are both None (default), reads the entire file up to an
    internal size limit (100KB). If the file is larger, content is truncated with a
    summary of what remains.
    
    When start and/or offset are set, reads the specified line range without
    automatic truncation — the agent explicitly controls the read window.
    
    Args:
        path: Path to the file (absolute or relative to CWD).
        start: 1-indexed line number to start reading from. None starts from the beginning.
        offset: Number of lines to read. None reads to end of file from start.
    """

@tool
def write_file(path: str, content: str) -> dict:
    """Write content to a file when its parent directory exists.
    
    Paths starting with '/' are treated as absolute. All other paths are resolved
    relative to the agent's current working directory.
    
    If the file already exists, it is overwritten. If it does not exist, the file
    is created. Missing parent directories return a structured error.
    
    Args:
        path: Path to the file (absolute or relative to CWD).
        content: Content to write.
    """

@tool
def edit_file(path: str, start: int, content: str, offset: int | None = None) -> dict:
    """Replace lines in an existing file starting at a given line number.
    
    Paths starting with '/' are treated as absolute. All other paths are resolved
    relative to the agent's current working directory.
    
    Reads the file, replaces lines starting at `start` for `offset` lines (or to
    end of file if offset is None), and writes the result back. The file must
    already exist — use `write_file` to create new files.
    
    Args:
        path: Path to the file (absolute or relative to CWD).
        start: 1-indexed line number to begin replacing at.
        content: Replacement content (may be multiple lines).
        offset: Number of lines to replace starting from `start`. None replaces to end of file.
    """

@tool
def list_files(path: str, pattern: str = "*") -> list[str] | dict:
    """List files in a directory matching a glob pattern.
    
    Paths starting with '/' are treated as absolute. All other paths are resolved
    relative to the agent's current working directory.
    
    Args:
        path: Directory path (absolute or relative to CWD).
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
| File not found | `read_file`: `{"error": "File not found: ..."}`; `list_files`: `{"error": "..."}`; `edit_file`: `{"error": "File not found: ..."}` |
| Directory not found | `list_files`: `{"error": "..."}` |
| Permission denied | `{"error": "Permission denied: ..."}` |
| Invalid start or range | `read_file`: `{"error": "Start line 500 exceeds file length (42 lines). Range out of bounds."}` or `{"error": "Start line 40 + offset 20 exceeds file length (42 lines). Range out of bounds."}`; `edit_file`: same format |
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
- [ ] Implement `files.py` — `read_file` (full-file with truncation + line-range reads), `write_file` (full-file create/overwrite), `edit_file` (partial line replacement), `list_files` using `pathlib` and `glob`
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

5. **Decision**: Internal truncation limit (100KB) for `read_file` full-file reads; bypass when `start` or `offset` is explicitly set.
   - **Reason**: Prevents context-window pollution during accidental full-file reads of large files. When the agent explicitly requests a line range via `start`/`offset`, it is making a deliberate choice and no automatic truncation is applied. The limit is an internal constant, not a tool parameter, to keep the tool interface simple for the LLM.
   - **Alternatives Considered**: `max_size` as a tool parameter — adds parameter complexity that may confuse the agent. Always truncating regardless of `start`/`offset` — prevents the agent from deliberately reading large sections when needed.

6. **Decision**: `read_file` uses 1-indexed line numbers for `start` and `offset` (line count), not character offsets or `[line, col]` tuples.
   - **Reason**: LLMs naturally think in terms of line numbers when reading files. Character offsets require the agent to know exact character positions, which is uncommon. A line-based interface aligns with how most agent tools (e.g., OpenCode's Read tool) present file content to the LLM.
   - **Alternatives Considered**: Character offset — more precise but harder for LLMs to use. `[line, col]` tuples — adds parsing complexity without clear benefit over line numbers alone.

7. **Decision**: Separate `write_file` (create/overwrite entire file) and `edit_file` (partial line replacement via `start`/`offset`) into two distinct tools.
   - **Reason**: Clean separation of concerns matches how most agent tools work (e.g., OpenCode's Write + Edit). `write_file` remains simple and predictable — it always creates or overwrites the entire file. `edit_file` handles targeted line-range replacements on existing files. This avoids the ambiguity of a single tool that behaves differently depending on whether optional parameters are set.
   - **Alternatives Considered**: Single `write_file` with optional `start`/`offset` for partial replacement — simpler tool count but the dual-purpose behavior is harder for the LLM to reason about (the tool either creates or patches depending on parameter presence). Text-based replacement via `oldString`/`newString` — powerful but more complex and error-prone than line-based replacement.

8. **Decision**: File paths are resolved relative to the process CWD; absolute paths (starting with `/`) are used as-is.
   - **Reason**: The agent should not need to discover or construct absolute paths for simple operations like `read_file("file.txt")` or `write_file("output/data.csv")`. Relative-to-CWD is the natural behavior — it matches how shell commands, Python's `open()`, and most tools work. This also reduces token waste from path-finding tool calls.
   - **Alternatives Considered**: Require absolute paths — safer but forces the agent to always know the full tree, which adds friction. Configurable `workspace_dir` — more flexible but adds complexity; CWD is the established convention.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `run_shell` could execute dangerous commands | Medium | High | Scope: benchmarks run in controlled environments. Future: sandboxing. |
| `run_python` could have infinite loops | Medium | Medium | Configurable timeout (default 30s) enforced by subprocess kill. |
| `fetch_url` could hit internal services | Low | Medium | Only HTTP/HTTPS URLs; no file:// or internal IP ranges in prototype. |
| Large file reads could exhaust memory | Low | Medium | Internal truncation at 100KB for full-file reads. Agent bypasses limit by setting `start`/`offset`. |
| `edit_file` could corrupt file on partial write | Low | Low | File is read first, lines replaced in memory, then written atomically. Validation of `start`/`offset` before replacement. |
