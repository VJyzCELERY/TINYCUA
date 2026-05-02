# Stage 9: Final Integration & Polish — Specification

## Objective
All 16 integration tests pass. The SDK is coherent, fully typed, linted, and documented.

## Guiding Principles
All stages adhere to the principles defined in [`ROADMAP.md#principles`](../../docs/ROADMAP.md#principles).

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

Each success criterion must be validated by running the specified target file(s).

Format: [ ] Success Criteria Description - Target File(s) - Expected Output - How to validate

- [ ] All Integration Tests Pass - tests/integration/goals/ - 16 passed, 0 failed - pytest -v
  Description: Full goal test suite passes.

- [ ] Ruff Passes - N/A - exits with code 0 - ruff check tinycua_sdk/
  Description: Code passes linting.

- [ ] Public API is Clean - N/A - only exports from `__all__` are present - python -c "from tinycua_sdk import *; print(sorted(dir()))"
  Description: `from tinycua_sdk import *` imports only v2 public API.

- [ ] No NotImplementedError in Production - N/A - PASS: no stubs found - grep -r "NotImplementedError" tinycua_sdk/
  Description: No production code raises `NotImplementedError`.

- [ ] Goal Scripts Runnable - N/A - all scripts run without `ImportError` or `AttributeError` - python <script>
  Description: Each goal script can be executed (with mock or real LLM).

- [ ] Import Sanity - N/A - prints `OK` - python -c "import tinycua_sdk; print('OK')"
  Description: SDK imports cleanly.

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
