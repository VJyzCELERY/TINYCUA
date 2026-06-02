# Implementation: M1 — Basic Tools

Implement the foundational tool layer for the TINYCUA prototype: native execution tools (shell, file, web, python), a TodoList tool, a digester retrieval tool interface, and tool constants/mappings. All tools are implemented as `tinycua_sdk` `@tool`-decorated functions.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P0
- **Estimated Effort**: XL

## Environment Pre-requisites

### Configuration

- [ ] **None** — this feature has no configuration dependencies

### Running Services

- [ ] **None** — no external services needed

### Data / Fixtures

- [ ] **None** — no data or fixtures needed

### Access / Permissions

- [ ] **None** — no special access required

### Developer Tooling

- [ ] **Runtime**: Python >=3.12
- [ ] **Package manager**: uv
- [ ] **Additional CLI tools**: none
- [ ] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/unit/test_basic_tools_e2e.py
"""Integration tests for M1 Basic Tools — end-to-end through the SDK."""

import os
import pytest
from unittest.mock import MagicMock, patch
from tinycua_sdk import Agent
from tinycua_sdk.tools.decorators import Tool


@pytest.fixture
def session():
    """Create a real session with todo_list for tool testing."""
    from tinycua_sdk import Session
    _session = Session()
    _session.todo_list = []
    return _session


def test_tool_result_model_importable():
    """ToolResult is importable from tinycua.tools and has all required fields."""
    from tinycua.tools.result import ToolResult

    result = ToolResult(success=True, output="hello")
    assert result.success is True
    assert result.output == "hello"
    assert result.error is None
    assert isinstance(result.metadata, dict) or result.metadata is None
    assert isinstance(result.duration, float)


def test_all_tools_register_with_agent():
    """All M1 tools can be registered with an SDK Agent as Tool instances."""
    from tinycua.tools.native.shell import run_shell
    from tinycua.tools.native.files import read_file, write_file, list_files
    from tinycua.tools.native.web import fetch_url
    from tinycua.tools.native.python_exec import run_python
    from tinycua.tools.todo import TodoList
    from tinycua.tools.digester import digest_information

    tools = [
        run_shell, read_file, write_file, list_files, fetch_url, run_python,
        TodoList, digest_information,
    ]
    for t in tools:
        assert isinstance(t, Tool), f"{t.name} should be a Tool instance"
    assert all(hasattr(t, "name") and hasattr(t, "parameters") for t in tools)


def test_todo_tool_add_read_clear(session):
    """TodoList add/read/clear work through the SDK."""
    from tinycua.tools.todo import TodoList

    with patch("tinycua.tools.todo._session", session):
        session.todo_list = []

        result = TodoList(action="add", todo="Write tests")
        assert "Write tests" in result

        result2 = TodoList(action="read")
        assert "Write tests" in result2

        result3 = TodoList(action="clear")
        assert "cleared" in result3.lower() or "empty" in result3.lower()


def test_native_tools_integration(tmp_path):
    """Native execution tools work and return structured results."""
    from unittest.mock import patch, MagicMock
    from tinycua.tools.native.files import write_file, read_file, list_files
    from tinycua.tools.native.shell import run_shell
    from tinycua.tools.native.python_exec import run_python
    from tinycua.tools.native.web import fetch_url

    # File tools
    test_file = tmp_path / "test_m1_integration.txt"
    result = write_file(path=str(test_file), content="hello world")
    assert result["success"] is True

    content = read_file(path=str(test_file))
    assert "hello world" in content

    # list_files
    files = list_files(path=str(tmp_path), pattern="*.txt")
    assert str(test_file) in files

    # Shell execution
    shell_result = run_shell(command=f"echo hello")
    assert shell_result["exit_code"] == 0
    assert "hello" in shell_result["stdout"]

    # Python execution
    py_result = run_python(code="print('hello')")
    assert py_result["exit_code"] == 0
    assert "hello" in py_result["stdout"]

    # HTTP fetch
    with patch("tinycua.tools.native.web.httpx.Client") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "hello from web"
        mock_client.return_value.__enter__.return_value.send.return_value = mock_response
        url_result = fetch_url(url="http://example.com")
        assert "hello from web" in url_result
