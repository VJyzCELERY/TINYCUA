# Tasks: Integration Tests Cleanup

Implementation tasks for tinycua-sdk integration tests cleanup. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Run baseline test suite to establish passing state: `cd src/tinycua-sdk && uv run pytest` <!-- id: 0 -->

## Phase 1 — File Relocation and Renaming

- [ ] Create `tests/integration/test_language_model.py` from `goals/test_gs_01_language_model_definition.py` <!-- id: 1 -->
  - [ ] Rename class `TestGS01LanguageModelDefinition` → `TestLanguageModel`
  - [ ] Rename test methods: `test_gs_01_*` → descriptive names
- [ ] Create `tests/integration/test_agent_streaming.py` from `goals/test_gs_04_agent_streaming.py` <!-- id: 2 -->
  - [ ] Rename test functions: `test_gs_01_*` → descriptive names
- [ ] Create `tests/integration/test_tool_creation.py` from `goals/test_int_01_tool_creation.py` <!-- id: 3 -->
  - [ ] Rename class `TestInt01ToolCreation` → `TestToolCreation`
  - [ ] Rename test methods: `test_int_01_*` → descriptive names
- [ ] Create `tests/integration/test_tool_loading.py` from `goals/test_int_09_loading_tools_from_directory.py` <!-- id: 4 -->
  - [ ] Rename class `TestInt09LoadingToolsFromDirectory` → `TestToolLoading`
  - [ ] Rename test methods: `test_int_01_*` → descriptive names
- [ ] Create `tests/integration/test_custom_agent_loop.py` from `goals/test_adv_01_custom_agent_loop.py` <!-- id: 5 -->
  - [ ] Functions already descriptive — keep as-is
- [ ] Create `tests/integration/test_guardrail_system.py` from `goals/test_adv_02_guardrail_system.py` <!-- id: 6 -->
  - [ ] Functions already descriptive — keep as-is
- [ ] Create `tests/integration/test_permission_system.py` from `goals/test_adv_03_permission_system.py` <!-- id: 7 -->
  - [ ] Functions already descriptive — keep as-is

## Phase 2 — Merging Overlapping Tests

- [ ] Merge `test_gs_02_agent_creation.py` into `tests/integration/test_agent_creation.py` <!-- id: 8 -->
  - [ ] Rename class `TestGS02AgentCreation` → `TestAgentConstructor`
  - [ ] Rename test methods: `test_gs_01_*` → descriptive names
  - [ ] Add necessary imports (`pytest`, `AgentPolicy`, `LanguageModel`, `Skill`, `tool`)
- [ ] Create `tests/integration/test_agent_export.py` merging `test_int_06` + `test_int_07` <!-- id: 9 -->
  - [ ] Rename `TestInt06ExportingAgent` → `TestAgentExport`
  - [ ] Rename `TestInt07LoadingAgent` → `TestAgentLoading`
  - [ ] Rename test methods: `test_int_01_*` → descriptive names
  - [ ] Deduplicate YAML redaction tests (keep more comprehensive version)
- [ ] Create `tests/integration/test_skills.py` merging `test_int_02` + `test_int_08` + `test_skills_example.py` <!-- id: 10 -->
  - [ ] Rename `TestInt02SkillsCreation` → `TestSkillsCreation`
  - [ ] Rename `TestInt08LoadingSkillsFromDirectory` → `TestSkillsDirectoryLoading`
  - [ ] Keep existing classes from `test_skills_example.py` (`TestSkillDiscovery`, `TestSkillRegistry`, `TestSkillTools`, `TestSkillsWithAgent`)
  - [ ] Rename test methods from `test_int_01_*` → descriptive names
  - [ ] Consolidate shared `temp_skill_dir` fixture / `_load_skills_from_directory` helper

## Phase 3 — New End-to-End Tests

- [ ] Create `tests/integration/test_end_to_end.py` <!-- id: 11 -->
  - [ ] Add `test_agent_create_export_reload_roundtrip`
  - [ ] Add `test_agent_run_simple` (skips if LLM unavailable)
  - [ ] Add `test_tool_invocation_via_executor`

## Phase 4 — Cleanup and Verification

- [ ] Delete `tests/integration/goals/` directory <!-- id: 12 -->
- [ ] Delete `tests/integration/test_skills_example.py` (now merged into `test_skills.py`) <!-- id: 13 -->
- [ ] Run integration tests: `uv run pytest tests/integration/` <!-- id: 14 -->
- [ ] Run full test suite: `cd src/tinycua-sdk && uv run pytest` <!-- id: 15 -->
- [ ] Run Makefile target: `make test-integration` <!-- id: 16 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-16*
