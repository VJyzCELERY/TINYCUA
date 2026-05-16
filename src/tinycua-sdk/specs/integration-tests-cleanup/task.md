# Tasks: Integration Tests Cleanup

Implementation tasks for tinycua-sdk integration tests cleanup. Check off items as completed.

## TDD Phase (Tests First)

- [x] Run baseline test suite to establish passing state: `cd src/tinycua-sdk && uv run pytest` <!-- id: 0 -->

## Phase 1 — File Relocation and Renaming

- [x] Create `tests/integration/test_language_model.py` from `goals/test_gs_01_language_model_definition.py` <!-- id: 1 -->
  - [x] Rename class `TestGS01LanguageModelDefinition` → `TestLanguageModel`
  - [x] Rename test methods: `test_gs_01_*` → descriptive names
- [x] Create `tests/integration/test_agent_streaming.py` from `goals/test_gs_04_agent_streaming.py` <!-- id: 2 -->
  - [x] Rename test functions: `test_gs_01_*` → descriptive names
- [x] Create `tests/integration/test_tool_creation.py` from `goals/test_int_01_tool_creation.py` <!-- id: 3 -->
  - [x] Rename class `TestInt01ToolCreation` → `TestToolCreation`
  - [x] Rename test methods: `test_int_01_*` → descriptive names
- [x] Create `tests/integration/test_tool_loading.py` from `goals/test_int_09_loading_tools_from_directory.py` <!-- id: 4 -->
  - [x] Rename class `TestInt09LoadingToolsFromDirectory` → `TestToolLoading`
  - [x] Rename test methods: `test_int_01_*` → descriptive names
- [x] Create `tests/integration/test_custom_agent_loop.py` from `goals/test_adv_01_custom_agent_loop.py` <!-- id: 5 -->
  - [x] Functions already descriptive — keep as-is
- [x] Create `tests/integration/test_guardrail_system.py` from `goals/test_adv_02_guardrail_system.py` <!-- id: 6 -->
  - [x] Functions already descriptive — keep as-is
- [x] Create `tests/integration/test_permission_system.py` from `goals/test_adv_03_permission_system.py` <!-- id: 7 -->
  - [x] Functions already descriptive — keep as-is

## Phase 2 — Merging Overlapping Tests

- [x] Merge `test_gs_02_agent_creation.py` into `tests/integration/test_agent_creation.py` <!-- id: 8 -->
  - [x] Rename class `TestGS02AgentCreation` → `TestAgentConstructor`
  - [x] Rename test methods: `test_gs_01_*` → descriptive names
  - [x] Add necessary imports (`AgentPolicy`, `LanguageModel`, `Skill`, `tool`)
  - [x] **Remove** `test_obsolete_params_rejected` (backward compat no longer needed) and its `pytest` import
- [x] Create `tests/integration/test_agent_export.py` merging `test_int_06` + `test_int_07` <!-- id: 9 -->
  - [x] Rename `TestInt06ExportingAgent` → `TestAgentExport`
  - [x] Rename `TestInt07LoadingAgent` → `TestAgentLoading`
  - [x] Rename test methods: `test_int_01_*` → descriptive names
  - [x] Deduplicate YAML redaction tests (keep more comprehensive version)
- [x] Create `tests/integration/test_skills.py` merging `test_int_02` + `test_int_08` + `test_skills_example.py` <!-- id: 10 -->
  - [x] Rename `TestInt02SkillsCreation` → `TestSkillsCreation`
  - [x] Rename `TestInt08LoadingSkillsFromDirectory` → `TestSkillsDirectoryLoading`
  - [x] Keep existing classes from `test_skills_example.py` (`TestSkillDiscovery`, `TestSkillRegistry`, `TestSkillTools`, `TestSkillsWithAgent`)
  - [x] Rename test methods from `test_int_01_*` → descriptive names
  - [x] Consolidate shared `temp_skill_dir` fixture / `_load_skills_from_directory` helper

## Phase 3 — New End-to-End Tests

- [x] Create `tests/integration/test_end_to_end.py` <!-- id: 11 -->
  - [x] Add `test_agent_create_export_reload_roundtrip`
  - [x] Add `test_agent_run_simple` (skips if LLM unavailable)
  - [x] Add `test_tool_invocation_via_executor`

## Phase 4 — Cleanup and Verification

- [x] Delete `tests/integration/goals/` directory <!-- id: 12 -->
- [x] Delete `tests/integration/test_skills_example.py` (now merged into `test_skills.py`) <!-- id: 13 -->
- [x] Run integration tests: `uv run pytest tests/integration/` — **81 passed** <!-- id: 14 -->
- [x] Run full test suite: `cd src/tinycua-sdk && uv run pytest` — **308 passed** (307 baseline + 3 new e2e - 1 removed obsolete_params - 1 duplicate YAML redaction) <!-- id: 15 -->
- [x] Run Makefile target: `make test-integration` — **81 passed** <!-- id: 16 -->

## Phase 5 — Targeted Suppression Cleanup (Planned, Not Implemented Yet)

- [ ] Run characterization checks before cleanup: `cd src/tinycua-sdk && uv run pytest tests/unit/test_loop.py` <!-- id: 17 -->
- [ ] Remove `# noqa: C901` from `tinycua_sdk/agent/loop.py` <!-- id: 18 -->
  - [ ] Add focused loop tests first if any `_run_stream` branch is not already covered
  - [ ] Refactor `_run_stream` into behavior-preserving helpers until Ruff no longer reports C901
  - [ ] Preserve stream lifecycle events, tool-call iteration, max iteration/tool-call handling, usage aggregation, provider failure handling, and cancellation behavior
- [ ] Remove `# type: ignore[type-arg]` from `tinycua_sdk/agent/config.py` <!-- id: 19 -->
  - [ ] Adjust the `skills` field annotation/import pattern without changing default list behavior
  - [ ] Verify Agent config serialization and skill-related behavior remain unchanged
- [ ] Remove `# pragma: no cover` from `tests/unit/test_loop.py` <!-- id: 20 -->
  - [ ] Replace the unreachable-yield async-generator stub with a coverage-friendly empty async stream helper
  - [ ] Preserve the empty provider stream response lifecycle assertions
- [ ] Run suppression cleanup validation commands <!-- id: 21 -->
  - [ ] `cd src/tinycua-sdk && uv run ruff check .`
  - [ ] `cd src/tinycua-sdk && uv run mypy tinycua_sdk/`
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/test_loop.py`
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/integration/`
  - [ ] `cd src/tinycua-sdk && uv run pytest`

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-16*