```

### Key Test Scenarios

- [ ] **Scenario 1**: All M1 tools are importable and register with SDK Agent as `Tool` instances
- [ ] **Scenario 2**: `ToolResult` model is importable and has all required fields
- [ ] **Scenario 3**: Native execution tools return correct structured results
- [ ] **Scenario 4**: TodoList add/read/clear cycle works

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for each tool module — test error handling, edge cases, fallbacks
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] `cd src/tinycua && uv run pytest tests/**/test_tool* tests/**/test_todo*` passes
- [ ] All tools are importable from `tinycua.tools` public exports

### Performance Considerations

- [ ] Timeout enforcement on shell/python prevents runaway processes

## Proposed Changes

### Native Tool Result Model

#### [NEW] `tinycua/tools/__init__.py`

- **[Description]**: Public exports for all tool functions + ToolResult
- **[Dependencies]**: tinycua_sdk

#### [NEW] `tinycua/tools/result.py`

- **[Description]**: Native `ToolResult` dataclass with `success`, `output`, `error`, `metadata`, `duration`
- **[Rationale]**: Structured result format for all tool executions, usable by ExecutionLog

### Native Execution Tools

#### [NEW] `tinycua/tools/native/__init__.py`

- **[Description]**: Re-exports from individual native tool modules

#### [NEW] `tinycua/tools/native/shell.py`

- **[Description]**: `run_shell` — execute shell command with timeout, return `{stdout, stderr, exit_code, timed_out, error}`
- **[Rationale]**: Adapted from `tinycua/agent/tools/native/shell.py`

#### [NEW] `tinycua/tools/native/files.py`

- **[Description]**: `read_file`, `write_file`, `list_files` — file I/O with SDK-compatible signatures
- **[Rationale]**: Adapted from `tinycua/agent/tools/native/files.py` (without `edit_file`)

#### [NEW] `tinycua/tools/native/web.py`

- **[Description]**: `fetch_url` — HTTP fetch with configurable method/headers/timeout
- **[Rationale]**: Adapted from `tinycua/agent/tools/native/web.py`

#### [NEW] `tinycua/tools/native/python_exec.py`

- **[Description]**: `run_python` — execute Python code in subprocess with timeout
- **[Rationale]**: Adapted from `tinycua/agent/tools/native/python_exec.py`

> **Note — M2 Deferral**: Task Tools (read/write tools and `_mutation.py` helpers) are deferred to M2 pending `Task`/`TaskResult` state object implementation in the SDK. See `src/tinycua/specs/basic-tools/spec.md` for details.

### TodoList Tool

#### [NEW] `tinycua/tools/todo.py`

- **[Description]**: `TodoList` tool with sub-commands: `add`, `read`, `mark_complete`, `mark_incomplete`, `edit`, `delete`, `clear`
- **[Rationale]**: Per-session short-term goal tracking stored on `session.todo_list`

### Digester Retrieval Tool Interface

#### [NEW] `tinycua/tools/digester.py`

- **[Description]**: `create_enhanced_context_retrieval` factory + `digest_information` tool
- **[Rationale]**: Digester interface for context retrieval and structured digest output

### Tool Constants

#### [NEW] `tinycua/constants/__init__.py`

- **[Description]**: Package init

#### [NEW] `tinycua/constants/tools.py`

- **[Description]**: All `*_BASE_TOOLS` constants for every agent node type: `SHARED_AGENT_BASE_TOOLS`, `TASK_EXECUTOR_BASE_TOOLS`, `RESULT_REVIEWER_BASE_TOOLS`, `QUERY_ANALYST_BASE_TOOLS`, `INFORMATION_DIGESTER_BASE_TOOLS`, `TASK_ANALYZER_BASE_TOOLS`, `TASK_ASSESSOR_BASE_TOOLS`, `PRIMARY_AGENT_BASE_TOOLS`, `CONTEXT_CACHE_TOOLS`, `EXPLORATION_TOOL` (note: `READ_ONLY_TASK_TOOLS` and `WRITE_TASK_TOOLS` are deferred to M2)
- **[Rationale]**: Module-level constants for per-node tool assignment

#### [MODIFY] `tinycua/__init__.py`

- **[Description]**: Update version string if needed (optional)

#### [MODIFY] `tinycua/agent/tools/__init__.py`

- **[Description]**: Update exports to maintain backward compatibility for any existing imports
- **[Rationale]**: Existing code may import from `tinycua.agent.tools`

### Tests

#### [NEW] `tests/unit/test_basic_tools_e2e.py`

- **[Description]**: End-to-end integration tests for M1 Basic Tools through the SDK
- **[Dependencies]**: All tool modules

#### [NEW] `tests/unit/test_tool_result.py`

- **[Description]**: Unit tests for `ToolResult` model

#### [NEW] `tests/unit/test_todo.py`

- **[Description]**: Unit tests for `TodoList` tool (all 7 sub-commands, pre-init behavior, empty list)

#### [NEW] `tests/unit/test_digester.py`

- **[Description]**: Unit tests for digester tool interface

#### [NEW] `tests/unit/test_tool_constants.py`

- **[Description]**: Unit tests for tool constants module

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/agent/tools/native/` | Existing | Shell, file, web, python tools already exist — verify SDK compatibility |
| `tinycua/agent/tools/__init__.py` | Modify | Update exports to include new tools |
| `tinycua/tools/` | New | New top-level package for tool implementations |
| `tinycua/tools/result.py` | New | Native ToolResult dataclass |
| `tinycua/tools/native/` | New | Native execution tools (adapted from agent/tools/native) |
| `tinycua/tools/task/` | Deferred → M2 | Task read/write tools (deferred to M2) |
| `tinycua/tools/todo.py` | New | TodoList tool with sub-command dispatch |
| `tinycua/tools/digester.py` | New | create_enhanced_context_retrieval + digest_information |
| `tinycua/constants/` | New | Package for tool constant definitions |
| `tinycua/constants/tools.py` | New | `*_BASE_TOOLS` constants for all agent nodes |
| `tinycua/tools/__init__.py` | New | Public exports for all tool functions |

