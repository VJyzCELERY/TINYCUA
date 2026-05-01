# Stage 4: Skills & Composition — Specification

## Objective
Skills inject their instructions into the agent's system prompt. Agents can use both tools and skills together.

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

### SC-4.1: Skill Instructions in System Prompt
**What:** Agent with skills includes skill instructions in the prompt.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, Skill

coding = Skill(name='python_expert', description='Write Python', instructions='Follow PEP 8.')
a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'), skills=[coding])
r = asyncio.run(a.run('Write a hello world function.'))
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-4.2: Multiple Skills
**What:** Multiple skills inject in order.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, Skill

s1 = Skill(name='s1', description='d1', instructions='Instruction A.')
s2 = Skill(name='s2', description='d2', instructions='Instruction B.')
a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'), skills=[s1, s2])
r = asyncio.run(a.run('Hello'))
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-4.3: Dynamic add_skills
**What:** Skills added after creation work on next run.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, Skill

a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'))
docs = Skill(name='documentarian', description='Docs', instructions='Use Google-style docstrings.')
a.add_skills(docs)
r = asyncio.run(a.run('Document this.'))
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-4.4: Combined Tools + Skills
**What:** Agent with both tools and skills works.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, Skill, tool

@tool
def web_search(query: str) -> str:
    return f'[Results for {query}]'

s = Skill(name='researcher', description='Research', instructions='Always cite sources.')
a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'), tools=[web_search], skills=[s])
r = asyncio.run(a.run('What is FastAPI?'))
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-4.5: Integration Tests Pass
**What:** Both Stage 4 integration tests pass.  
**How to check:**
```bash
cd src/tinycua-sdk && pytest tests/integration/goals/test_int_04_agent_with_skills.py tests/integration/goals/test_int_05_agent_with_tools_and_skills.py -v
```
**Pass if:** 2 passed, 0 failed.

## Integration Test Files
- `tests/integration/goals/test_int_04_agent_with_skills.py`
- `tests/integration/goals/test_int_05_agent_with_tools_and_skills.py`
