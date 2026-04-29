# Stage 01 Review — Remove Legacy Tests & Examples
**Review Type:** Completely fresh, independent review  
**Reviewer:** OpenCode Agent  
**Date:** 2026-04-29  
**Branch:** `refactor/tinycua-sdk`  
**Commit Base:** `8c107a2`

---

## Summary

| Check | Status |
|-------|--------|
| Correct files deleted? | **Mostly** — one test was incorrectly deleted |
| Files incorrectly deleted? | **YES** — `test_context_discovery.py` |
| Remaining references to deleted modules? | **YES** — dead code in `conftest.py`, obsolete docs |
| Import errors? | **NONE** — `pytest --collect-only` passes cleanly |
| Remaining tests pass? | **YES** — 357 unit tests pass, 75 integration tests collect |
| Compliance with spec? | **Partial** — conditional deletion misapplied |

**Overall Verdict:** ⚠️ **Issues Found** — 1 major, 4 minor.

---

## Findings

### 🔴 MAJOR — Incorrectly Deleted Test

**Status:** ADDRESSED ✅

#### `tests/unit/test_context_discovery.py` was deleted but should have been kept

**Location:** `tests/unit/test_context_discovery.py` (deleted)  
**Spec Reference:** `spec.md` lists it with condition: *"if it depends on memory/session"*

**Analysis:**
- The deleted test imported `ContextDiscovery` from `tinycua_sdk.context.discovery`.
- Examination of `tinycua_sdk/context/discovery.py` shows **zero** imports from `memory/`, `session/`, `storage/`, or any module scheduled for deletion.
- `ContextDiscovery` is a standalone utility that searches for markdown context files (`.hermes.md`, `AGENTS.md`, `CLAUDE.md`) using only the Python standard library (`pathlib`).
- No later stage spec mentions deleting `context.discovery`.

**Conclusion:** The conditional deletion criterion (*"if it depends on session"*) was **not met**. The test was incorrectly deleted, resulting in lost coverage for a staying module.

**Recommended Fix:** Restore `tests/unit/test_context_discovery.py` from git history.

```bash
git show HEAD:src/tinycua-sdk/tests/unit/test_context_discovery.py > src/tinycua-sdk/tests/unit/test_context_discovery.py
```

---

### 🟡 MINOR — Dead Code in Integration Conftest

**Status:** ADDRESSED ✅

#### `tests/integration/conftest.py` references deleted test file

**Location:** `tests/integration/conftest.py:23`  
**Code:**
```python
if "test_local_run" in item.fspath.basename:
```

**Analysis:**
- `tests/integration/test_local_run.py` was correctly deleted.
- This skip logic in `pytest_collection_modifyitems` will never match any collected item.
- The code is harmless but should be removed to avoid confusion.

**Recommended Fix:** Remove the `if "test_local_run" in item.fspath.basename:` block from `pytest_collection_modifyitems`.

---

### 🟡 MINOR — Unused Fixture in Unit Conftest

**Status:** ADDRESSED ✅

#### `tests/unit/conftest.py` defines `temp_memory_dir` that is no longer used

**Location:** `tests/unit/conftest.py:45-49`  
**Code:**
```python
@pytest.fixture
def temp_memory_dir(tmp_path):
    """Temporary memory directory."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    return memory_dir
```

**Analysis:**
- Grepping the entire `tests/` tree shows **zero** usages of `temp_memory_dir`.
- All memory-related tests that used this fixture were deleted.
- The fixture is harmless but adds unnecessary noise.

**Recommended Fix:** Remove the `temp_memory_dir` fixture.

---

### 🟡 MINOR — Obsolete Integration Test Documentation

**Status:** ADDRESSED ✅

#### `tests/integration/README.md` documents deleted/non-existent tests

**Location:** `tests/integration/README.md`  
**Issues:**
- References deleted tests: `test_memory_session.py`, `test_memory_operations.py`
- References non-existent tests: `test_all.py`, `test_01_basic_agent.py`, `test_02_streaming.py`, `test_05_agent_hierarchy.py`, `test_06_local_storage.py`
- Describes fixtures (`memory_agent`, `temp_memory_backend`, `temp_store`) for deleted functionality
- Documents test coverage for `memory/`, `storage/`, and `session/` which are being removed

**Recommended Fix:** Delete `tests/integration/README.md` or rewrite it to reflect the current integration test suite.

---

### 🟡 MINOR — Obsolete Integration Test Specification

**Status:** ADDRESSED ✅

#### `tests/integration/SPEC.md` documents deleted/non-existent tests

**Location:** `tests/integration/SPEC.md`  
**Issues:**
- Same problems as `README.md` — references `test_all.py`, `test_01_basic_agent.py`, `test_02_streaming.py`, `test_03_memory_session.py`, `test_05_agent_hierarchy.py`, `test_06_local_storage.py`
- Describes deleted fixtures and deleted functionality
- Contains implementation plans for tests that no longer exist

**Recommended Fix:** Delete `tests/integration/SPEC.md`.

---

## Verification Log

### Files Deleted (from git status)

