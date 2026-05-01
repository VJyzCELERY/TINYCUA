# Stage 9: Final Integration & Polish — Specification

## Objective
All 16 integration tests pass. The SDK is coherent, fully typed, linted, and documented.

## References
- All goal scripts in [`../goals/`](../goals/)
- [`ROADMAP.md`](../docs/ROADMAP.md)

## Requirements

### R-9.1: Full Integration Test Suite
All 16 goal-derived integration tests must pass.

### R-9.2: Type Cleanup
- No unnecessary `Any` types in public APIs.
- All public functions have complete type annotations.
- Internal functions should also be typed where possible.

### R-9.3: Public API Exports
`tinycua_sdk/__init__.py` exports only the v2 public API:
```python
__all__ = [
    "Agent",
    "LanguageModel",
    "Tool",
    "tool",
    "Skill",
    "SkillRegistry",
    "BaseLoop",
    "ApprovalWorkflow",
]
```

### R-9.4: Documentation Update
- `AGENTS.md` updated if it references deleted APIs.
- Docstrings on all public classes and methods.

### R-9.5: Old Test Cleanup
- Delete unit tests for removed modules.
- Keep or rewrite unit tests for behavior still present.

### R-9.6: Linting
`ruff check tinycua_sdk/` must pass.

### R-9.7: No Stubs
No `NotImplementedError` stubs remain in production code paths.

## Success Criteria

### SC-9.1: All Integration Tests Pass
**What:** Full goal test suite passes.  
**How to check:**
```bash
cd src/tinycua-sdk && pytest tests/integration/goals/ -v
```
**Pass if:** 16 passed, 0 failed.

### SC-9.2: Ruff Passes
**What:** Code passes linting.  
**How to check:**
```bash
cd src/tinycua-sdk && ruff check tinycua_sdk/
```
**Pass if:** exits with code 0.

### SC-9.3: Public API is Clean
**What:** `from tinycua_sdk import *` imports only v2 public API.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
from tinycua_sdk import *
print(sorted(dir()))
"
```
**Pass if:** only exports from `__all__` are present.

### SC-9.4: No NotImplementedError in Production
**What:** No production code raises `NotImplementedError`.  
**How to check:**
```bash
cd src/tinycua-sdk && grep -r "NotImplementedError" tinycua_sdk/ || echo "PASS: no stubs found"
```
**Pass if:** prints `PASS` or empty result.

### SC-9.5: Goal Scripts Runnable
**What:** Each goal script can be executed (with mock or real LLM).  
**How to check:**
```bash
cd src/tinycua-sdk && python specs/refactor-tinycua-sdk-v2/goals/getting-started/01_language_model_definition.py
cd src/tinycua-sdk && python specs/refactor-tinycua-sdk-v2/goals/intermediate/01_tool_creation.py
# ... etc for all 16 scripts
```
**Pass if:** all scripts run without `ImportError` or `AttributeError`.

### SC-9.6: Import Sanity
**What:** SDK imports cleanly.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "import tinycua_sdk; print('OK')"
```
**Pass if:** prints `OK`.

## Integration Test Files
All 16:
- `tests/integration/goals/test_gs_01_language_model_definition.py`
- `tests/integration/goals/test_gs_02_agent_creation.py`
- `tests/integration/goals/test_gs_03_agent_calling.py`
- `tests/integration/goals/test_gs_04_agent_streaming.py`
- `tests/integration/goals/test_int_01_tool_creation.py`
- `tests/integration/goals/test_int_02_skills_creation.py`
- `tests/integration/goals/test_int_03_agent_with_tools.py`
- `tests/integration/goals/test_int_04_agent_with_skills.py`
- `tests/integration/goals/test_int_05_agent_with_tools_and_skills.py`
- `tests/integration/goals/test_int_06_exporting_agent.py`
- `tests/integration/goals/test_int_07_loading_agent.py`
- `tests/integration/goals/test_int_08_loading_skills_from_directory.py`
- `tests/integration/goals/test_int_09_loading_tools_from_directory.py`
- `tests/integration/goals/test_adv_01_custom_agent_loop.py`
- `tests/integration/goals/test_adv_02_guardrail_system.py`
- `tests/integration/goals/test_adv_03_permission_system.py`
