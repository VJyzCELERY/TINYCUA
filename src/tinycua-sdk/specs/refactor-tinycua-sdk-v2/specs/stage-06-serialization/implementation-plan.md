# Implementation: Stage 6 — Serialization & Directory Loading

Add agent-level JSON/YAML serialization (with sensitive field redaction), skill directory loading from `SKILL.md` frontmatter, and tool directory loading from Python modules with `@tool` decorators.

## Context

- **Spec Reference**: `spec.md`
- **Design Reference**: `design.md`
- **Priority**: P1
- **Estimated Effort**: M

## Success Criteria — Integration Tests (TDD First)

Integration tests that prove the feature works. These are written FIRST — before any implementation code. Implementation is only complete when these tests pass.

```python
# Test file: tests/integration/goals/test_int_06_exporting_agent.py
"""Integration tests for agent JSON/YAML export and redaction."""


def test_agent_json_export_round_trip():
    """Agent to_config → from_dict round-trip preserves equality."""
    # Arrange
    agent = Agent(config=AgentConfig(...))
    # Act
    config = agent.to_config()
    restored = Agent.from_dict(config)
    # Assert
    assert restored.to_config() == config


def test_agent_json_redaction():
    """Redacted JSON masks api_key; non-redacted shows full value."""
    # Arrange
    agent = Agent(config=AgentConfig(llm_model=LanguageModel(api_key="sk-secret")))
    # Act
    redacted = json.loads(agent.to_json(redact_sensitive=True))
    exposed = json.loads(agent.to_json(redact_sensitive=False))
    # Assert
    assert redacted["llm_model"]["api_key"] == "***"
    assert exposed["llm_model"]["api_key"] == "sk-secret"


def test_agent_yaml_round_trip():
    """YAML export/import round-trip preserves agent config."""
    # Arrange
    agent = Agent(config=AgentConfig(...))
    # Act
    yaml_str = agent.to_yaml()
    restored = Agent.from_yaml_file(io.StringIO(yaml_str))
    # Assert
    assert restored.to_config() == agent.to_config()
```

```python
# Test file: tests/integration/goals/test_int_08_loading_skills_from_directory.py
"""Integration tests for skill directory loading."""


def test_skill_directory_discovery():
    """Load_directory finds all skill subdirectories with SKILL.md."""
    # Arrange
    tmpdir = tmp_path / "skills"
    (tmpdir / "skill_a" / "SKILL.md").write_text("---\nname: Skill A\ndescription: Does X\n---\nDo X")
    (tmpdir / "skill_b" / "SKILL.md").write_text("---\nname: Skill B\ndescription: Does Y\n---\nDo Y")
    # Act
    skills = Skill.load_directory(tmpdir)
    # Assert
    assert len(skills) == 2
    assert {s.name for s in skills} == {"Skill A", "Skill B"}


def test_skill_directory_empty():
    """load_directory returns empty list for empty directory."""
    assert Skill.load_directory(tmp_path / "empty") == []
```

```python
# Test file: tests/integration/goals/test_int_09_loading_tools_from_directory.py
"""Integration tests for tool directory loading."""


def test_tool_directory_discovery():
    """load_directory finds @tool functions in subdirectory modules."""
    # Arrange
    tmpdir = tmp_path / "tools"
    mod_dir = tmpdir / "my_tools"
    mod_dir.mkdir(parents=True)
    (mod_dir / "__init__.py").write_text("")
    (mod_dir / "math_tools.py").write_text(
        "from tinycua_sdk.tools import tool\n\n@tool\ndef add(a: int, b: int) -> int:\n    return a + b\n"
    )
    # Act
    tools = Tool.load_directory(tmpdir)
    # Assert
    assert len(tools) == 1
    assert tools[0].name == "add"
```

### Key Test Scenarios

- [ ] **Round-trip**: Agent config can be serialized and restored without loss
- [ ] **Redaction**: api_key is masked by default, exposed when opted out
- [ ] **Skill discovery**: Directory with multiple SKILL.md files loads correctly
- [ ] **Tool discovery**: Python modules with @tool decorators load correctly
- [ ] **Edge case**: Empty directory returns empty list

## Proposed Changes

### Agent Serialization — `tinycua_sdk/agent/agent.py`

#### [MODIFY] `tinycua_sdk/agent/agent.py`

