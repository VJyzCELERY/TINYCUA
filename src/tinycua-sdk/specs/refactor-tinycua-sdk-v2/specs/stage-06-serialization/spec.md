# Stage 6: Serialization & Directory Loading — Specification

## Objective
Agents, skills, and tools can be exported and imported. Skills and tools can be bulk-loaded from directories.

## References
- [`goals/intermediate/06_exporting_agent.py`](../goals/intermediate/06_exporting_agent.py)
- [`goals/intermediate/07_loading_agent.py`](../goals/intermediate/07_loading_agent.py)
- [`goals/intermediate/08_loading_skills_from_directory.py`](../goals/intermediate/08_loading_skills_from_directory.py)
- [`goals/intermediate/09_loading_tools_from_directory.py`](../goals/intermediate/09_loading_tools_from_directory.py)

## Requirements

### R-6.1: Agent Serialization

- `Agent.to_config() -> dict` — plain dict with all serializable fields.
- `Agent.to_json(indent: int = 2, redact_sensitive: bool = True) -> str` — JSON string.
- `Agent.to_yaml(redact_sensitive: bool = True) -> str` — YAML string.
- `Agent.from_json_file(path: str | Path) -> Agent` — load from JSON file.
- `Agent.from_yaml_file(path: str | Path) -> Agent` — load from YAML file.
- `Agent.from_dict(config: dict) -> Agent` — load from in-memory dict.

**Redaction rules:**
- When `redact_sensitive=True`, `api_key` is replaced with `"***"`.
- When `redact_sensitive=False`, full `api_key` is preserved.

**Round-trip parity:**
- `Agent.from_dict(agent.to_config())` must produce an equivalent agent.
- Equivalent means: same `name`, `instructions`, `llm_model` params, same tools count, same skills count.
- Custom `loop` instances cannot be serialized; they default to `None` on load.

### R-6.2: Skill Directory Loading

- `Skill.load_directory(path: Path) -> list[Skill]` — discovers all immediate subdirectories containing `SKILL.md`, parses each into a `Skill`.
- `Skill.from_directory(path: Path) -> Skill` — loads a single skill folder.

**Directory layout:**
```
skills/
├── web_research/
│   ├── SKILL.md
│   └── utils.py          # ignored by loader
├── data_analyst/
│   ├── SKILL.md
│   └── stats.py          # ignored by loader
└── cli_assistant/
    └── SKILL.md
```

**SKILL.md format:**
```markdown
---
name: web_research
description: Research topics using web search.
category: research
author: tinycua-team
---

When the user asks about current events, use the web_search tool...
```

- Frontmatter is YAML between `---` delimiters.
- `name` and `description` come from frontmatter.
- Everything after frontmatter is `instructions`.
- Any extra frontmatter keys go into `metadata`.

### R-6.3: Tool Directory Loading

- `Tool.load_directory(path: Path) -> list[Tool]` — discovers subdirectories, inspects Python files for `@tool` decorators, registers decorated functions.

**Directory layout:**
```
tools/
├── calculator/
│   ├── calculator.py       # @tool decorators here
│   └── helpers.py          # ignored
├── file_manager/
│   ├── file_manager.py     # @tool decorators here
│   ├── validators.py       # ignored
│   └── permissions.py      # ignored
```

- Each subdirectory is treated as a package.
- All `.py` files are scanned.
- Only top-level `Tool` instances are collected.
- Files starting with `_` are skipped.

## Success Criteria

### SC-6.1: to_config Round-Trip
**What:** Export and import produce equivalent agent.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
from tinycua_sdk import Agent, LanguageModel, Skill, tool

@tool
def calc(expr: str) -> str:
    return str(eval(expr))

s = Skill(name='math', description='Math', instructions='Show work.')
a = Agent(name='tutor', llm_model=LanguageModel(temperature=0.2), tools=[calc], skills=[s])
a2 = Agent.from_dict(a.to_config())
assert a2.name == 'tutor'
assert a2.llm_model.temperature == 0.2
assert len(a2.tools) == 1
assert len(a2.skills) == 1
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-6.2: JSON Export with Redaction
**What:** Sensitive fields are redacted when requested.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
from tinycua_sdk import Agent, LanguageModel
a = Agent(llm_model=LanguageModel(api_key='secret123'))
json_redacted = a.to_json(redact_sensitive=True)
assert '***' in json_redacted
json_full = a.to_json(redact_sensitive=False)
assert 'secret123' in json_full
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-6.3: YAML Export/Import
**What:** YAML serialization works.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
from tinycua_sdk import Agent
a = Agent(name='yaml_test')
import tempfile, os
with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
    f.write(a.to_yaml())
    path = f.name
a2 = Agent.from_yaml_file(path)
os.unlink(path)
assert a2.name == 'yaml_test'
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-6.4: Skill Directory Loading
**What:** `Skill.load_directory()` discovers and parses skills.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
from pathlib import Path
from tinycua_sdk import Skill
skills = Skill.load_directory(Path('specs/refactor-tinycua-sdk-v2/goals/intermediate/examples/skills'))
assert len(skills) == 3
names = {s.name for s in skills}
assert names == {'cli_assistant', 'data_analyst', 'web_research'}
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-6.5: Tool Directory Loading
**What:** `Tool.load_directory()` discovers and registers tools.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
from pathlib import Path
from tinycua_sdk import Tool
tools = Tool.load_directory(Path('specs/refactor-tinycua-sdk-v2/goals/intermediate/examples/tools'))
assert len(tools) >= 1
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-6.6: Integration Tests Pass
**What:** All 4 Stage 6 integration tests pass.  
**How to check:**
```bash
cd src/tinycua-sdk && pytest tests/integration/goals/test_int_06_exporting_agent.py tests/integration/goals/test_int_07_loading_agent.py tests/integration/goals/test_int_08_loading_skills_from_directory.py tests/integration/goals/test_int_09_loading_tools_from_directory.py -v
```
**Pass if:** 4 passed, 0 failed.

## Integration Test Files
- `tests/integration/goals/test_int_06_exporting_agent.py`
- `tests/integration/goals/test_int_07_loading_agent.py`
- `tests/integration/goals/test_int_08_loading_skills_from_directory.py`
- `tests/integration/goals/test_int_09_loading_tools_from_directory.py`
