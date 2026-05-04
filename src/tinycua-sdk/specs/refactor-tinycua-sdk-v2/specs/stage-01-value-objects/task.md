# Tasks: Stage 1 - Core Value Objects

Implementation tasks for Stage 1 - Core Value Objects. Check off items as completed.

## Implementation Phase

- [x] Rename LLMModel to LanguageModel and expand fields per spec R-1.1 <!-- id: 0 -->
  - [x] Rename class from `LLMModel` to `LanguageModel` in `tinycua_sdk/agent/llm_model.py` <!-- id: 1 -->
  - [x] Add all OpenAI-compatible parameter fields with defaults <!-- id: 2 -->
  - [x] Add `_normalize_provider` field validator <!-- id: 3 -->
  - [x] Add `_resolve_env_vars` field validator for api_key <!-- id: 4 -->
  - [x] Add `to_dict()` method (exclude_none=True) <!-- id: 5 -->
  - [x] Add `to_json()` method (indent=2) <!-- id: 6 -->
  - [x] Add `from_dict()` classmethod <!-- id: 7 -->
  - [x] Add `from_json()` classmethod <!-- id: 8 -->
  - [x] Add `ConfigDict(frozen=True)` for immutability <!-- id: 9 -->

- [x] Implement Tool class and @tool decorator per spec R-1.2 <!-- id: 10 -->
  - [x] Add `dependencies` field to `Tool.__init__` <!-- id: 11 -->
  - [x] Update `to_config()` to return OpenAI function-calling schema format <!-- id: 12 -->
  - [x] Update `invoke()` to raise RuntimeError when _callable is None <!-- id: 13 -->
  - [x] Add `from_callable()` classmethod with signature inspection <!-- id: 14 -->
  - [x] Add `_python_type_to_json_schema()` helper function <!-- id: 15 -->
  - [x] Add `_parse_param_descriptions()` helper function <!-- id: 16 -->
  - [x] Add `@tool` decorator function (supports both `@tool` and `@tool(dependencies=[])`) <!-- id: 17 -->

- [x] Implement Skill value object per spec R-1.3 <!-- id: 18 -->
  - [x] Create frozen Pydantic Skill model with name, description, instructions, metadata fields <!-- id: 19 -->
  - [x] Add `to_dict()` method <!-- id: 20 -->
  - [x] Add `from_dict()` classmethod <!-- id: 21 -->

- [x] Implement SkillRegistry per spec R-1.3 <!-- id: 22 -->
  - [x] Implement `register(skill)` with overwrite-on-duplicate behavior <!-- id: 23 -->
  - [x] Implement `list_skills()` returning list of all skills <!-- id: 24 -->
  - [x] Implement `get(name)` returning Skill or None <!-- id: 25 -->

- [x] Update package exports <!-- id: 26 -->
  - [x] Add LanguageModel, Tool, tool, Skill, SkillRegistry to `__all__` in `tinycua_sdk/__init__.py` <!-- id: 27 -->

## Testing Phase

- [x] Create integration test: LanguageModel creation patterns <!-- id: 28 -->
  - [x] Test minimal creation with defaults (from target 1.1) <!-- id: 29 -->
  - [x] Test full configuration with all OpenAI-compatible params (from target 1.2) <!-- id: 30 -->
  - [x] Test serialization round-trip to_dict/from_dict (from target 1.3) <!-- id: 31 -->
  - [x] Test JSON export/import to_json/from_json (from target 1.4) <!-- id: 32 -->

- [x] Create integration test: Tool and @tool <!-- id: 33 -->
  - [x] Test @tool schema generation with type mapping and docstring parsing (from target 1.5) <!-- id: 34 -->
  - [x] Test Tool.invoke execution with keyword and positional args (from target 1.6) <!-- id: 35 -->
  - [x] Test manual Tool construction (from target 1.7) <!-- id: 36 -->

- [x] Create integration test: Skill and SkillRegistry <!-- id: 37 -->
  - [x] Test Skill creation, to_dict, from_dict round-trip (from target 1.8) <!-- id: 38 -->
  - [x] Test SkillRegistry register, list, get, overwrite behavior (from target 1.9) <!-- id: 39 -->

- [x] Run full integration test suite <!-- id: 40 -->
  - [x] `pytest tests/integration/goals/ -v` — expect 25 passed, 0 failed <!-- id: 41 -->

## Verification Phase

- [x] Verify LanguageModel is frozen (mutation raises error) <!-- id: 42 -->
- [x] Verify @tool decorator works without args and with dependencies arg <!-- id: 43 -->
- [x] Verify SkillRegistry overwrites on duplicate name registration <!-- id: 44 -->
- [x] Verify env-var substitution resolves `${VAR_NAME}` in api_key <!-- id: 45 -->
- [x] Verify to_dict excludes None values <!-- id: 46 -->

## Documentation Phase

- [x] Verify `__all__` exports are complete and correct <!-- id: 47 -->
- [x] Verify all public methods have docstrings per code generation rules <!-- id: 48 -->

## Review and Merge

- [x] Review implementation against spec.md requirements (R-1.1, R-1.2, R-1.3) <!-- id: 49 -->
- [x] Verify all success criteria from spec.md are met <!-- id: 50 -->
- [ ] Delete targets/ directory after confirming integration tests cover all target scenarios <!-- id: 51 -->
- [ ] Create pull request for Stage 1 changes <!-- id: 52 -->
- [ ] Address review feedback <!-- id: 53 -->
- [ ] Merge to main branch <!-- id: 54 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement-plan` to execute these tasks*
*Last updated: 2026-05-02*
