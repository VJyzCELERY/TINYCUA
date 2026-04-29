# Review Report: Stage 07 — Remove CLI & Clients

**Date:** 2026-04-29
**Reviewer:** OpenCode
**Target Directory:** `src/tinycua-sdk/specs/refactor-tinycua-sdk/07-remove-cli-clients/`

---

## Summary

**Status: NOT CLEAN**

The `cli/`, `clients/`, and `runner/` packages have been successfully removed from the SDK. The core `tinycua_sdk` package contains no imports from the deleted packages and imports cleanly. However, **8 tests still import from the deleted `tinycua_sdk.runner` module and fail with `ModuleNotFoundError`**, violating the acceptance criterion that "pytest still passes for remaining tests." Additionally, several examples and the `README.md` still document the deleted APIs.

---

## Checks

### 1. `cli/` deleted?
✅ **PASS** — `tinycua_sdk/cli/` does not exist.

### 2. `clients/` deleted?
✅ **PASS** — `tinycua_sdk/clients/` does not exist.

### 3. `runner/` deleted?
✅ **PASS** — `tinycua_sdk/runner/` does not exist.

### 4. No imports from deleted packages?
✅ **PASS** — No `from tinycua_sdk.cli`, `from tinycua_sdk.clients`, or `from tinycua_sdk.runner` imports remain inside the `tinycua_sdk/` package.

> Note: `agent/executor.py` and `agent/agent.py` still accept constructor parameters related to remote execution (`mode`, `backend_url`, `backend_api_key`, `backend_headers`, `agent_id`, `runner`). These are not imports from deleted packages, but they are residual remote-execution parameters.

### 5. Package imports cleanly?
✅ **PASS** — `python -c "import tinycua_sdk"` succeeds without error.

### 6. `pyproject.toml` — CLI entry point removed?
✅ **PASS** — No `[project.scripts]` or `tinycua = ...` entry point in `pyproject.toml`.

### 7. `Agent` — no client / remote-execution method references?
✅ **PASS** — `agent/executor.py` has no `BackendClient` import and no `_client`, `_get_client()`, `_run_deployed()`, `_run_guest()` methods. `agent/agent.py` has no `deploy()`, `delete()`, `set_guest_mode()`, or `load_agent()` class methods.

---

## Issues Found

### Issue 1: Tests still import deleted `runner` package (8 failures)
**Severity: HIGH**

Two test files contain imports from `tinycua_sdk.runner` (deleted). Running pytest produces `ModuleNotFoundError`.

| File | Lines | Import |
|------|-------|--------|
| `tests/unit/test_streaming.py` | 36, 69, 125, 150, 169 | `from tinycua_sdk.runner import Runner` |
| `tests/unit/test_agent_hierarchy.py` | 442, 453, 464 | `from tinycua_sdk.runner import Runner` |

**Failing tests:**
- `tests/unit/test_streaming.py::TestRunnerStreamWithTools::test_stream_with_tools_returns_events`
- `tests/unit/test_streaming.py::TestRunnerStreamWithTools::test_stream_with_tools_tool_call_detection`
- `tests/unit/test_streaming.py::TestToolExecutionStreaming::test_execute_tool_regular_function`
- `tests/unit/test_streaming.py::TestToolExecutionStreaming::test_execute_tool_not_found`
- `tests/unit/test_streaming.py::TestToolExecutionStreaming::test_tool_result_chunking`
- `tests/unit/test_agent_hierarchy.py::TestRunnerStreamSSE::test_runner_stream_sse_attribute`
- `tests/unit/test_agent_hierarchy.py::TestRunnerStreamSSE::test_runner_verbose_attribute`
- `tests/unit/test_agent_hierarchy.py::TestRunnerStreamSSE::test_runner_trace_attribute`

**Impact:** Breaks the acceptance criterion *"pytest still passes for remaining tests."*

**Recommendation:** Remove or rewrite these tests since the `runner` package no longer exists.

---

### Issue 2: Examples still reference deleted packages
**Severity: MEDIUM**

Four example scripts import from deleted modules. They will fail at runtime.

| File | Line | Import |
|------|------|--------|
| `examples/04_remote_runner.py` | 15 | `from tinycua_sdk.runner import HTTPRunner, RemoteRunner, RunnerOptions` |
| `examples/07_deployed_agent.py` | 30 | `from tinycua_sdk.clients import BackendClient` |
| `examples/09_global_api_key.py` | 28 | `from tinycua_sdk.clients import BackendClient` |
| `examples/11_deployed_loop.py` | 29 | `from tinycua_sdk.clients import BackendClient` |

**Recommendation:** Delete or update these examples to reflect the new SDK surface.

---

### Issue 3: `README.md` still documents deleted `BackendClient`
**Severity: LOW**

`README.md` line 113 contains:
```python
from tinycua_sdk.clients import BackendClient
```

**Recommendation:** Remove the "Remote Execution (With Backend)" section or rewrite it to show consumer-implemented HTTP clients.

---

## Minor Notes

- `agent/executor.py` and `agent/agent.py` retain constructor parameters (`mode`, `backend_url`, `backend_api_key`, `backend_headers`, `agent_id`, `runner`) related to remote execution. While not imports from deleted packages, they are vestigial references to removed remote-execution concepts. Consider cleaning them up in a follow-up stage.
- The `run()` / `stream()` methods in `AgentExecutor` currently raise `NotImplementedError("Agent execution infrastructure has been removed.")` for all invocation paths. The spec says `Agent.run()` should "only handle local execution"; at present it handles none. This may be intentional for an intermediate stage, but should be tracked.

---

## Verdict

Stage 07 has successfully removed the `cli/`, `clients/`, and `runner/` packages from the SDK core. The package itself is import-clean. However, **leftover test code referencing the deleted `runner` package causes pytest failures**, and broken examples/README references remain. These must be cleaned up before the stage can be considered complete.
