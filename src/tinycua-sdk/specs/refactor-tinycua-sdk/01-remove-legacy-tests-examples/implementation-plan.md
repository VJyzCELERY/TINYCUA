# Implementation Plan: Stage 01 — Remove Legacy Tests & Examples

## Context

| Field | Value |
|-------|-------|
| **Priority** | P0 — Must be completed first; blocks all subsequent refactor stages |
| **Effort** | Small (pure deletion, no new code) |
| **Dependencies** | None — this is the foundational stage |
| **Stage** | 01 of 13 |

This stage is purely destructive. We delete tests, examples, and documentation that depend on modules being removed in later stages. Executing this first ensures that later stages are not blocked by failing tests for deleted code.

---

## Proposed Changes

### Unit Test Files (DELETE)

<!-- id: 1 -->
- [ ] DELETE `tests/unit/test_storage*.py` — Tests `storage/` module (deleted in Stage 04)
- [ ] DELETE `tests/unit/test_memory*.py` — Tests `memory/` module (deleted in Stage 05)
- [ ] DELETE `tests/unit/test_memory_plugin.py` — Tests `memory/` plugin system
- [ ] DELETE `tests/unit/test_memory_snapshot.py` — Tests `memory/` snapshot functionality
- [ ] DELETE `tests/unit/test_short_term_memory.py` — Tests `memory/short_term.py`
- [ ] DELETE `tests/unit/test_long_term_memory.py` — Tests `memory/long_term.py`
- [ ] DELETE `tests/unit/test_local_storage.py` — Tests `storage/sqlite.py`
- [ ] DELETE `tests/unit/test_export_import.py` — Tests `storage/export.py` and `storage/importer.py`
- [ ] DELETE `tests/unit/test_cli_*.py` — Tests `cli/` module (deleted in Stage 07)
- [ ] DELETE `tests/unit/test_clients.py` — Tests `clients/` module (deleted in Stage 07)
- [ ] DELETE `tests/unit/test_client.py` — Tests `clients/client.py`
- [ ] DELETE `tests/unit/test_backend_connection.py` — Tests `clients/backend.py`
- [ ] DELETE `tests/unit/test_registry.py` — Tests `core/registry.py` (deleted in Stage 08)
- [ ] DELETE `tests/unit/test_user_modeling.py` — Tests `modeling/` module (deleted in Stage 06)
- [ ] DELETE `tests/unit/test_personality.py` — Tests `modeling/personality.py`
- [ ] DELETE `tests/unit/test_remote_runner.py` — Tests remote execution (clients deleted)
- [ ] DELETE `tests/unit/test_prompt_cache.py` — Caching is a consumer concern
- [ ] DELETE `tests/unit/test_context_tools.py` — Depends on memory/session
- [ ] DELETE `tests/unit/test_context_compression.py` — Context compression is consumer concern
- [ ] DELETE `tests/unit/test_context_discovery.py` — Depends on session

### Integration Test Files (DELETE)

<!-- id: 2 -->
- [ ] DELETE `tests/integration/test_memory_*.py` — Tests `memory/` module
- [ ] DELETE `tests/integration/test_storage_agent.py` — Tests `storage/` module
- [ ] DELETE `tests/integration/test_local_run.py` — Depends on storage/session
- [ ] DELETE `tests/integration/test_agent_delegation.py` — Depends on remote client
- [ ] DELETE `tests/integration/test_hooks_pipeline.py` — Depends on removed modules
- [ ] DELETE `tests/integration/test_context_pipeline.py` — Depends on removed modules
- [ ] DELETE `tests/integration/test_runner_integration.py` — Runner depends on removed modules

### Example Files (DELETE)

<!-- id: 3 -->
- [ ] DELETE `docs/examples/example_main.py` — Uses session, memory, storage APIs being deleted
- [ ] DELETE `docs/examples/README.md` — Documents obsolete APIs

### Documentation Files (DELETE)

<!-- id: 4 -->
- [ ] DELETE `docs/session.md` — Documents deleted `session/` module
- [ ] DELETE `docs/memory.md` — Documents deleted `memory/` module
- [ ] DELETE `docs/storage.md` — Documents deleted `storage/` module
- [ ] DELETE `docs/cli.md` — Documents deleted `cli/` module