- **[Add `to_json` method]**: `Agent.to_json(indent: int = 2, redact_sensitive: bool = True) -> str` — calls `to_config()`, redacts `api_key` if requested, then `json.dumps`.
- **[Add `to_yaml` method]**: `Agent.to_yaml(redact_sensitive: bool = True) -> str` — calls `to_config()`, redacts `api_key` if requested, then `yaml.dump`.
- **[Add `from_dict` classmethod]**: Wraps `AgentConfig.from_config()` and constructs an `Agent`, aligning with the existing `from_config` pattern.
- **[Add `from_json_file` classmethod]**: Reads a JSON file path, parses, delegates to `from_dict`.
- **[Add `from_yaml_file` classmethod]**: Reads a YAML file path, parses, delegates to `from_dict`.
- **[Rationale]**: Spec R-6.1 requires agent-level serialization methods beyond the existing `to_config`/`from_config`.

### Skill Directory Loading — `tinycua_sdk/skills/models.py`

#### [MODIFY] `tinycua_sdk/skills/models.py`

- **[Add `load_directory` classmethod]**: `Skill.load_directory(path: Path) -> list[Skill]` — iterates immediate subdirectories, finds `SKILL.md`, delegates to `from_directory`.
- **[Add `from_directory` classmethod]**: `Skill.from_directory(path: Path) -> Skill` — reads `SKILL.md`, parses YAML frontmatter between `---` delimiters, extracts `name`/`description` from frontmatter (rest goes to `metadata`), everything after frontmatter is `instructions`.
- **[Add yaml import]**: Add `import yaml` for frontmatter parsing.
- **[Rationale]**: Spec R-6.2 requires bulk-loading skills from a directory tree.

### Tool Directory Loading — `tinycua_sdk/tools/decorators.py`

#### [MODIFY] `tinycua_sdk/tools/decorators.py`

- **[Add `load_directory` classmethod]**: `Tool.load_directory(path: Path) -> list[Tool]` — iterates subdirectories, scans `.py` files (skipping `_` prefix), loads each module via `importlib`, collects top-level `Tool` instances via `inspect.getmembers`.
- **[Add `_load_module_from_path` module-level helper]**: Loads a Python module from a file path using `importlib.util.spec_from_file_location`.
- **[Add `from_config` classmethod]**: Alias or explicit method — design shows `Tool.from_config(config)` that extracts from `{"function": {"name": ..., "description": ..., "parameters": ...}}` format. The existing `Tool.from_dict` already handles this (it checks for `"function"` key). Add `from_config` as a public alias for clarity.
- **[Rationale]**: Spec R-6.3 requires bulk-loading tools from a directory tree of Python modules.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `Agent` | Modify | Add `to_json`, `to_yaml`, `from_dict`, `from_json_file`, `from_yaml_file` |
| `Skill` | Modify | Add `load_directory`, `from_directory` classmethods |
| `Tool` | Modify | Add `load_directory`, `from_config` classmethods; add `_load_module_from_path` helper |

## Verification Plan

### Automated Tests

- [ ] `test_int_06_exporting_agent.py` — round-trip to_config equality, JSON/YAML export with/without redaction, file-based round-trip
- [ ] `test_int_07_loading_agent.py` — YAML export, YAML file round-trip
- [ ] `test_int_08_loading_skills_from_directory.py` — Skill directory discovery, frontmatter parsing, SKILL.md without frontmatter, empty directory
- [ ] `test_int_09_loading_tools_from_directory.py` — Tool directory discovery, @tool function collection, module loading edge cases

### Manual Verification

- [ ] Run `pytest -v tests/integration/goals/` — all 4 integration tests pass
- [ ] Verify redaction: redacted JSON/YAML shows `"***"` for api_key, non-redacted shows full value

## Dependencies

### Internal Dependencies

- [x] Stage 1 (Value Objects) — LanguageModel.to_dict/from_dict, Skill.to_dict/from_dict, Tool.to_config/from_dict
- [x] Stage 2 (Agent Config) — AgentConfig.to_config/from_config
- [x] Stage 3 (Execution Core) — Agent class, AgentExecutor
- [ ] Depends on Stage 7 (Security) for full approval workflow serialization (not needed yet)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `api_key` leaked in non-redacted serialization | Medium | Redact by default (`redact_sensitive=True`); document the risk for callers who disable redaction |
| `importlib` module loading has side effects | Medium | Skip `_` prefixed files, document that loaded modules have no callable, add a warning |
| YAML dependency not in pyproject.toml | Low | Add `PyYAML` to project dependencies if not already present |
