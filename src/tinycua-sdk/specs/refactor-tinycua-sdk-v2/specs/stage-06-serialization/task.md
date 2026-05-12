# Tasks: Stage 6 — Serialization & Directory Loading

Implementation tasks for Stage 6. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests (defined in implementation-plan.md) <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [ ] Add `to_json`, `to_yaml` to Agent with api_key redaction <!-- id: 2 -->
  - [ ] Implement `Agent.to_json(indent=2, redact_sensitive=True)` — builds on `to_config()`, redacts `llm_model.api_key` if redact_sensitive, serializes to JSON
  - [ ] Implement `Agent.to_yaml(redact_sensitive=True)` — same pattern with YAML
  - [ ] Add `import json` and/or `import yaml` in agent.py
- [ ] Add `from_dict`, `from_json_file`, `from_yaml_file` classmethods to Agent <!-- id: 3 -->
  - [ ] `Agent.from_dict(config)` — delegates to `AgentConfig.from_config` and constructs Agent
  - [ ] `Agent.from_json_file(path)` — reads file, parses JSON, calls `from_dict`
  - [ ] `Agent.from_yaml_file(path)` — reads file, parses YAML, calls `from_dict`
- [ ] Add `load_directory` and `from_directory` classmethods to Skill <!-- id: 4 -->
  - [ ] `Skill.from_directory(path)` — reads `SKILL.md`, parses YAML frontmatter, extracts name/description/instructions/metadata
  - [ ] `Skill.load_directory(path)` — iterates subdirectories, calls `from_directory` for each with `SKILL.md`
  - [ ] Add `import yaml` and `from pathlib import Path` to `skills/models.py`
- [ ] Add `load_directory` and `from_config` to Tool <!-- id: 5 -->
  - [ ] `Tool.from_config(config)` — public alias/delegate matching design spec (existing `from_dict` handles the logic)
  - [ ] `Tool.load_directory(path)` — iterates subdirectories, scans `.py` files, loads modules, collects `Tool` instances
  - [ ] Add `_load_module_from_path(path)` helper function
  - [ ] Add needed imports: `importlib.util`, `inspect`, `sys`, `Path`

## Testing Phase

- [ ] Write integration test for agent round-trip and redaction — `test_int_06_exporting_agent.py` <!-- id: 6 -->
  - [ ] Round-trip: create agent → `to_config` → `from_dict` → assert equality
  - [ ] JSON redaction: verify `***` in redacted output, full api_key in non-redacted
  - [ ] YAML redaction: same as JSON
  - [ ] File round-trip: write JSON file → load back → assert equivalence
- [ ] Write integration test for YAML agent loading — `test_int_07_loading_agent.py` <!-- id: 7 -->
  - [ ] YAML export/import round-trip
  - [ ] YAML file load round-trip
- [ ] Write integration test for skill directory loading — `test_int_08_loading_skills_from_directory.py` <!-- id: 8 -->
  - [ ] Create temp directory with multiple skill subdirectories
  - [ ] Load and verify count and content
  - [ ] Test edge case: SKILL.md without frontmatter
  - [ ] Test edge case: empty directory
- [ ] Write integration test for tool directory loading — `test_int_09_loading_tools_from_directory.py` <!-- id: 9 -->
  - [ ] Create temp directory with tool subdirectories containing @tool functions
  - [ ] Load and verify count
  - [ ] Test edge case: directory with no tools
  - [ ] Test edge case: directory with `_` prefixed files (should be skipped)

## Verification Phase

- [ ] Run all 4 integration tests — verify they pass <!-- id: 10 -->
- [ ] Verify redaction behavior manually <!-- id: 11 -->
- [ ] Verify round-trip parity with different agent configurations <!-- id: 12 -->

## Documentation Phase

- [ ] Add docstrings to all new public methods <!-- id: 13 -->
- [ ] Update any relevant README or docs if needed <!-- id: 14 -->

## Review and Merge

- [ ] Create pull request <!-- id: 15 -->
- [ ] Address review feedback <!-- id: 16 -->
- [ ] Merge to main branch <!-- id: 17 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-10*
