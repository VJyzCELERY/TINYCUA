# Implementation: Stage 14 — Create Integration Tests

Write integration tests based on the working examples from Stage 13. These tests verify that the SDK components work together correctly, mocking external dependencies (LLM server) to remain fast and deterministic.

## Context

- **Spec Reference**: spec.md — 33 test cases across 4 test files + conftest.py fixtures
- **Design Reference**: design.md — detailed test code, mock strategy, running instructions
- **Priority**: P1
- **Estimated Effort**: M

## Proposed Changes

### tests/integration/ Directory

#### [NEW] tests/integration/__init__.py

- **[Description]**: Package init for integration tests
- **[Rationale]**: Makes tests/integration a Python package

#### [NEW] tests/integration/conftest.py

- **[Description]**: Shared pytest fixtures for integration tests
- **[Rationale]**: Centralizes mock LLM setup; avoids duplication across test files
- **Fixtures**:
  - `mock_llm_client` — patches `tinycua_sdk.agent.executor.LLMClient.chat` to return `"Mocked response"`
  - `mock_llm_with_tool_calls` — returns tool call JSON then final response via `side_effect`

#### [NEW] tests/integration/test_agent_creation.py

- **[Description]**: 9 tests for agent construction from config, files, and templates
- **[Rationale]**: Covers `Agent.from_config()` with dict, JSON, YAML, templates, and round-trip serialization
- **Tests**:
  - `test_from_dict_minimal` — minimal dict config
  - `test_from_dict_with_tools` — config with tools list
  - `test_from_json_file` — load from JSON file via `tmp_path`
  - `test_from_yaml_file` — load from YAML file via `tmp_path`
  - `test_config_round_trip_file` — serialize to file and restore
  - `test_coder_template` — load built-in coder template
  - `test_researcher_template` — load built-in researcher template
  - `test_assistant_template` — load built-in assistant template
  - `test_template_with_llm_override` — override LLMModel after template load
  - `test_invalid_template` — unknown template raises `ValueError`

#### [NEW] tests/integration/test_tool_execution.py

- **[Description]**: 9 tests for tool invocation, schema, composition, and error handling
- **[Rationale]**: Covers `@tool` decorator, `Tool.invoke()`, schema generation, and agent tool integration
- **Tests**:
  - `test_tool_invoked_during_run` — tool called during mocked agent run
  - `test_multiple_tools` — multiple tools available on agent
  - `test_tool_with_defaults` — tool with default parameters
  - `test_no_tools` — agent without tools still runs
  - `test_tool_direct_invoke` — direct `Tool.invoke()` call
  - `test_tool_schema_for_api` — schema generation for API calls
  - `test_tool_error_handling` — tool exceptions handled gracefully
  - `test_add_tools_then_run` — add tools after construction
  - `test_add_multiple_tools` — add list of tools

#### [NEW] tests/integration/test_skills_integration.py

- **[Description]**: 9 tests for Skill loading, registry, and agent composition
- **[Rationale]**: Covers `Skill.load()`, `SkillRegistry`, and skill-agent integration
- **Tests**:
  - `test_add_single_skill` — add one skill to agent
  - `test_add_multiple_skills` — add list of skills
  - `test_skill_at_construction` — skills passed at Agent construction
  - `test_agent_with_skill_run` — run agent with skill attached
  - `test_skill_load` — `Skill.load(markdown_text)` with YAML frontmatter
  - `test_skill_registry_load` — load skills into registry
  - `test_registry_not_singleton` — registries are independent (no global singleton)
  - `test_filter_skills_by_category` — filter registry by category
  - `test_skill_config_round_trip` — serialize and deserialize skill

#### [NEW] tests/integration/test_loop_execution.py

- **[Description]**: 7 tests for agent loop execution with mocked LLM
- **[Rationale]**: Covers `Agent.run()`, message passing, streaming, tools in loop, statelessness, and custom loops
- **Tests**:
  - `test_run_basic` — basic run with mocked LLM
  - `test_run_with_messages` — pass message history
  - `test_run_stream` — streaming response
  - `test_run_with_tools` — tool calling in loop
  - `test_run_stateless` — multiple runs are independent
  - `test_custom_loop` — agent with custom `BaseLoop` subclass
  - `test_base_loop_default` — default `BaseLoop()` used when `loop=None`

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| tests/integration/ | New | 4 test files + conftest.py + __init__.py |
| tests/integration/conftest.py | New | Shared mock LLM fixtures |

## Data Model Changes

None. Tests consume existing public API.

## API Changes

None. Tests consume existing public API.

## Verification Plan

### Automated Tests

- [ ] All 33 integration tests pass (`pytest tests/integration/ -v`)
- [ ] Tests run without import errors
- [ ] Tests do not require external services (mocked LLM)
- [ ] Tests verify statelessness (no side effects between runs)

### Manual Verification

- [ ] Review test coverage for Stage 13 examples
- [ ] Confirm fixtures in `conftest.py` are reused across files

## Rollout Strategy

1. **Phase 1** (Create test infrastructure): Write `__init__.py` and `conftest.py` with fixtures
2. **Phase 2** (Write agent creation tests): `test_agent_creation.py`
3. **Phase 3** (Write tool execution tests): `test_tool_execution.py`
4. **Phase 4** (Write skills integration tests): `test_skills_integration.py`
5. **Phase 5** (Write loop execution tests): `test_loop_execution.py`
6. **Phase 6** (Run and verify): Execute full integration suite, fix any failures

## Dependencies

### Internal Dependencies

- [ ] Depends on Stage 13 (examples must exist and be working)
- [ ] Blocks: None

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SDK API not yet stable from Stage 11/12/13 | Medium | Verify imports against actual refactored SDK before finalizing tests |
| Mock paths incorrect if executor module moved | Medium | Check actual `LLMClient` location in SDK; adjust patch path in conftest.py |
| Async test setup issues | Low | Use `pytest-asyncio` and `@pytest.mark.asyncio` on all async tests |

---

*Generated from spec.md and design.md*
*Last updated: 2026-04-29*
