# Implementation: M1 — Basic Tools

Implement the foundational tool layer for the TINYCUA prototype: native execution tools (shell, file, web, python), the `ToolResult` model, and minimal stateless tool constants. Orchestration-layer tools (TodoList, digester retrieval interface, per-agent tool constants) are deferred to M2. All M1 tools are implemented as `tinycua_sdk` `@tool`-decorated functions.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P0
- **Estimated Effort**: L *(reduced from XL — TodoList, digester, per-agent constants deferred to M2)*

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


def test_tool_result_model_importable():
    """ToolResult is importable from tinycua.tools and has all required fields."""
    from tinycua.tools.result import ToolResult

    result = ToolResult(success=True, output="hello")
    assert result.success is True
    assert result.output == "hello"
    assert result.error is None
    assert isinstance(result.metadata, dict) or result.metadata is None
    assert isinstance(result.duration, float)


def test_all_native_tools_register_with_agent():
    """All M1 native tools can be registered with an SDK Agent as Tool instances."""
    from tinycua.tools.native.shell import run_shell
    from tinycua.tools.native.files import read_file, write_file, list_files
    from tinycua.tools.native.web import fetch_url
    from tinycua.tools.native.python_exec import run_python

    tools = [
        run_shell, read_file, write_file, list_files, fetch_url, run_python,
    ]
    for t in tools:
        assert isinstance(t, Tool), f"{t.name} should be a Tool instance"
    assert all(hasattr(t, "name") and hasattr(t, "parameters") for t in tools)


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
    shell_result = run_shell(command="echo hello")
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
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        url_result = fetch_url(url="http://example.com")
        assert "hello from web" in url_result
```

### Key Test Scenarios

- [x] **Scenario 1**: All M1 native tools are importable and register with SDK Agent as `Tool` instances
- [x] **Scenario 2**: `ToolResult` model is importable and has all required fields
- [x] **Scenario 3**: Native execution tools return correct structured results
- [ ] **Scenario 4**: No orchestration-layer tools (TodoList, digester, per-agent constants) are implemented in M1

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

- **[Description]**: `read_file`, `write_file`, `edit_file`, `list_files` — file I/O with SDK-compatible signatures
- **[Rationale]**: Adapted from `tinycua/agent/tools/native/files.py` (including `edit_file`)

#### [NEW] `tinycua/tools/native/web.py`

- **[Description]**: `fetch_url` — HTTP fetch with configurable method/headers/timeout
- **[Rationale]**: Adapted from `tinycua/agent/tools/native/web.py`

#### [NEW] `tinycua/tools/native/python_exec.py`

- **[Description]**: `run_python` — execute Python code in subprocess with timeout
- **[Rationale]**: Adapted from `tinycua/agent/tools/native/python_exec.py`

> **Note — M2 Deferral**: Task Tools, TodoList, digester tools, and per-agent `*_BASE_TOOLS` constants are all deferred to M2. See `src/tinycua/specs/basic-tools/spec.md` for details.

### Tool Constants

#### [NEW] `tinycua/constants/__init__.py`

- **[Description]**: Package init

#### [NEW] `tinycua/constants/tools.py`

- **[Description]**: M1-scoped constants: `NATIVE_BASE_TOOLS` (the seven native execution tools), `READ_ONLY_TASK_TOOLS` (forward reference to M2 — placeholder only). Per-agent `*_BASE_TOOLS` (`SHARED_AGENT_BASE_TOOLS`, `TASK_EXECUTOR_BASE_TOOLS`, `RESULT_REVIEWER_BASE_TOOLS`, `QUERY_ANALYST_BASE_TOOLS`, `INFORMATION_DIGESTER_BASE_TOOLS`, `TASK_ANALYZER_BASE_TOOLS`, `TASK_ASSESSOR_BASE_TOOLS`, `PRIMARY_AGENT_BASE_TOOLS`, `CONTEXT_CACHE_TOOLS`, `EXPLORATION_TOOL`) are deferred to M2.
- **[Rationale]**: `NATIVE_BASE_TOOLS` provides a convenient stateless reference for native tool registration. `READ_ONLY_TASK_TOOLS` documents the M2 forward contract.

#### [MODIFY] `tinycua/__init__.py`

- **[Description]**: Update version string if needed (optional)

#### [MODIFY] `tinycua/agent/tools/__init__.py`

- **[Description]**: Update exports to maintain backward compatibility for any existing imports
- **[Rationale]**: Existing code may import from `tinycua.agent.tools`

### Tests

#### [NEW] `tests/unit/test_basic_tools_e2e.py`

- **[Description]**: End-to-end integration tests for M1 native tools through the SDK
- **[Dependencies]**: All native tool modules

#### [NEW] `tests/unit/test_tool_result.py`

- **[Description]**: Unit tests for `ToolResult` model

#### [NEW] `tests/unit/test_tool_constants.py`

- **[Description]**: Unit tests for `NATIVE_BASE_TOOLS` and `READ_ONLY_TASK_TOOLS` constants

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/agent/tools/native/` | Existing | Shell, file, web, python tools already exist — verify SDK compatibility |
| `tinycua/agent/tools/__init__.py` | Modify | Update exports to include new tools |
| `tinycua/tools/` | New | New top-level package for tool implementations |
| `tinycua/tools/result.py` | New | Native ToolResult dataclass |
| `tinycua/tools/native/` | New | Native execution tools (adapted from agent/tools/native) |
| `tinycua/constants/` | New | Package for tool constant definitions |
| `tinycua/constants/tools.py` | New | NATIVE_BASE_TOOLS + READ_ONLY_TASK_TOOLS (forward ref) |
| `tinycua/tools/__init__.py` | New | Public exports for all tool functions |
| `tinycua/tools/todo.py` | Deferred → M2 | TodoList tool with sub-command dispatch |
| `tinycua/tools/digester.py` | Deferred → M2 | create_enhanced_context_retrieval + digest_information |
| `tinycua/tools/task/` | Deferred → M2 | Task read/write tools |
| (per-agent *BASE_TOOLS) | Deferred → M2 | SHARED_AGENT_BASE_TOOLS, etc. |

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

> **Note — M2 Deferral**: State extensions (TodoList storage, digester cache state, Task tree state) are deferred to M2.

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

> **Note — M2 Deferred APIs**: `TodoList` (orchestration-layer goal tracking), `digest_information` (structured digest), `create_enhanced_context_retrieval` (retrieval tool factory), all per-agent `*_BASE_TOOLS` constants.

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| tinycua-sdk | >=0.1.0 | Tool decorator, Agent, AgentExecutor |
| httpx | >=0.27.0 | HTTP fetch tool |

### Internal Dependencies

- [ ] Blocks Agent node implementations (TaskExecutor, TaskAnalyzer, etc.)
- [ ] Task tools, TodoList, digester, and per-agent constants (all deferred to M2) depend on M1 for native tool primitives and the ToolResult model

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SDK compatibility gaps | Medium | All tools tested through `AgentExecutor.execute()` in integration tests |
| `run_shell` dangerous commands | High | Scope: benchmarks run in controlled environments only; future sandboxing needed |
| `run_python` infinite loops | Medium | Configurable timeout (default 30s) enforced by subprocess kill |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-02*
