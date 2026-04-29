# Review Report: Stage 02 — New Unit Tests

**Reviewer:** Independent Fresh Review  
**Date:** 2026-04-29  
**Scope:** `src/tinycua-sdk/specs/refactor-tinycua-sdk/02-new-unit-tests/` and `tests/unit/`

---

## Summary

Stage 02 is **nearly clean**. All required test files exist, every spec-required test is present, mocking and lazy imports are correct, and `pytest --collect-only` passes without errors. There is **one duplicate test** that should be removed.

---

## Required Test Files Status

| File | Status | Notes |
|------|--------|-------|
| `tests/unit/__init__.py` | ✅ Exists | Package marker present. |
| `tests/unit/conftest.py` | ✅ Exists | All 4 required fixtures (`default_llm`, `default_backend`, `default_loop`, `mock_llm_response`) present with lazy imports. |
| `tests/unit/test_agent.py` | ✅ Complete | All 32 spec-required tests present (construction, tool/skill composition, config round-trip, run, statelessness, templates). |
| `tests/unit/test_tool.py` | ✅ Complete | All 13 spec-required tests present (decorator, schema, invoke, config, statelessness). |
| `tests/unit/test_skills.py` | ✅ Complete | All 10 spec-required tests present (construction, load, registry). |
| `tests/unit/test_config.py` | ✅ Complete | All AgentConfig and SDKConfig tests present. |
| `tests/unit/test_loop.py` | ✅ Complete | All 7 spec-required BaseLoop / resolve_loop tests present. |
| `tests/unit/test_llm_model.py` | ✅ Complete | All 8 LLMModel tests present. |
| `tests/unit/test_backend_config.py` | ✅ Complete | All 4 BackendConfig tests present. |
| `tests/unit/test_agent_templates.py` | ✅ Complete | All 4 template tests present. |

---

## Detailed Checks

### 1. Coverage of Public APIs per Spec
**Result: PASS**

Every test named in `spec.md` and `design.md` is implemented. The few tests that the spec lists under `test_config.py` but logically belong to `test_llm_model.py` / `test_backend_config.py` (e.g., `test_llm_model_defaults`) were correctly split into their own files per `design.md`.

### 2. Duplicate Tests
**Result: ONE ISSUE FOUND**

- **`test_llm_model_round_trip`** is **identically duplicated** in:
  - `tests/unit/test_llm_model.py` (lines 73–81)
  - `tests/unit/test_config.py` (lines 129–137)

The two implementations have the exact same assertions. One copy should be removed. `test_llm_model.py` is the more natural home; the duplicate in `test_config.py` should be deleted.

> **Other duplicates exist** across legacy test files (e.g., `test_add_sub_agent` in `test_agent_definition.py` and `test_agent_hierarchy.py`), but those are outside the Stage 02 scope and do not duplicate any of the new stateless API tests.

### 3. Missing Spec-Required Tests
**Result: NONE**

All 87 spec-required tests are present and named clearly.

### 4. Proper Mocking
**Result: PASS**

All `Agent.run()` tests in `test_agent.py` mock the LLM client at the public executor boundary exactly as specified:

```python
with patch("tinycua_sdk.agent.executor.LLMClient") as MockClient:
    mock_instance = MockClient.return_value
    mock_instance.chat = AsyncMock(return_value=...)
```

No tests call real LLM endpoints.

### 5. Lazy Imports
**Result: PASS**

All Stage 02 required test files use lazy imports (`from tinycua_sdk import X` inside test functions). This prevents collection errors when the target implementation does not yet exist.

### 6. Test Collection Errors
**Result: PASS**

```
pytest tests/unit/ --collect-only
# => 365 tests collected in 0.19s, zero import/syntax errors.
```

The 87 Stage 02 tests also collect cleanly in isolation:

```
pytest tests/unit/test_agent.py tests/unit/test_tool.py ... --collect-only
# => 87 tests collected in 0.04s, zero errors.
```

### 7. TDD State (Tests Fail as Expected)
**Result: PASS**

Running the Stage 02 tests fails because the new stateless API classes (`LLMModel`, `Agent`, `Tool`, etc.) are not yet exported from `tinycua_sdk`. This is the correct TDD state for Stage 02.

---

## Recommendations

1. **Remove duplicate test** `test_llm_model_round_trip` from `tests/unit/test_config.py` (keep the one in `tests/unit/test_llm_model.py`).

2. **Optional cleanup:** Legacy test files (`test_agent_definition.py`, `test_agent_executor.py`, `test_agent_hierarchy.py`, `test_skills_registry.py`, `test_skills_loader.py`, `test_skills_tools.py`, `test_skills_cache.py`, `test_skills_improver.py`, `test_tool_registry.py`, `test_tool_resolver.py`, `test_tool_schema.py`, `test_loop_resolver.py`, `test_streaming.py`, `test_providers.py`, `test_mcp.py`, `test_security.py`, `test_sanitizer.py`, `test_middleware_hooks.py`, `test_error_handling.py`, `test_command_parser.py`, `test_injection_detection.py`, `test_context_discovery.py`, `test_import_sanity.py`) remain in `tests/unit/`. They test legacy/singleton-based APIs and do not conflict with the new tests, but their presence means Stage 01 (legacy test removal) was not fully completed. Consider archiving or deleting them in a future cleanup pass to avoid confusion.

---

## Verdict

**Stage 02 is approved with one minor fix required:** remove the duplicated `test_llm_model_round_trip` from `test_config.py`.

After that fix, Stage 02 will be **CLEAN**.
