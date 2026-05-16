# Feature Specification: Integration Tests Cleanup

**Status**: Draft
**Created**: 2026-05-16
**Last Updated**: 2026-05-16
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

- **Goals**: Reorganize the tinycua-sdk integration tests to follow project conventions, remove the informal `goals/` subdirectory, deduplicate overlapping test files, and add end-to-end integration tests to increase coverage of real SDK workflows.
- **Gaps**:
  - Integration tests are split between `tests/integration/goals/` (12 files) and `tests/integration/` (2 files), creating confusion about where tests should live.
  - Goal tests use numbered prefixes (`test_gs_*`, `test_int_*`, `test_adv_*`) that do not match the project `test_<topic>.py` convention.
  - Some test files overlap in coverage (e.g., `test_agent_creation.py` vs `test_gs_02_agent_creation.py`, `test_int_06_exporting_agent.py` vs `test_int_07_loading_agent.py`), creating maintenance burden and potential for test drift.
  - No end-to-end integration tests exist that exercise the full SDK workflow (config, agent creation, tool registration, run, result).
- **Non-Goals**:
  - No changes to unit tests.
  - No changes to the SDK source code (only test files are modified).
  - No removal of test coverage — all existing test scenarios must be preserved.
  - No changes to CI/CD or test runner configuration beyond what is needed for reorganization.
- **Constraints**:
  - Must preserve all existing test scenarios and assertions.
  - The `test-integration` Makefile target (`pytest tests/integration/`) must continue to work.
  - The `run_integration_tests.py` script must continue to work.

---

## User Scenarios & Testing

### Primary Scenario

A developer runs integration tests for tinycua-sdk. They run `make test-integration` and all integration tests are discovered and executed — regardless of whether they were previously in `goals/` or not.

### Acceptance Scenarios

1. **Given** a tinycua-sdk checkout with the integration tests reorganized,
   **When** the developer runs `make test-integration`,
   **Then** all integration tests are discovered and executed successfully.

2. **Given** the old `tests/integration/goals/` directory,
   **When** the reorganization is complete,
   **Then** the `goals/` directory no longer exists and all its tests are at `tests/integration/`.

3. **Given** two test files that cover overlapping functionality,
   **When** they are merged,
   **Then** no test scenarios are lost and no assertions are changed.

4. **Given** a new end-to-end integration test,
   **When** it is added,
   **Then** it tests a complete workflow from configuration through agent execution (with environment-based LLM endpoint).

### Edge Cases

- LLM server unavailable: integration tests gracefully skip (handled by existing `conftest.py`).
- External tool references old numbered filenames: those filenames will no longer exist; external references must be updated.

---

## Requirements

### Functional Requirements

- **FR-001**: All integration tests in `tests/integration/goals/` MUST be moved to `tests/integration/` directly.
- **FR-002**: Each moved test file MUST be renamed to follow `test_<topic>.py` convention.
- **FR-003**: The `tests/integration/goals/` directory MUST be removed after all tests are migrated.
- **FR-004**: Tests covering overlapping functionality MUST be merged into single files to eliminate duplication.
- **FR-005**: All unique test scenarios and assertions MUST be preserved during the move and merge. Duplicate test methods (same scenario covered by multiple original files) MAY be removed, provided a merge traceability table documents which original methods are covered by each new method.
- **FR-006**: New end-to-end integration tests MUST be added that cover full SDK workflows (agent creation, tool registration, run with real or mock LLM endpoint).
- **FR-007**: The `make test-integration` target MUST continue to discover and run all integration tests.
- **FR-008**: The `run_integration_tests.py` script MUST continue to work without modification.
- **FR-009**: Integration tests that require a live LLM server MUST continue to be skipped gracefully when the server is unavailable (via existing conftest.py logic).

### Test File Mapping

#### Tests to move from `goals/`

| Current Path | New Name |
|---|---|
| `goals/test_gs_01_language_model_definition.py` | `test_language_model.py` |
| `goals/test_gs_02_agent_creation.py` | Merge into `test_agent_creation.py` |
| `goals/test_gs_04_agent_streaming.py` | `test_agent_streaming.py` |
| `goals/test_int_01_tool_creation.py` | `test_tool_creation.py` |
| `goals/test_int_02_skills_creation.py` | Merge into `test_skills.py` |
| `goals/test_int_06_exporting_agent.py` | Merge into `test_agent_export.py` |
| `goals/test_int_07_loading_agent.py` | Merge into `test_agent_export.py` |
| `goals/test_int_08_loading_skills_from_directory.py` | Merge into `test_skills.py` |
| `goals/test_int_09_loading_tools_from_directory.py` | `test_tool_loading.py` |
| `goals/test_adv_01_custom_agent_loop.py` | `test_custom_agent_loop.py` |
| `goals/test_adv_02_guardrail_system.py` | `test_guardrail_system.py` |
| `goals/test_adv_03_permission_system.py` | `test_permission_system.py` |

#### Existing tests at `tests/integration/`

| Current File | Action |
|---|---|
| `test_agent_creation.py` | Expand with merged content from `goals/test_gs_02_agent_creation.py` |
| `test_skills_example.py` | Merge into `test_skills.py` |

---

## Success Criteria

- [ ] `make test-integration` passes: all integration tests succeed or skip gracefully for LLM-dependent tests.
- [ ] `goals/` directory removed: no tests remain under `tests/integration/goals/`.
- [ ] All test scenarios preserved: every unique test scenario from original files exists in the new structure; duplicate methods may be removed per merge traceability.
- [ ] Overlapping tests merged: duplicate test files are consolidated (agent creation, agent export/loading).
- [ ] New end-to-end tests added: at least one end-to-end integration test covering a full agent workflow.
- [ ] Naming consistent: all integration test files follow `test_<topic>.py` convention.

---

## Testing Plan

### Unit Tests

No new unit tests needed — this spec addresses reorganization of integration tests only.

### Integration Tests

- All existing integration tests will be verified to work in their new locations and under their new names.
- New end-to-end integration tests will be added covering full agent workflows.
- Tests will be run with both `make test-integration` and `uv run pytest tests/integration/`.

### Manual Tests

- Run the full test suite (`uv run pytest`) to confirm no regressions.
- Run `make test-integration` to verify the Makefile target works.

---

## Resolved Questions

1. **Should skills-related tests be merged into a single file?**
   - **Decision**: YES. Merge `test_int_02_skills_creation.py`, `test_int_08_loading_skills_from_directory.py`, and `test_skills_example.py` into a single `test_skills.py`. The three files cover closely related functionality (skill creation, registry, directory loading, and agent integration) and merging eliminates fragmentation. The resulting file will be larger but simpler to maintain.

2. **Should internal test method names be renamed from `test_gs_*` / `test_int_*` / `test_adv_*` to descriptive names?**
   - **Decision**: YES. The numbered prefixes are tied to old goalspec numbering that no longer exists. Rename to descriptive names alongside the filenames.
