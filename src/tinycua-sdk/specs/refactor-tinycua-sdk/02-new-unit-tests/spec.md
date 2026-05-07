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
- `test_agent_minimal_construction` — Agent() with defaults
- `test_agent_full_construction` — All parameters
- `test_system_prompt_on_llm_model` — LLMModel carries system_prompt
- `test_agent_rejects_system_prompt` — Agent() rejects system_prompt param
- `test_agent_rejects_session_id` — Agent() rejects session_id param
- `test_agent_rejects_short_term_memory` — Agent() rejects short_term_memory param
- `test_agent_rejects_long_term_memory` — Agent() rejects long_term_memory param
- `test_agent_rejects_planning_prompt` — Agent() rejects planning_prompt param
- `test_agent_rejects_model` — Agent() rejects model param
- `test_agent_rejects_provider` — Agent() rejects provider param
- `test_agent_rejects_base_url` — Agent() rejects base_url param
- `test_agent_rejects_api_key` — Agent() rejects api_key param
- `test_agent_rejects_mode` — Agent() rejects mode param
- `test_agent_rejects_backend_url` — Agent() rejects backend_url param

### Tool/Skill Mutation Tests
- `test_add_tools_single` — add_tools(tool) works
- `test_add_tools_list` — add_tools([tool1, tool2]) works
- `test_add_skills_single` — add_skills(skill) works
- `test_add_skills_list` — add_skills([skill1, skill2]) works

### Config Serialization Tests
- `test_agent_to_config` — Agent.to_config() returns correct dict
- `test_agent_from_config_dict` — Agent.from_config({...}) works
- `test_agent_config_round_trip` — to_config -> from_config produces equivalent Agent

### Run Tests (mocked)
- `test_agent_run_basic` — Agent.run("query") returns str
- `test_agent_run_with_messages` — Agent.run("query", messages=[...]) passes messages
- `test_agent_run_with_instructions` — Agent.run("query", instructions="...") works
- `test_agent_run_stream` — Agent.run("query", stream=True) returns AsyncIterator
- `test_agent_run_with_tools` — Tool is available during run

### Statelessness Tests
- `test_no_internal_message_history` — Agent does not remember previous runs
- `test_no_singleton_registry` — ToolRegistry import fails

### Template Tests
- `test_coder_template_exists` — Agent.from_config("coder") works
- `test_researcher_template_exists` — Agent.from_config("researcher") works
- `test_template_llm_override` — Template with LLMModel override
- `test_invalid_template_raises` — Raises ValueError for unknown template

## test_tool.py Requirements

- `test_decorator_returns_tool_instance`
- `test_decorator_with_dependencies`
- `test_decorator_without_parentheses`
- `test_tool_schema_generation`
- `test_tool_schema_with_defaults`
- `test_tool_invoke`
- `test_tool_invoke_with_defaults`
- `test_tool_invoke_missing_required`
- `test_tool_to_config`
- `test_tool_to_bundle`
- `test_tool_from_config`
- `test_tool_source_captured`
- `test_no_global_registry`

## test_skills.py Requirements

- `test_skill_default_construction`
- `test_skill_full_construction`
- `test_skill_to_dict`
- `test_skill_load_markdown` — Skill.load(markdown_text) works
- `test_skill_load_without_frontmatter`
- `test_registry_explicit_instance`
- `test_registry_not_singleton`
- `test_registry_register_and_get`
- `test_registry_list_skills`
- `test_registry_filter_by_category`

## test_loop.py Requirements

- `test_base_loop_default_construction`
- `test_base_loop_custom_max_iterations`
- `test_base_loop_extensible`
- `test_resolve_loop_none`
- `test_resolve_loop_instance_passthrough`
- `test_resolve_loop_rejects_react_string`
- `test_resolve_loop_dict`

## test_config.py Requirements

### LLMModel
- `test_llm_model_defaults`
- `test_llm_model_custom_values`
- `test_llm_model_to_dict`
- `test_llm_model_from_dict`
- `test_llm_model_immutable`
- `test_llm_model_no_io_methods`
- `test_system_prompt_on_llm_model`

### AgentConfig
- `test_agent_config_defaults`
- `test_agent_config_to_dict`
- `test_agent_config_from_dict`
- `test_agent_config_no_system_prompt_field`
- `test_agent_config_no_session_id_field`
- `test_agent_config_no_memory_fields`

### BackendConfig
- `test_backend_config_defaults`
- `test_backend_config_remote`
- `test_backend_config_to_dict`

### SDKConfig
- `test_sdk_config_defaults`
- `test_sdk_config_no_memory_field`
- `test_sdk_config_no_session_field`
- `test_sdk_config_no_environment_field`
- `test_sdk_config_from_env`
- `test_sdk_config_from_yaml`

### Round Trip
- `test_llm_model_round_trip`
- `test_agent_config_round_trip`
- `test_backend_config_round_trip`

## Mock Strategy

All tests that call `Agent.run()` must mock the LLM client at the public executor boundary to avoid coupling tests to internal implementation details:

```python
from unittest.mock import patch, AsyncMock

with patch("tinycua_sdk.agent.executor.LLMClient") as MockClient:
    mock_instance = MockClient.return_value
    mock_instance.chat = AsyncMock(return_value="Mocked")
```

## Acceptance Criteria

- [ ] All new test files exist in `tests/unit/`.
- [ ] Tests compile (no syntax errors) when run with `pytest --collect-only`.
- [ ] Tests initially fail because the target code doesn't exist yet.
- [ ] Each test has a clear, descriptive name explaining what behavior it validates.
- [ ] Tests use only the new stateless API (no singletons, no stores, no session/memory references).

## Dependencies

- **Requires**: Stage 01 (legacy tests removed, so no name collisions)
