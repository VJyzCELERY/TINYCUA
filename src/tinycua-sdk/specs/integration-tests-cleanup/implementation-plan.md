# Implementation: Integration Tests Cleanup

Reorganize the tinycua-sdk integration tests by relocating files from `tests/integration/goals/` into `tests/integration/`, renaming to `test_<topic>.py` convention, merging overlapping test files, adding end-to-end tests, and removing the `goals/` directory. No SDK source code changes.

## Context

- **Spec Reference**: `src/tinycua-sdk/specs/integration-tests-cleanup/spec.md`
- **Design Reference**: `src/tinycua-sdk/specs/integration-tests-cleanup/design.md`
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

> N/A — This feature only reorganizes test files. No special environment setup is needed. The existing `uv run pytest` and `make test-integration` commands continue to work as-is.

## Success Criteria — Integration Tests (TDD First)

Since this is a test reorganization (no source code changes), the "tests first" principle means:
1. Run the **existing** test suite to establish a baseline — all tests pass (or skip gracefully).
2. After each phase, rerun to verify no regressions.

```bash
# Baseline — run from src/tinycua-sdk/
cd src/tinycua-sdk && uv run pytest
```

### Key Test Scenarios

- [x] **Baseline**: All existing tests pass before we start.
- [ ] **After Phase 1**: `uv run pytest tests/integration/` still discovers all relocated tests.
- [ ] **After Phase 2**: Merged test files contain all original test methods (audit by name).
- [ ] **After Phase 3**: New `test_end_to_end.py` is discovered and runs.
- [ ] **After Phase 4**: `make test-integration` and `uv run pytest tests/integration/` both pass.

## Verification Plan

### Automated Tests

- [ ] **Phase gate after each step**: `cd src/tinycua-sdk && uv run pytest` — full test suite must pass.
- [ ] **Integration-only run**: `uv run pytest tests/integration/` — all integration tests discovered.
- [ ] **Makefile target**: `make test-integration` — must work without errors.

### Manual Verification