### Configuration / CI Updates (MODIFY)

<!-- id: 5 -->
- [ ] MODIFY `pyproject.toml` — Remove references to deleted test paths if present
- [ ] MODIFY CI configuration — Update test commands to only run remaining tests
- [ ] MODIFY `Makefile` — Remove references to deleted tests or examples

---

## Architecture Changes

There are **no architectural changes** in this stage. This stage is purely cleanup. The goal is to remove obsolete artifacts without altering the remaining codebase structure.

Key principle: **Tests are not sacred.** A test that exercises deleted code is worse than no test — it creates false confidence and maintenance burden. Deleted tests will be replaced with focused unit tests in Stage 02.

---

## Verification Plan

| Step | Command / Action | Expected Result |
|------|------------------|-----------------|
| 1 | `python -c "import tinycua_sdk"` | Package imports successfully with no errors |
| 2 | `pytest tests/ --collect-only` | Test collection completes without import errors |
| 3 | `pytest tests/unit/test_agent.py -v` | Passes |
| 4 | `pytest tests/unit/test_tool.py -v` | Passes |
| 5 | `pytest tests/unit/test_skills.py -v` | Passes |
| 6 | `pytest tests/unit/test_config.py -v` | Passes |
| 7 | `pytest tests/unit/test_loop.py -v` | Passes |
| 8 | `pytest tests/unit/test_agent_templates.py -v` | Passes |
| 9 | `pytest tests/ -v` | All remaining tests pass |
| 10 | Search for imports of deleted modules in `tests/` | No references found |

---

## Dependencies

| Dependency | Reason |
|------------|--------|
| None | This stage has no upstream dependencies; it is the first stage |

**Downstream impact:** All subsequent stages (02–13) depend on this stage being complete.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Accidentally delete a test for staying code | Medium | High | Review each file before deletion; verify it does not test `Agent`, `Tool`, `Skill`, `Config`, `BaseLoop`, or templates. Check imports against source tree. |
| CI breaks because it expects deleted tests | Medium | Medium | Audit `pyproject.toml`, CI config, and `Makefile` for hardcoded test paths; update them before merging. |
| Coverage drops to 0% | High | Low | Expected and acceptable — Stage 02 adds new unit tests. Document this in PR description. |
| Partial test file tests both deleted and staying code | Low | High | If discovered, split the file first (extract staying tests into a new file) before deleting the legacy portion. |
| Hidden imports of deleted test utilities | Medium | Medium | Run `pytest --collect-only` to surface any import errors from shared test fixtures or conftest.py. |

---

## Order of Operations

1. **Delete test files first** — Immediately reveals which tests are "real" vs. "legacy."
2. **Delete example files** — Removes broken references from docs.
3. **Delete documentation files** — Prevents confusion for new developers.
4. **Update configuration** — Ensure CI, `pyproject.toml`, and `Makefile` don't reference deleted files.
5. **Run verification** — Execute the full verification plan.

---

## Files to Keep (Do Not Delete)

| File | Reason |
|------|--------|
| `tests/unit/test_agent.py` | Tests `Agent` class (staying) |
| `tests/unit/test_tool.py` | Tests `@tool` decorator and `Tool` class (staying) |
| `tests/unit/test_skills.py` | Tests `Skill` dataclass and `SkillRegistry` (staying) |
| `tests/unit/test_config.py` | Tests config classes (staying, refactored) |
| `tests/unit/test_loop.py` | Tests `BaseLoop` (staying, refactored) |
| `tests/unit/test_agent_templates.py` | Tests agent templates (staying, refactored) |

---

## Acceptance Criteria

- [ ] All listed test files are deleted.
- [ ] All listed example files are deleted.
- [ ] All listed documentation files are deleted.
- [ ] `pytest tests/` runs without import errors.
- [ ] Remaining tests (if any) still pass.
- [ ] No references to deleted files in `pyproject.toml`, CI configuration, or `Makefile`.
