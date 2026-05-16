# Design Document: Integration Tests Cleanup

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-05-16

---

## Overview

Reorganize the tinycua-sdk integration tests from the informal `tests/integration/goals/` structure into a flat `tests/integration/` layout with consistent naming. Covers file relocation, renaming, deduplication via merging, addition of new end-to-end integration tests, and a targeted cleanup of inline suppression comments discovered during SDK review. Source changes are limited to the suppression cleanup in `loop.py` and `config.py`; test changes are limited to integration cleanup plus the `test_loop.py` coverage-suppression cleanup.

---

## Architecture

### Before and After

```
Before:                                After:
tests/integration/                     tests/integration/
├── __init__.py                        ├── __init__.py
├── conftest.py                        ├── conftest.py
├── goals/                             ├── test_agent_creation.py    (expanded)
│   ├── test_gs_01_*.py               ├── test_agent_export.py      (merged)
│   ├── test_gs_02_*.py     ──►       ├── test_agent_streaming.py
│   ├── test_gs_04_*.py               ├── test_custom_agent_loop.py
│   ├── test_int_01_*.py              ├── test_guardrail_system.py
│   ├── test_int_02_*.py              ├── test_language_model.py
│   ├── test_int_06_*.py              ├── test_permission_system.py
│   ├── test_int_07_*.py              ├── test_skills.py            (merged)
│   ├── test_int_08_*.py              ├── test_tool_creation.py
│   ├── test_int_09_*.py              ├── test_tool_loading.py
│   ├── test_adv_01_*.py              └── test_end_to_end.py        (NEW)
│   ├── test_adv_02_*.py
│   └── test_adv_03_*.py
├── test_agent_creation.py
└── test_skills_example.py
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tests/integration/goals/` | Deleted | All files moved to parent dir |
| `tests/integration/test_agent_creation.py` | Modified | Expanded with merged content from `test_gs_02_agent_creation.py` |
| `tests/integration/test_skills_example.py` | Deleted | Merged into `test_skills.py` |
| `test_agent_export.py` | Created | Merge of `test_int_06` + `test_int_07` |
| `test_agent_streaming.py` | Created | Renamed from `test_gs_04` |
| `test_custom_agent_loop.py` | Created | Renamed from `test_adv_01` |
| `test_guardrail_system.py` | Created | Renamed from `test_adv_02` |
| `test_language_model.py` | Created | Renamed from `test_gs_01` |
| `test_permission_system.py` | Created | Renamed from `test_adv_03` |
| `test_skills.py` | Created | Merge of `test_int_02` + `test_int_08` + `test_skills_example.py` |
| `test_tool_creation.py` | Created | Renamed from `test_int_01` |
| `test_tool_loading.py` | Created | Renamed from `test_int_09` |
| `test_end_to_end.py` | Created | New end-to-end integration tests |
| `tinycua_sdk/agent/loop.py` | Modified | Refactor `_run_stream` enough to remove `# noqa: C901` without changing streaming/tool-call behavior |
| `tinycua_sdk/agent/config.py` | Modified | Remove `# type: ignore[type-arg]` from the `skills` field while preserving Agent config behavior |
| `tests/unit/test_loop.py` | Modified | Replace unreachable async-generator stub pattern so `# pragma: no cover` is no longer needed |

---

## Merge Analysis

### Merge 1: `test_agent_creation.py` + `test_gs_02_agent_creation.py`

| Aspect | `test_agent_creation.py` | `test_gs_02_agent_creation.py` |
|--------|--------------------------|-------------------------------|
| What it tests | `Agent.from_config()` (dict-based) | `Agent()` constructor |
| Test class | `TestAgentCreation` | `TestGS02AgentCreation` |
| Overlap | None | None |

Decision: Merge into `test_agent_creation.py`. Keep both classes distinct since they test different creation paths. Rename method prefixes from `test_gs_*` to descriptive names.

> **Removed test**: `test_gs_05_obsolete_params_rejected` → `test_obsolete_params_rejected` was intentionally dropped. This test validated that old backward-compatible parameters raised `TypeError`, but backward compatibility is no longer needed.

### Merge 2: `test_int_06_exporting_agent.py` + `test_int_07_loading_agent.py`

| Aspect | `test_int_06_exporting_agent.py` | `test_int_07_loading_agent.py` |
|--------|----------------------------------|-------------------------------|
| What it tests | JSON/YAML export, redaction, file round-trips | YAML export, redaction, file loading |
| Overlap | YAML redaction | YAML redaction |
| Unique tests | dict round-trip, JSON file round-trip, YAML file round-trip | yaml file load, yaml exposed export |

Decision: Merge into `test_agent_export.py`. Export and loading are two sides of the same serialization concern.

### Merge 3: Skills tests (three-way merge)

| Aspect | `test_int_02_skills_creation.py` | `test_int_08_loading_skills_from_directory.py` | `test_skills_example.py` |
|--------|----------------------------------|-----------------------------------------------|--------------------------|
| What it tests | Skill model creation, `SkillRegistry` CRUD | `Skill.load_directory()`, `Skill.from_directory()` | Skill discovery from dir, registry ops, skill tools, agent integration |
| Test class | `TestInt02SkillsCreation` | `TestInt08LoadingSkillsFromDirectory` | `TestSkillDiscovery`, `TestSkillRegistry`, `TestSkillTools`, `TestSkillsWithAgent` |
| Overlap | None with loading; partial with example (registry) | None with creation; partial with example (discovery) | Registry overlaps with creation; discovery overlaps with loading |