- [ ] **File count**: `tests/integration/` has exactly the expected files (11 test files + conftest + __init__).
- [ ] **No goals/**: `tests/integration/goals/` directory no longer exists.
- [ ] **No test loss**: Every original test method exists in the new structure (documented in merge analysis below).

## Proposed Changes

### Phase 1 — File Relocation and Renaming (FR-001, FR-002, FR-003, FR-005)

Files that are **simply renamed** (no merge). For each file:
- Create new file in `tests/integration/` with updated name
- Rename test class from numbered to descriptive
- Rename test methods from `test_gs_*`/`test_int_*`/`test_adv_*` to descriptive names
- Remove the old goals/ file

#### [NEW] `tests/integration/test_language_model.py`

From `goals/test_gs_01_language_model_definition.py`:

| Old Class | New Class |
|-----------|-----------|
| `TestGS01LanguageModelDefinition` | `TestLanguageModel` |

| Old Method | New Method |
|-----------|-----------|
| `test_gs_01_minimal_creation` | `test_minimal_creation` |
| `test_gs_02_full_configuration` | `test_full_configuration` |
| `test_gs_03_serialization_roundtrip` | `test_serialization_roundtrip` |
| `test_gs_04_json_export_import` | `test_json_export_import` |
| `test_gs_05_frozen_immutable` | `test_frozen_immutable` |
| `test_gs_06_env_var_substitution` | `test_env_var_substitution` |
| `test_gs_07_to_dict_excludes_none` | `test_to_dict_excludes_none` |
| `test_gs_08_provider_normalization` | `test_provider_normalization` |

#### [NEW] `tests/integration/test_agent_streaming.py`

From `goals/test_gs_04_agent_streaming.py`:

| Old Function | New Function |
|-------------|-------------|
| `test_gs_01_stream_off_returns_string` | `test_stream_off_returns_string` |
| `test_gs_02_stream_on_yields_events` | `test_stream_on_yields_events` |
| `test_gs_03_stream_with_tool_calls` | `test_stream_with_tool_calls` |

No class rename needed (module-level functions).

#### [NEW] `tests/integration/test_tool_creation.py`

From `goals/test_int_01_tool_creation.py`:

| Old Class | New Class |
|-----------|-----------|
| `TestInt01ToolCreation` | `TestToolCreation` |

| Old Method | New Method |
|-----------|-----------|
| `test_int_01_tool_schema_generation` | `test_tool_schema_generation` |
| `test_int_02_tool_invoke_keyword_args` | `test_tool_invoke_keyword_args` |
| `test_int_03_tool_invoke_positional_args` | `test_tool_invoke_positional_args` |
| `test_int_04_manual_tool_construction` | `test_manual_tool_construction` |
| `test_int_05_tool_invoke_no_callable_raises` | `test_tool_invoke_no_callable_raises` |
| `test_int_06_tool_decorator_no_args` | `test_tool_decorator_no_args` |
| `test_int_07_tool_decorator_with_dependencies` | `test_tool_decorator_with_dependencies` |
| `test_int_08_tool_from_callable_classmethod` | `test_tool_from_callable_classmethod` |
| `test_int_09_tool_dependencies_field` | `test_tool_dependencies_field` |

#### [NEW] `tests/integration/test_tool_loading.py`

From `goals/test_int_09_loading_tools_from_directory.py`:

| Old Class | New Class |
|-----------|-----------|
| `TestInt09LoadingToolsFromDirectory` | `TestToolLoading` |

| Old Method | New Method |
|-----------|-----------|
| `test_int_01_tool_directory_discovery` | `test_tool_directory_discovery` |
| `test_int_02_tool_directory_empty` | `test_tool_directory_empty` |
| `test_int_03_tool_directory_no_tools` | `test_tool_directory_no_tools` |
| `test_int_04_tool_directory_skips_prefix_underscore` | `test_tool_directory_skips_prefix_underscore` |
| `test_int_05_tool_from_config_openai_format` | `test_tool_from_config_openai_format` |
| `test_int_06_tool_directory_multiple_tools` | `test_tool_directory_multiple_tools` |

#### [NEW] `tests/integration/test_custom_agent_loop.py`

From `goals/test_adv_01_custom_agent_loop.py`:

No class rename needed (module-level functions).

| Old Function | New Function |
|-------------|-------------|
| `test_custom_loop_overrides_default_execution` | Keep as-is (already descriptive) |
| `test_custom_loop_can_respect_agent_cancellation` | Keep as-is |
| `test_custom_loop_can_use_max_iterations` | Keep as-is |
| `test_integration_custom_loop_calls_real_llm` | Keep as-is |
| `test_integration_react_loop_real_llm` | Keep as-is |
| `test_integration_streaming_lifecycle_real_llm` | Keep as-is |
| `test_integration_model_override_real_llm` | Keep as-is |

#### [NEW] `tests/integration/test_guardrail_system.py`

From `goals/test_adv_02_guardrail_system.py`:

No class rename needed (module-level functions).

| Old Function | New Function |
|-------------|-------------|
| `test_dangerous_tool_guardrail_blocks` | Keep as-is (already descriptive) |
| `test_logging_guardrail_logs_without_blocking` | Keep as-is |
| `test_multiple_guardrails_first_denial_wins` | Keep as-is |

#### [NEW] `tests/integration/test_permission_system.py`

From `goals/test_adv_03_permission_system.py`:

No class rename needed (module-level functions).

| Old Function | New Function |
|-------------|-------------|
| `test_permission_map_deny_blocks_without_guardrail` | Keep as-is (already descriptive) |
| `test_permission_map_ask_triggers_guardrail` | Keep as-is |
| `test_runtime_permission_mutation_applies_immediately` | Keep as-is |

### Phase 2 — Merging Overlapping Tests (FR-004, FR-005)

#### [MODIFY] `tests/integration/test_agent_creation.py` — Merge 1

Merge content from `goals/test_gs_02_agent_creation.py` into the existing `test_agent_creation.py`.

**Existing class**: `TestAgentCreation` (dict-based creation via `Agent.from_config()`)
**Incoming class**: `TestGS02AgentCreation` → rename to `TestAgentConstructor` (constructor-based creation via `Agent()`)

| Old Method | New Method |
|-----------|-----------|
| `test_gs_01_minimal_agent` | `test_minimal_agent` |
| `test_gs_02_named_agent` | `test_named_agent` |
| `test_gs_03_agent_with_policy` | `test_agent_with_policy` |
| `test_gs_04_agent_with_metadata` | `test_agent_with_metadata` |
| `test_gs_05_obsolete_params_rejected` | `test_obsolete_params_rejected` |
| `test_gs_06_dynamic_composition` | `test_dynamic_composition` |
| `test_gs_07_to_config` | `test_to_config` |

Add imports: `pytest`, `AgentPolicy`, `LanguageModel`, `Skill`, `tool`.

#### [NEW] `tests/integration/test_agent_export.py` — Merge 2

Merge `goals/test_int_06_exporting_agent.py` + `goals/test_int_07_loading_agent.py`.

| Old Class | New Class | Source |
|-----------|-----------|--------|
| `TestInt06ExportingAgent` | `TestAgentExport` | From `test_int_06` |
| `TestInt07LoadingAgent` | `TestAgentLoading` | From `test_int_07` |

| Old Method (int_06) | New Method |
|--------------------|-----------|
| `test_int_01_agent_dict_round_trip` | `test_agent_dict_round_trip` |
| `test_int_02_agent_json_redaction` | `test_agent_json_redaction` |
| `test_int_03_agent_yaml_redaction` | `test_agent_yaml_redaction` |
| `test_int_04_agent_json_file_round_trip` | `test_agent_json_file_round_trip` |
| `test_int_05_agent_yaml_file_round_trip` | `test_agent_yaml_file_round_trip` |

| Old Method (int_07) | New Method |
|--------------------|-----------|
| `test_int_01_yaml_export_import_round_trip` | `test_yaml_export_import_round_trip` |
| `test_int_02_yaml_file_load` | `test_yaml_file_load` |
| `test_int_03_yaml_redacted_export` | `test_yaml_redacted_export` |
| `test_int_04_yaml_exposed_export` | `test_yaml_exposed_export` |

Deduplicate the YAML redaction tests (both files tested the same thing). Keep the more comprehensive version from `test_int_06` (which tests both JSON and YAML redaction) and remove the duplicate from `test_int_07`.

#### [NEW] `tests/integration/test_skills.py` — Merge 3

Merge `goals/test_int_02_skills_creation.py` + `goals/test_int_08_loading_skills_from_directory.py` + `tests/integration/test_skills_example.py`.

| Old Class | New Class | Source |
|-----------|-----------|--------|
| `TestInt02SkillsCreation` | `TestSkillsCreation` | From `test_int_02` |
| `TestInt08LoadingSkillsFromDirectory` | `TestSkillsDirectoryLoading` | From `test_int_08` |
| `TestSkillDiscovery` | Keep as-is | From `test_skills_example.py` |
| `TestSkillRegistry` | Keep as-is | From `test_skills_example.py` |
| `TestSkillTools` | Keep as-is | From `test_skills_example.py` |
| `TestSkillsWithAgent` | Keep as-is | From `test_skills_example.py` |

| Old Method (int_02) | New Method |
|--------------------|-----------|
| `test_int_01_skill_creation` | `test_skill_creation` |
| `test_int_02_skill_to_dict` | `test_skill_to_dict` |
| `test_int_03_skill_from_dict_roundtrip` | `test_skill_from_dict_roundtrip` |
| `test_int_04_skill_default_metadata` | `test_skill_default_metadata` |
| `test_int_05_skill_frozen_immutable` | `test_skill_frozen_immutable` |
| `test_int_06_skill_registry_register_and_list` | `test_skill_registry_register_and_list` |
| `test_int_07_skill_registry_get` | `test_skill_registry_get` |
| `test_int_08_skill_registry_overwrite` | `test_skill_registry_overwrite` |

| Old Method (int_08) | New Method |
|--------------------|-----------|
| `test_int_01_skill_directory_discovery` | `test_skill_directory_discovery` |
| `test_int_02_skill_directory_empty` | `test_skill_directory_empty` |
| `test_int_03_skill_from_directory_parses_frontmatter` | `test_skill_from_directory_parses_frontmatter` |
| `test_int_04_skill_from_directory_no_frontmatter` | `test_skill_from_directory_no_frontmatter` |
| `test_int_05_skill_directory_skips_missing_skill_md` | `test_skill_directory_skips_missing_skill_md` |

| Old Method (test_skills_example.py) | New Method |
|-----------------------------------|-----------|
| Keep all as-is | Already descriptive |

Consolidate the `temp_skill_dir` fixture and `_load_skills_from_directory` helper — they are duplicated between `test_skills_example.py` and `test_int_08`. Promote to a module-level fixture or shared helper.

### Phase 3 — New End-to-End Tests (FR-006)

#### [NEW] `tests/integration/test_end_to_end.py`

Create a new end-to-end integration test covering the full SDK workflow:

- Agent creation with `LanguageModel` and tools
- Tool registration via `@tool` decorator
- Config export via `to_config()`
- Config reload via `from_dict()`/`from_config()`
- Agent run with a simple prompt (gracefully skips if LLM server unavailable)

```python
"""End-to-end integration tests for full SDK workflow."""

import pytest
from tinycua_sdk import Agent, LanguageModel, tool


class TestEndToEnd:
    """Full workflow integration tests."""

    def test_agent_create_export_reload_roundtrip(self):
        """Create agent, export config, reload, verify equivalence."""
        @tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        agent = Agent(
            name="e2e-test",
            instructions="You are helpful.",
            llm_model=LanguageModel(model_name="gpt-4o"),
            tools=[add],
        )
        config = agent.to_config()
        restored = Agent.from_dict(config)
        assert restored.name == agent.name
        assert restored.instructions == agent.instructions

    @pytest.mark.asyncio
    async def test_agent_run_simple(self):
        """Run agent with simple prompt (skips if LLM unavailable)."""
        import os
        agent = Agent(
            name="hello-agent",
            instructions="You are helpful.",
            llm_model=LanguageModel(
                provider=os.environ.get("TINYCUA_PROVIDER", "openai-compatible"),
                model_name=os.environ.get("TINYCUA_MODEL", "qwen/qwen3.5-9b"),
                base_url=os.environ.get("TINYCUA_BASE_URL", "http://localhost:1234/v1"),
                api_key=os.environ.get("LLM_API_KEY", "dummy"),
            ),
        )
        try:
            response = await agent.run("Say 'hello' in one word.")
            assert isinstance(response, str)
            assert len(response) > 0
        except Exception:
            pytest.skip("LLM endpoint not available")

    def test_tool_invocation_via_executor(self):
        """Tool can be invoked directly through ToolExecutor."""
        from tinycua_sdk.agent.executor import ToolExecutor

        @tool
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        agent = Agent(llm_model=LanguageModel())
        result = ToolExecutor.execute(greet, {"name": "World"}, agent)
        assert result == "Hello, World!"
```

### Phase 4 — Cleanup: Remove `goals/` directory (FR-003)

#### [DELETE] `tests/integration/goals/`

Remove the entire `tests/integration/goals/` directory and all its contents after Phases 1-3 are complete and verified.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tests/integration/goals/` | DELETE | Entire directory removed after all files migrated |
| `tests/integration/test_language_model.py` | NEW | Renamed from `test_gs_01` |
| `tests/integration/test_agent_streaming.py` | NEW | Renamed from `test_gs_04` |
| `tests/integration/test_tool_creation.py` | NEW | Renamed from `test_int_01` |
| `tests/integration/test_tool_loading.py` | NEW | Renamed from `test_int_09` |
| `tests/integration/test_custom_agent_loop.py` | NEW | Renamed from `test_adv_01` |
| `tests/integration/test_guardrail_system.py` | NEW | Renamed from `test_adv_02` |
| `tests/integration/test_permission_system.py` | NEW | Renamed from `test_adv_03` |
| `tests/integration/test_agent_creation.py` | MODIFY | Expanded with merged content from `test_gs_02` |
| `tests/integration/test_agent_export.py` | NEW | Merge of `test_int_06` + `test_int_07` |
| `tests/integration/test_skills.py` | NEW | Merge of `test_int_02` + `test_int_08` + `test_skills_example.py` |
| `tests/integration/test_end_to_end.py` | NEW | End-to-end integration tests |

## Dependencies

### External Dependencies

No new dependencies. All imports already exist in the codebase.

### Internal Dependencies

- [ ] Phase 1 must complete before Phase 4 (goals/ deletion)
- [ ] Phase 2 builds on Phase 1 (merged files created alongside renamed files)
- [ ] Phase 3 is independent of Phases 1-2
- [ ] Phase 4 must wait until Phases 1-3 are verified

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Missed test scenario during merge | High | Audit each merged file against original after creation — every original test method must be present by name |
| Typo in renamed method causes test to not run | High | Run full suite after each phase — pytest will fail to find tests if method names don't start with `test_` |
| Import error in relocated file | High | Run `uv run pytest tests/integration/` after each file move — import errors surface immediately |
| `_load_skills_from_directory` helper duplicated after merge | Medium | Consolidate into a single module-level function in `test_skills.py` |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-16*
