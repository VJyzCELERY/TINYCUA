# Stage 4: Skills & Composition — Specification

**Status**: Draft | In Progress | Complete
**Created**: 2026-05-02
**Last Updated**: 2026-05-02
**Subproject(s) Affected**: tinycua-sdk

## Objective
Skills inject their instructions into the agent's system prompt. Agents can use both tools and skills together.

## Guiding Principles
All stages adhere to the principles defined in [`ROADMAP.md#principles`](../../docs/ROADMAP.md#principles).

## References
- [`goals/intermediate/04_agent_with_skills.py`](../goals/intermediate/04_agent_with_skills.py)
- [`goals/intermediate/05_agent_with_tools_and_skills.py`](../goals/intermediate/05_agent_with_tools_and_skills.py)

## Requirements

### R-4.1: Skill Prompt Injection

When `Agent.run()` starts, the effective system prompt is built as:
1. `instructions` (agent-level, or override from run)
2. Each skill's `instructions` (in registration order)

Format:
```
<agent instructions>

[<skill_name>]
<skill instructions>

[<skill_name>]
<skill instructions>
```

**Key rule:** Skills are **metadata-only**. They do NOT auto-resolve tools. Tools must always be composed explicitly via `Agent.add_tools()`.

### R-4.2: Combined Usage

Agent constructor accepts both `tools` and `skills` simultaneously:
```python
agent = Agent(
    name="research_coder",
    instructions="You are a research assistant that can also read code.",
    llm_model=LanguageModel(...),
    tools=[web_search, read_file],
    skills=[research_skill, code_skill],
)
```

### R-4.3: Dynamic add_skills

`add_skills(skill_or_list)` works after creation and takes effect on the next `run()`.

## Success Criteria

Each success criterion must be validated by running the specified target file(s).

Format: [ ] Success Criteria Description - Target File(s) - Expected Output - How to validate

- [ ] Skill Instructions in System Prompt - tests/integration/goals/test_int_04_agent_with_skills.py - PASS - `print('PASS')`
  Description: Agent with skills includes skill instructions in the prompt.

- [ ] Multiple Skills - tests/integration/goals/test_int_04_agent_with_skills.py - PASS - `print('PASS')`
  Description: Multiple skills inject in order.

- [ ] Dynamic add_skills - tests/integration/goals/test_int_04_agent_with_skills.py - PASS - `print('PASS')`
  Description: Skills added after creation work on next run.

- [ ] Combined Tools + Skills - tests/integration/goals/test_int_05_agent_with_tools_and_skills.py - PASS - `print('PASS')`
  Description: Agent with both tools and skills works.

- [ ] Integration Tests Pass - tests/integration/goals/test_int_04_agent_with_skills.py, tests/integration/goals/test_int_05_agent_with_tools_and_skills.py - 2 passed, 0 failed - pytest -v

## Integration Test Files
- `tests/integration/goals/test_int_04_agent_with_skills.py`
- `tests/integration/goals/test_int_05_agent_with_tools_and_skills.py`