Decision: Merge all three into `test_skills.py`. The three files test closely related functionality — skill creation, registry, directory loading, and agent integration — and merging eliminates fragmentation. Consolidate shared fixtures (temp skill directory creation) into a single `conftest.py` fixture or module-level helper. Keep test classes distinct since each tests a different facet.

---

## Naming Convention

All test files follow `test_<topic>.py`:

| Topic | File |
|-------|------|
| Language model definition | `test_language_model.py` |
| Agent creation (constructor + from_config) | `test_agent_creation.py` |
| Agent serialization/export/loading | `test_agent_export.py` |
| Agent streaming | `test_agent_streaming.py` |
| Custom agent loops | `test_custom_agent_loop.py` |
| Guardrail system | `test_guardrail_system.py` |
| Permission system | `test_permission_system.py` |
| Tool creation (@tool decorator) | `test_tool_creation.py` |
| Tool loading from directory | `test_tool_loading.py` |
| Skill model, registry, directory loading, agent integration | `test_skills.py` |
| End-to-end workflows | `test_end_to_end.py` |

Internal test method names will also be renamed from numbered prefixes to descriptive names.

---

## Implementation Phases

### Phase 1 — File Relocation and Renaming

- Create new files in `tests/integration/` with renamed versions of each goals file.
- Update internal class names and test method names to be descriptive.
- Remove the `tests/integration/goals/` directory.
- Update any imports or path references.

### Phase 2 — Merging Overlapping Tests

- Merge `test_gs_02_agent_creation.py` content into `test_agent_creation.py`.
- Merge `test_int_06_exporting_agent.py` and `test_int_07_loading_agent.py` into `test_agent_export.py`.
- Merge `test_int_02_skills_creation.py`, `test_int_08_loading_skills_from_directory.py`, and `test_skills_example.py` into `test_skills.py`.

### Phase 3 — New End-to-End Tests

- Create `test_end_to_end.py` with full workflow integration tests:
  - Agent creation, tool registration, config export, reload, run.

### Phase 4 — Verification

- Run `make test-unit` to verify no unit test breakage.
- Run `make test-integration` to verify all tests are discovered and pass (or skip gracefully).
- Run `uv run pytest` to verify full test suite.

### Phase 5 — Targeted Suppression Cleanup

- Refactor `tinycua_sdk/agent/loop.py` so `_run_stream` no longer needs `# noqa: C901` while preserving the stream event lifecycle, tool-call iteration, max-iteration/max-tool-call handling, usage accounting, and cancellation behavior.
- Update `tinycua_sdk/agent/config.py` so the `skills` field type-checks without `# type: ignore[type-arg]` while preserving Pydantic field defaults and serialization behavior.
- Update `tests/unit/test_loop.py` so the empty async-generator test helper remains valid without an unreachable `yield  # pragma: no cover` line.
- Verify with lint, type checking, unit tests, integration tests, and the full SDK test suite.

---

## Technical Decisions

1. **Merge all skills-related tests into `test_skills.py`**. `test_int_02_skills_creation.py`, `test_int_08_loading_skills_from_directory.py`, and `test_skills_example.py` all cover closely related functionality (skill creation, registry, directory loading, and agent integration). Merging eliminates fragmentation and reduces the number of test files. Keep test classes distinct to preserve the different testing perspectives (unit-style vs. example-driven).

2. **Rename test method prefixes** from numbered (`test_gs_01_*`) to descriptive names. The numbers were tied to old goalspec numbering that no longer exists. Descriptive names are self-documenting.

3. **Keep `conftest.py` and `__init__.py` unchanged**. They already handle LLM server detection and skip logic correctly.

4. **Merge agent export and loading** into one file. Export and loading are two sides of the same serialization concern. Keeping them separate led to duplication (both tested YAML redaction independently).

5. **Remove suppression comments instead of broadening ignore configuration**. The cleanup should improve local code shape and test helpers directly; it should not add new Ruff, mypy, or coverage ignore rules.

6. **Keep suppression cleanup behavior-preserving**. The `loop.py` refactor is allowed only if existing stream/tool behavior remains unchanged and tests continue to pass.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Test method name changes break external references | Low | Medium | No known external references to internal test method names |
| Missed test scenario during merge | Low | High | Audit each merged file to ensure every original test method is present |
| Import errors after file moves | Low | High | Run full test suite after changes |
| Loop refactor changes stream/tool event ordering | Medium | High | Treat existing loop tests as characterization tests; add focused tests before refactor if gaps are found |
| Type-ignore cleanup changes Agent `skills` defaults or validation | Low | High | Verify `Agent()` creation, `Agent.to_config()`, and skill-related tests after the annotation change |
| Coverage-suppression cleanup makes async-generator test stop exercising the empty-stream path | Low | Medium | Keep the test's observable behavior unchanged: empty provider stream still yields response lifecycle completion events |

---

---


## References

- Spec: `./spec.md`
- Project structure rules: `.agents/rules/005-project-structure.md`
- Testing standards: `.agents/rules/003-testing.md`
