# Stage 02 — New Unit Tests

## Objective

Write unit tests that define the target API and behavior for the refactored stateless SDK. These tests will initially fail (they test code that doesn't exist yet) and serve as the success criteria for implementation stages.

## Test Structure

```
tests/
  unit/
    test_agent.py              — Agent construction, mutation, run(), config
    test_tool.py               — @tool decorator, Tool.invoke(), schema
    test_skills.py             — Skill dataclass, Skill.load(), SkillRegistry
    test_config.py             — AgentConfig, SDKConfig, LLMModel, BackendConfig
    test_agent_templates.py    — Template loading with new config
```

## test_agent.py Requirements

### Construction Tests
- `test_default_construction` — Agent() with defaults
- `test_full_construction` — All parameters
- `test_system_prompt_on_llm_model` — LLMModel carries system_prompt
- `test_no_system_prompt_on_agent` — Agent() rejects system_prompt param
- `test_no_session_id_on_agent` — Agent() rejects session_id param
- `test_no_memory_params_on_agent` — Agent() rejects short_term_memory/long_term_memory
- `test_no_planning_prompt_on_agent` — Agent() rejects planning_prompt param
- `test_no_model_string_on_agent` — Agent() rejects model/provider/base_url/api_key params

### Tool/Skill Mutation Tests
- `test_add_single_tool` — add_tools(tool) works
- `test_add_multiple_tools` — add_tools([tool1, tool2]) works
- `test_add_single_skill` — add_skills(skill) works
- `test_add_multiple_skills` — add_skills([skill1, skill2]) works

### Config Serialization Tests
- `test_to_config` — Agent.to_config() returns correct dict
- `test_from_config_dict` — Agent.from_config({...}) works
- `test_config_round_trip` — to_config -> from_config produces equivalent Agent

### Run Tests (mocked)
- `test_run_basic` — Agent.run("query") returns str
- `test_run_with_messages` — Agent.run("query", messages=[...]) passes messages
- `test_run_with_instructions` — Agent.run("query", instructions="...") works
- `test_run_stream` — Agent.run("query", stream=True) returns AsyncIterator
- `test_run_with_tools` — Tool is available during run

### Statelessness Tests
- `test_no_internal_message_history` — Agent does not remember previous runs
- `test_no_singleton_registry` — ToolRegistry import fails
- `test_explicit_skill_registry` — SkillRegistry instances are independent

### Template Tests
- `test_from_template` — Agent.from_template("coder") works
- `test_from_template_with_llm_override` — Template with LLMModel override
- `test_invalid_template` — Raises ValueError for unknown template

## test_tool.py Requirements

- `test_decorator_returns_tool_instance`
- `test_decorator_with_dependencies`
- `test_tool_schema_generation`
- `test_tool_invoke`
- `test_tool_invoke_with_defaults`
- `test_tool_invoke_missing_required`
- `test_tool_bundle`
- `test_no_global_registry`
- `test_tool_source_captured`
- `test_tool_from_config`

## test_skills.py Requirements

- `test_default_construction`
- `test_full_construction`
- `test_skill_to_dict`
- `test_skill_load` — Skill.load(markdown_text) works
- `test_skill_registry_explicit_instance`
- `test_skill_registry_not_singleton`
- `test_skill_registry_register_and_get`
- `test_skill_registry_list_skills`
- `test_skill_registry_filter_by_category`

## test_config.py Requirements

### LLMModel
- `test_defaults`
- `test_custom_values`
- `test_to_dict`
- `test_from_dict`
- `test_immutable`
- `test_no_io_methods`

### AgentConfig
- `test_defaults`
- `test_to_dict`
- `test_from_dict`
- `test_no_system_prompt_field`
- `test_no_session_id_field`
- `test_no_memory_fields`

### BackendConfig
- `test_defaults`
- `test_remote`
- `test_to_dict`

### SDKConfig
- `test_defaults`
- `test_no_memory_field`
- `test_no_session_field`
- `test_no_environment_field`
- `test_from_env`
- `test_from_yaml`

### Round Trip
- `test_llm_model_round_trip`
- `test_agent_config_round_trip`

## Acceptance Criteria

- [ ] All new test files exist in `tests/unit/`.
- [ ] Tests compile (no syntax errors) when run with `pytest --collect-only`.
- [ ] Tests initially fail because the target code doesn't exist yet.
- [ ] Each test has a clear, descriptive name explaining what behavior it validates.
- [ ] Tests use only the new stateless API (no singletons, no stores, no session/memory references).

## Dependencies

- **Requires**: Stage 01 (legacy tests removed, so no name collisions)
