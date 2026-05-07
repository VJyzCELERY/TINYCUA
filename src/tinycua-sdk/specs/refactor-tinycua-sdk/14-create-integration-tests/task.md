# Tasks: Stage 14 — Create Integration Tests

Implementation tasks for creating integration tests based on Stage 13 working examples. Check off items as completed.

## Setup Phase

- [ ] Create `tests/integration/__init__.py` <!-- id: 0 -->
- [ ] Create `tests/integration/conftest.py` with `mock_llm_client` and `mock_llm_with_tool_calls` fixtures <!-- id: 1 -->

## Test Implementation Phase

- [ ] Write `tests/integration/test_agent_creation.py` <!-- id: 2 -->
  - [ ] `test_from_dict_minimal`
  - [ ] `test_from_dict_with_tools`
  - [ ] `test_from_json_file`
  - [ ] `test_from_yaml_file`
  - [ ] `test_config_round_trip_file`
  - [ ] `test_coder_template`
  - [ ] `test_researcher_template`
  - [ ] `test_assistant_template`
  - [ ] `test_template_with_llm_override`
  - [ ] `test_invalid_template`
- [ ] Write `tests/integration/test_tool_execution.py` <!-- id: 3 -->
  - [ ] `test_tool_invoked_during_run`
  - [ ] `test_multiple_tools`
  - [ ] `test_tool_with_defaults`
  - [ ] `test_no_tools`
  - [ ] `test_tool_direct_invoke`
  - [ ] `test_tool_schema_for_api`
  - [ ] `test_tool_error_handling`
  - [ ] `test_add_tools_then_run`
  - [ ] `test_add_multiple_tools`
- [ ] Write `tests/integration/test_skills_integration.py` <!-- id: 4 -->
  - [ ] `test_add_single_skill`
  - [ ] `test_add_multiple_skills`
  - [ ] `test_skill_at_construction`
  - [ ] `test_agent_with_skill_run`
  - [ ] `test_skill_load`
  - [ ] `test_skill_registry_load`
  - [ ] `test_registry_not_singleton`
  - [ ] `test_filter_skills_by_category`
  - [ ] `test_skill_config_round_trip`
- [ ] Write `tests/integration/test_loop_execution.py` <!-- id: 5 -->
  - [ ] `test_run_basic`
  - [ ] `test_run_with_messages`
  - [ ] `test_run_stream`
  - [ ] `test_run_with_tools`
  - [ ] `test_run_stateless`
  - [ ] `test_custom_loop`
  - [ ] `test_base_loop_default`

## Testing Phase

- [ ] Run `pytest tests/integration/ -v` and verify all 33 tests pass <!-- id: 6 -->
- [ ] Verify tests do not require external LLM server (all mocked) <!-- id: 7 -->
- [ ] Verify statelessness (no side effects between runs) <!-- id: 8 -->
- [ ] Check test coverage for Stage 13 examples <!-- id: 9 -->

## Verification Phase

- [ ] Confirm no import errors across all integration test files <!-- id: 10 -->
- [ ] Confirm fixtures in `conftest.py` are reused correctly <!-- id: 11 -->

## Review and Merge

- [ ] Review test code for clarity and maintainability <!-- id: 12 -->
- [ ] Merge to main branch <!-- id: 13 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement-plan` to execute these tasks*
*Last updated: 2026-04-29*
