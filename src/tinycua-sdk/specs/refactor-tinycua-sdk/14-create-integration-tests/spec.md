# Stage 14 — Create Integration Tests

## Objective

Write integration tests based on the working examples from Stage 13.

## Test Structure

```
tests/integration/
  test_agent_creation.py      — From config, templates
  test_tool_execution.py      — Tool invoke, schema, composition
  test_skills_integration.py  — Skill.load(), SkillRegistry, composition
  test_loop_execution.py      — Agent loop with mocked LLM
```

## Test Requirements

### test_agent_creation.py
- `test_from_dict_minimal` — Create agent from minimal dict config
- `test_from_dict_with_tools` — Create agent with tools from config
- `test_from_json_file` — Load agent from JSON file
- `test_from_yaml_file` — Load agent from YAML file
- `test_config_round_trip_file` — Serialize to file and restore
- `test_coder_template` — Load coder template
- `test_researcher_template` — Load researcher template
- `test_assistant_template` — Load assistant template
- `test_template_with_llm_override` — Override LLMModel in template
- `test_invalid_template` — Unknown template raises ValueError

### test_tool_execution.py
- `test_tool_invoked_during_run` — Tool is called during agent run
- `test_multiple_tools` — Multiple tools available
- `test_tool_with_defaults` — Tool with default parameters
- `test_no_tools` — Agent without tools still runs
- `test_tool_direct_invoke` — Direct Tool.invoke()
- `test_tool_schema_for_api` — Schema generation for API calls
- `test_tool_error_handling` — Tool exceptions handled gracefully
- `test_add_tools_then_run` — Add tools after construction
- `test_add_multiple_tools` — Add list of tools

### test_skills_integration.py
- `test_add_single_skill` — Add one skill
- `test_add_multiple_skills` — Add list of skills
- `test_skill_at_construction` — Skills at Agent construction
- `test_agent_with_skill_run` — Run with skill
- `test_skill_load` — Skill.load(markdown_text)
- `test_skill_registry_load` — Load skills into registry
- `test_registry_not_singleton` — Independent registries
- `test_filter_skills_by_category` — Filter in registry
- `test_skill_config_round_trip` — Serialize and deserialize skill

### test_loop_execution.py
- `test_run_basic` — Basic run with mocked LLM
- `test_run_with_messages` — Pass message history
- `test_run_stream` — Streaming response
- `test_run_with_tools` — Tool calling in loop
- `test_run_stateless` — Multiple runs are independent

## Mock Strategy

Integration tests should mock the LLM client to avoid requiring a running LLM server:

```python
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_llm_client():
    with patch("tinycua_sdk.agent.executor.LLMClient") as mock:
        mock.return_value.chat = AsyncMock(return_value="Mocked response")
        yield mock
```

## Acceptance Criteria

- [ ] All integration tests pass.
- [ ] Tests cover the examples from Stage 13.
- [ ] Tests do not require external services (mocked LLM).
- [ ] Tests verify statelessness (no side effects between runs).

## Dependencies

- **Requires**: Stage 13 (examples must exist and be working)
