# Stage 2: Agent Configuration & Creation — Specification

## Objective
An `Agent` can be instantiated and configured with all v2 parameters, but cannot yet execute. The constructor shape, config model, and serialization of config must match the spec exactly.

## Reference
- [`goals/getting-started/02_agent_creation.py`](../goals/getting-started/02_agent_creation.py)

## Requirements

### R-2.1: AgentPolicy

Behavior-only settings. No LLM inference parameters.

```python
class AgentPolicy(BaseModel):
    max_tool_calls: int = 10
    parallel_tool_calls: bool = True
```

**Removed from v1:** `temperature` (lives on `LanguageModel` only).

### R-2.2: AgentConfig

```python
class AgentConfig(BaseModel):
    name: str = "assistant"
    instructions: str = ""
    llm_model: LanguageModel
    tools: list[Tool] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    policy: AgentPolicy = Field(default_factory=AgentPolicy)
    metadata: dict = Field(default_factory=dict)
    loop: BaseLoop | None = None
    tool_permissions: dict[str, Literal["allow", "ask", "deny"]] = Field(default_factory=dict)
    approval_workflow: ApprovalWorkflow | None = None
```

### R-2.3: Agent Constructor

```python
def __init__(
    self,
    name: str = "assistant",
    instructions: str = "",
    llm_model: LanguageModel | None = None,
    tools: list[Tool] | None = None,
    skills: list[Skill] | None = None,
    policy: AgentPolicy | None = None,
    metadata: dict | None = None,
    loop: BaseLoop | None = None,
    tool_permissions: dict[str, Literal["allow", "ask", "deny"]] | None = None,
    approval_workflow: ApprovalWorkflow | None = None,
    **kwargs,
):
```

**Default behavior:**
- If `llm_model` is `None`, create `LanguageModel()` with defaults.
- If `policy` is `None`, create `AgentPolicy()` with defaults.
- If `tools` is `None`, use empty list.
- If `skills` is `None`, use empty list.
- If `metadata` is `None`, use empty dict.
- If `tool_permissions` is `None`, use empty dict.

**Obsolete parameter rejection:**
- Any keyword in `kwargs` that matches an obsolete parameter name raises `TypeError` with a clear message.
- Obsolete names: `system_prompt`, `model`, `provider`, `base_url`, `api_key`, `mode`, `backend_url`, `backend_api_key`, `backend_headers`, `agent_id`, `planning_prompt`, `short_term_memory`, `long_term_memory`, `session_id`, `sub_agents`, `max_depth`, `strip_thinking`, `backend`.

### R-2.4: Dynamic Composition

- `add_tools(tool_or_list: Tool | list[Tool]) -> None` — appends to `self.config.tools`.
- `add_skills(skill_or_list: Skill | list[Skill]) -> None` — appends to `self.config.skills`.
- Both mutate in place.

### R-2.5: Config Serialization

- `to_config() -> dict` — returns a plain dict representation of the agent's configuration. Includes nested serialization of `llm_model`, `tools`, `skills`, `policy`.

## Success Criteria

### SC-2.1: Minimal Agent Creation
**What:** `Agent()` with no args creates a valid agent.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
from tinycua_sdk import Agent
a = Agent()
assert a.name == 'assistant'
assert a.llm_model.model_name == 'gpt-4o-mini'
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-2.2: Named Agent with Instructions
**What:** Agent with custom name and instructions.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
from tinycua_sdk import Agent, LanguageModel
a = Agent(name='greeter', instructions='Say hello.', llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'))
assert a.name == 'greeter'
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-2.3: Agent with Policy
**What:** Policy settings are stored correctly.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
from tinycua_sdk import Agent
a = Agent(policy={'max_tool_calls': 15, 'parallel_tool_calls': True})
assert a.policy.max_tool_calls == 15
assert a.policy.parallel_tool_calls is True
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-2.4: Agent with Metadata
**What:** Consumer-defined metadata is preserved.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
from tinycua_sdk import Agent
a = Agent(metadata={'team': 'platform', 'version': '2.1.0'})
assert a.metadata['team'] == 'platform'
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-2.5: Obsolete Parameters Rejected
**What:** Passing obsolete params raises `TypeError`.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
from tinycua_sdk import Agent
try:
    Agent(system_prompt='hello')
except TypeError:
    print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-2.6: Dynamic add_tools / add_skills
**What:** Tools and skills can be added after creation.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
from tinycua_sdk import Agent, Skill, tool

@tool
def calc(expr: str) -> str:
    return str(eval(expr))

s = Skill(name='math', description='Math help', instructions='Show work.')
a = Agent()
a.add_tools(calc)
a.add_skills(s)
assert len(a.tools) == 1
assert len(a.skills) == 1
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-2.7: to_config Serializes
**What:** `to_config()` returns a dict with all fields.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
from tinycua_sdk import Agent
a = Agent(name='test', instructions='help')
c = a.to_config()
assert c['name'] == 'test'
assert c['instructions'] == 'help'
assert 'llm_model' in c
assert 'tools' in c
assert 'skills' in c
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-2.8: Integration Test Pass
**What:** `test_gs_02_agent_creation.py` passes.  
**How to check:**
```bash
cd src/tinycua-sdk && pytest tests/integration/goals/test_gs_02_agent_creation.py -v
```
**Pass if:** 1 passed, 0 failed.

## Integration Test File
- `tests/integration/goals/test_gs_02_agent_creation.py`
