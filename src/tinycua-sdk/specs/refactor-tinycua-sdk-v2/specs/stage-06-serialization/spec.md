# Stage 6: Serialization & Directory Loading — Specification

**Status**: Draft | In Progress | Complete
**Created**: 2026-05-02
**Last Updated**: 2026-05-02
**Subproject(s) Affected**: tinycua-sdk

## Objective
Agents, skills, and tools can be exported and imported. Skills and tools can be bulk-loaded from directories.

## Guiding Principles
All stages adhere to the principles defined in [`ROADMAP.md#principles`](../../docs/ROADMAP.md#principles).

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

Each success criterion must be validated by running the specified target file(s).

Format: [ ] Success Criteria Description - Target File(s) - Expected Output - How to validate

- [ ] to_config Round-Trip - tests/integration/goals/test_int_06_exporting_agent.py - PASS - `print('PASS')`
  Description: Export and import produce equivalent agent.

- [ ] JSON Export with Redaction - tests/integration/goals/test_int_06_exporting_agent.py - PASS - `print('PASS')`
  Description: Sensitive fields are redacted when requested.

- [ ] YAML Export/Import - tests/integration/goals/test_int_07_loading_agent.py - PASS - `print('PASS')`
  Description: YAML serialization works.

- [ ] Skill Directory Loading - tests/integration/goals/test_int_08_loading_skills_from_directory.py - PASS - `print('PASS')`
  Description: `Skill.load_directory()` discovers and parses skills.

- [ ] Tool Directory Loading - tests/integration/goals/test_int_09_loading_tools_from_directory.py - PASS - `print('PASS')`
  Description: `Tool.load_directory()` discovers and registers tools.

- [ ] Integration Tests Pass - tests/integration/goals/test_int_06_exporting_agent.py, tests/integration/goals/test_int_07_loading_agent.py, tests/integration/goals/test_int_08_loading_skills_from_directory.py, tests/integration/goals/test_int_09_loading_tools_from_directory.py - 4 passed, 0 failed - pytest -v

## Integration Test Files
- `tests/integration/goals/test_int_06_exporting_agent.py`
- `tests/integration/goals/test_int_07_loading_agent.py`
- `tests/integration/goals/test_int_08_loading_skills_from_directory.py`
- `tests/integration/goals/test_int_09_loading_tools_from_directory.py`