## Data Model Changes

```python
# New types or modified interfaces
@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    metadata: dict | None = None
    duration: float = 0.0
```

```python
# Session state extensions
session.todo_list: list[dict] | None = None
# Each item: {"status": "incomplete" | "completed", "todo": str}
```

## API Changes

### New Tool APIs

All tools are `@tool`-decorated functions callable through `tinycua_sdk.AgentExecutor.execute()`:

| Tool Name | Module | Description |
|-----------|--------|-------------|
| `run_shell` | `tinycua.tools.native.shell` | Execute shell command with timeout |
| `read_file` | `tinycua.tools.native.files` | Read file contents (full or line-range) |
| `write_file` | `tinycua.tools.native.files` | Write content to file |
| `list_files` | `tinycua.tools.native.files` | List files matching glob pattern |
| `fetch_url` | `tinycua.tools.native.web` | Fetch URL content |
| `run_python` | `tinycua.tools.native.python_exec` | Execute Python code in subprocess |
| `TodoList` | `tinycua.tools.todo` | Per-session goal tracking |
| `digest_information` | `tinycua.tools.digester` | Produce structured digest |
| `create_enhanced_context_retrieval` | `tinycua.tools.digester` | Factory for retrieval tool |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| tinycua-sdk | >=0.1.0 | Tool decorator, Agent, AgentExecutor, Session model |
| httpx | >=0.27.0 | HTTP fetch tool |

### Internal Dependencies

- [ ] Blocks Agent node implementations (TaskExecutor, TaskAnalyzer, etc.)
- [ ] Task tools (deferred to M2) depend on `tinycua-sdk` Task/TaskResult state objects

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SDK compatibility gaps | Medium | All tools tested through `AgentExecutor.execute()` in integration tests |
| Session state management errors in tools | Medium | Tools receive session via closure |
| `run_shell` dangerous commands | High | Scope: benchmarks run in controlled environments only; future sandboxing needed |
| `run_python` infinite loops | Medium | Configurable timeout (default 30s) enforced by subprocess kill |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-02*
