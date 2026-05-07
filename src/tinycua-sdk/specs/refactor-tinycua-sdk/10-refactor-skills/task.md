# Tasks: Stage 10 — Refactor Skills Framework

Implementation tasks for Stage 10. Check off items as completed.

## Core Skills Package

- [ ] Task 1 — Delete `skills/backend.py` <!-- id: 10-1 -->
  - [ ] Remove `tinycua_sdk/skills/backend.py`
  - [ ] Verify no imports reference it (grep `SkillBackend`, `LocalSkillBackend`, etc.)

- [ ] Task 2 — Update `skills/models.py` <!-- id: 10-2 -->
  - [ ] Add `source: str | None = None` field
  - [ ] Add `is_active: bool = True` field
  - [ ] Add `version: str = "1.0.0"` field
  - [ ] Remove or deprecate `path`, `created_at`, `modified_at` fields
  - [ ] Implement `Skill.load(cls, text: str) -> Skill` classmethod
  - [ ] Implement `Skill.from_dict(cls, data: dict) -> Skill` classmethod
  - [ ] Update `Skill.to_dict()` for new fields
  - [ ] Add `_parse_markdown_sections` helper

- [ ] Task 3 — Update `skills/registry.py` <!-- id: 10-3 -->
  - [ ] Remove `SkillLoader` import and `_loader` initialization
  - [ ] Remove `cache` parameter from `__init__`
  - [ ] Remove `load_skills_from_directory()` method
  - [ ] Rename `register_skill` -> `register`
  - [ ] Rename `get_skill` -> `get`
  - [ ] Add `unregister(name: str) -> None` method
  - [ ] Decide whether to keep or remove `get_categories()`
  - [ ] Verify no singleton pattern exists

- [ ] Task 4 — Delete `skills/loader.py` <!-- id: 10-4 -->
  - [ ] Remove `tinycua_sdk/skills/loader.py`
  - [ ] Ensure parsing logic is fully migrated to `Skill.load()`

- [ ] Task 5 — Update `skills/cache.py` <!-- id: 10-5 -->
  - [ ] Remove `snapshot_dir` parameter from `__init__`
  - [ ] Remove `save_snapshot()` method
  - [ ] Remove `load_snapshot()` method
  - [ ] Remove `invalidate_if_stale()` method
  - [ ] Remove `check_modification` parameter
  - [ ] Keep LRU in-memory behavior (`get`, `put`, `invalidate`, `clear`, `size`)

- [ ] Task 6 — Update `skills/__init__.py` <!-- id: 10-6 -->
  - [ ] Remove exports for deleted classes (`SkillLoader`, `SkillNotFoundError`, `SkillParseError`, `SkillCache`)
  - [ ] Keep exports: `Skill`, `SkillRegistry`
  - [ ] Update `__all__`

## Consumer Code

- [ ] Task 7 — Update `agent/loader.py` <!-- id: 10-7 -->
  - [ ] Replace `skill_registry.load_skills_from_directory(path)` with direct file reading + `Skill.load()` + `registry.register()`
  - [ ] Replace `skill_registry.get_skill(name)` -> `skill_registry.get(name)`

- [ ] Task 8 — Update `tinycua/tui/skills_manager.py` <!-- id: 10-8 -->
  - [ ] Remove `SkillLoader` import
  - [ ] Replace loader usage with `Path.read_text()` + `Skill.load()`
  - [ ] Replace `load_skills_from_directory` with explicit loop
  - [ ] Replace `get_skill` -> `get`

## Tests

- [ ] Task 9 — Update `tests/unit/test_skills.py` <!-- id: 10-9 -->
  - [ ] Verify it passes with updated `models.py` and `registry.py`
  - [ ] Fix any field name mismatches (`path` -> `source`)

- [ ] Task 10 — Update `tests/unit/test_skills_registry.py` <!-- id: 10-10 -->
  - [ ] Replace `register_skill` -> `register`
  - [ ] Replace `get_skill` -> `get`
  - [ ] Delete `test_load_skills_from_directory`
  - [ ] Add `test_unregister`
  - [ ] Add `test_registry_instances_are_independent`

- [ ] Task 11 — Update `tests/unit/test_skills_loader.py` <!-- id: 10-11 -->
  - [ ] Replace all `SkillLoader` tests with `Skill.load()` tests
  - [ ] Test YAML frontmatter parsing
  - [ ] Test section parsing (`## Description`, `## Instructions`)
  - [ ] Test missing/invalid frontmatter

- [ ] Task 12 — Update `tests/unit/test_skills_cache.py` <!-- id: 10-12 -->
  - [ ] Remove `test_save_and_load_snapshot`
  - [ ] Remove `test_invalidate_if_stale`

- [ ] Task 13 — Update `tests/unit/test_skills_tools.py` <!-- id: 10-13 -->
  - [ ] Replace `register_skill` -> `register`

- [ ] Task 14 — Update integration tests <!-- id: 10-14 -->
  - [ ] `tests/integration/test_skills_integration.py` — replace `load_skills_from_directory` with `Skill.load()` + `register()`
  - [ ] `tests/integration/test_skills_example.py` — remove `SkillLoader`, use `Skill.load()`
  - [ ] `tests/integration/test_agent_creation.py` — replace `load_skills_from_directory` with `Skill.load()` + `register()`

## Examples and Verification

- [ ] Task 15 — Update `examples/12_skills_example.py` <!-- id: 10-15 -->
  - [ ] Remove `SkillLoader` usage
  - [ ] Use `Skill.load()` from file content

- [ ] Task 16 — Run full test suite <!-- id: 10-16 -->
  - [ ] `pytest` passes for all remaining tests
  - [ ] Fix any import errors from deleted modules

## Documentation

- [ ] Task 17 — Verify `CallableTool` is already absent <!-- id: 10-17 -->
  - [ ] Confirm `skills/tools.py` does not exist
  - [ ] Confirm no `CallableTool` class exists in codebase
  - [ ] Mark acceptance criteria as satisfied (no-op)

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement-plan` to execute these tasks*
*Last updated: 2026-04-29*
