# Feature Specification: Integration Tests Cleanup

**Status**: Complete
**Created**: 2026-05-16
**Last Updated**: 2026-05-16
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

- **Goals**: Reorganize the tinycua-sdk integration tests to follow project conventions, remove the informal `goals/` subdirectory, deduplicate overlapping test files, add end-to-end integration tests to increase coverage of real SDK workflows, and clean up targeted inline suppression comments discovered during SDK review.
- **Gaps**:
  - Integration tests are split between `tests/integration/goals/` (12 files) and `tests/integration/` (2 files), creating confusion about where tests should live.
  - Goal tests use numbered prefixes (`test_gs_*`, `test_int_*`, `test_adv_*`) that do not match the project `test_<topic>.py` convention.
  - Some test files overlap in coverage (e.g., `test_agent_creation.py` vs `test_gs_02_agent_creation.py`, `test_int_06_exporting_agent.py` vs `test_int_07_loading_agent.py`), creating maintenance burden and potential for test drift.
  - No end-to-end integration tests exist that exercise the full SDK workflow (config, agent creation, tool registration, run, result).
  - A small number of inline suppression comments remain in SDK source/tests and should either be removed by simplifying code or replaced with coverage/type-checker-friendly patterns:
    - `tinycua_sdk/agent/loop.py` suppresses `C901` complexity on `_run_stream` with `# noqa: C901`.
    - `tinycua_sdk/agent/config.py` suppresses a type argument warning on the `skills` field with `# type: ignore[type-arg]`.
    - `tests/unit/test_loop.py` suppresses unreachable async-generator stub coverage with `# pragma: no cover`.
- **Non-Goals**:
  - No broad changes to unit tests beyond the targeted `test_loop.py` coverage-suppression cleanup.
  - No broad SDK source code changes beyond the targeted suppression cleanup in `loop.py` and `config.py`.
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
- **FR-010**: The SDK MUST remove the inline `# noqa: C901` suppression from `tinycua_sdk/agent/loop.py` by reducing `_run_stream` complexity while preserving streaming and tool-call behavior.
- **FR-011**: The SDK MUST remove the inline `# type: ignore[type-arg]` suppression from `tinycua_sdk/agent/config.py` while preserving the `skills` field behavior and validation contract.
- **FR-012**: The SDK test suite MUST remove the inline `# pragma: no cover` suppression from `tests/unit/test_loop.py` while preserving the async-generator test scenario.
- **FR-013**: The targeted suppression cleanup MUST pass lint, type-checking where configured, unit tests, integration tests, and the full SDK test suite.

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

- [x] `make test-integration` passes: all integration tests succeed or skip gracefully for LLM-dependent tests (80 discovered, 80 passed).
- [x] `goals/` directory removed: no tests remain under `tests/integration/goals/`.
- [x] All test scenarios preserved: every unique test scenario from original files exists in the new structure; duplicate methods removed per merge traceability.
- [x] Overlapping tests merged: duplicate test files are consolidated (agent creation, agent export/loading, skills).
- [x] New end-to-end tests added: end-to-end integration tests covering full agent workflow, tool calling, and skills/tools integration.
- [x] Naming consistent: all integration test files follow `test_<topic>.py` convention.
- [x] Inline suppressions cleaned up: targeted `# noqa: C901`, `# type: ignore[type-arg]`, and `# pragma: no cover` comments are removed without behavior regression.

---

## Testing Plan

### Unit Tests

- Existing unit tests will be preserved for the integration-test reorganization work.
- The targeted `test_loop.py` cleanup will keep the async-generator behavior under unit test without relying on `# pragma: no cover`.
- Existing loop/config unit tests will be used as characterization coverage before refactoring `loop.py` and `config.py`.

### Integration Tests

- All existing integration tests will be verified to work in their new locations and under their new names.
- New end-to-end integration tests will be added covering full agent workflows.
- Tests will be run with both `make test-integration` and `uv run pytest tests/integration/`.

### Manual Tests

- Run the full test suite (`uv run pytest`) to confirm no regressions.
- Run `make test-integration` to verify the Makefile target works.
- Run lint/type-check commands for the suppression cleanup scope to confirm the removed comments are no longer needed.

---

## Resolved Questions

1. **Should skills-related tests be merged into a single file?**
   - **Decision**: YES. Merge `test_int_02_skills_creation.py`, `test_int_08_loading_skills_from_directory.py`, and `test_skills_example.py` into a single `test_skills.py`. The three files cover closely related functionality (skill creation, registry, directory loading, and agent integration) and merging eliminates fragmentation. The resulting file will be larger but simpler to maintain.

2. **Should internal test method names be renamed from `test_gs_*` / `test_int_*` / `test_adv_*` to descriptive names?**
   - **Decision**: YES. The numbered prefixes are tied to old goalspec numbering that no longer exists. Rename to descriptive names alongside the filenames.

3. **Should `test_obsolete_params_rejected` be preserved?**
   - **Decision**: NO. This test validated that old backward-compatible parameters raised `TypeError`, but backward compatibility is no longer needed. The test and its associated `pytest` import have been removed from `TestAgentConstructor`.