| File | Spec Match | Verdict |
|------|-----------|---------|
| `docs/examples/example_main.py` | ✅ `docs/examples/example_main.py` | Correct |
| `tests/integration/test_agent_delegation.py` | ✅ `tests/integration/test_agent_delegation.py` | Correct |
| `tests/integration/test_context_pipeline.py` | ✅ `tests/integration/test_context_pipeline.py` | Correct |
| `tests/integration/test_hooks_pipeline.py` | ✅ `tests/integration/test_hooks_pipeline.py` | Correct |
| `tests/integration/test_local_run.py` | ✅ `tests/integration/test_local_run.py` | Correct |
| `tests/integration/test_memory_example.py` | ✅ `tests/integration/test_memory_*.py` | Correct |
| `tests/integration/test_memory_operations.py` | ✅ `tests/integration/test_memory_*.py` | Correct |
| `tests/integration/test_memory_session.py` | ✅ `tests/integration/test_memory_*.py` | Correct |
| `tests/integration/test_runner_integration.py` | ✅ `tests/integration/test_runner_integration.py` | Correct |
| `tests/integration/test_storage_agent.py` | ✅ `tests/integration/test_storage_agent.py` | Correct |
| `tests/unit/test_agent_commands.py` | ✅ `tests/unit/test_cli_*.py` pattern | Correct (CLI test) |
| `tests/unit/test_backend_connection.py` | ✅ `tests/unit/test_backend_connection.py` | Correct |
| `tests/unit/test_client.py` | ✅ `tests/unit/test_client.py` | Correct |
| `tests/unit/test_clients.py` | ✅ `tests/unit/test_clients.py` | Correct |
| `tests/unit/test_context_compression.py` | ✅ `tests/unit/test_context_compression.py` | Correct (depends on `memory/`) |
| `tests/unit/test_context_discovery.py` | ⚠️ "if depends on session" — **it does not** | **INCORRECTLY DELETED** |
| `tests/unit/test_export_import.py` | ✅ `tests/unit/test_export_import.py` | Correct |
| `tests/unit/test_local_storage.py` | ✅ `tests/unit/test_local_storage.py` | Correct |
| `tests/unit/test_long_term_memory.py` | ✅ `tests/unit/test_long_term_memory.py` | Correct |
| `tests/unit/test_memory.py` | ✅ `tests/unit/test_memory*.py` | Correct |
| `tests/unit/test_memory_plugin.py` | ✅ `tests/unit/test_memory*.py` | Correct |
| `tests/unit/test_memory_snapshot.py` | ✅ `tests/unit/test_memory*.py` | Correct |
| `tests/unit/test_personality.py` | ✅ `tests/unit/test_personality.py` | Correct |
| `tests/unit/test_prompt_cache.py` | ✅ `tests/unit/test_prompt_cache.py` | Correct |
| `tests/unit/test_registry.py` | ✅ `tests/unit/test_registry.py` | Correct |
| `tests/unit/test_remote_runner.py` | ✅ `tests/unit/test_remote_runner.py` | Correct |
| `tests/unit/test_session_store_crud.py` | ✅ `tests/test_session*.py` (design) | Correct |
| `tests/unit/test_short_term_memory.py` | ✅ `tests/unit/test_short_term_memory.py` | Correct |
| `tests/unit/test_storage.py` | ✅ `tests/unit/test_storage*.py` | Correct |
| `tests/unit/test_user_modeling.py` | ✅ `tests/unit/test_user_modeling.py` | Correct |

### Spec File Not Found (no action needed)

| File | Status |
|------|--------|
| `tests/unit/test_context_tools.py` | Did not exist in codebase |

### Obsolete Docs Already Removed

| File | Status |
|------|--------|
| `docs/session.md` | ✅ Missing |
| `docs/memory.md` | ✅ Missing |
| `docs/storage.md` | ✅ Missing |
| `docs/cli.md` | ✅ Missing |
| `docs/examples/README.md` | ✅ Missing |

### Test Results

```
$ cd src/tinycua-sdk && python -m pytest tests/ --collect-only
========================= 432 tests collected in 0.20s =========================

$ cd src/tinycua-sdk && python -m pytest tests/unit/ -v --tb=short
======================== 357 passed, 1 warning in 1.54s ========================

$ cd src/tinycua-sdk && python -m pytest tests/integration/ --collect-only
========================= 75 tests collected in 0.14s ==========================
```

**No import errors. All remaining tests pass.**

### Modified File Reviewed

**`tests/unit/test_import_sanity.py`** — Correctly updated:
- Removed `TestDeprecatedRegistryPatterns` (imported `core.registry.ToolRegistry`)
- Removed `TestDeprecatedStorePatterns` (imported `storage.store.SessionStore`)
- Added `TestCoreImports` with clean imports for `Agent` and `tool`

This modification is compliant with the spec.

---

## Validation Log

**Date:** 2026-04-29  
**Validator:** OpenCode Agent  
**Status:** All findings verified as addressed ✅

### Verification Commands & Results

| Check | Command | Result |
|-------|---------|--------|
| Package imports | `python -c "import tinycua_sdk"` | ✅ Success |
| Test collection | `pytest tests/ --collect-only` | ✅ 438 tests collected, zero import errors |
| Restored test passes | `pytest tests/unit/test_context_discovery.py -v` | ✅ 6/6 passed |
| Dead code removed | `grep -r "test_local_run" tests/integration/conftest.py` | ✅ No matches |
| Unused fixture removed | `grep -r "temp_memory_dir" tests/unit/conftest.py` | ✅ No matches |
| Obsolete README deleted | `ls tests/integration/README.md` | ✅ File not found |
| Obsolete SPEC deleted | `ls tests/integration/SPEC.md` | ✅ File not found |

### Summary

All recommendations from this review have been successfully implemented and validated. The codebase is clean with no regressions.

---

*End of Review — Validated*
