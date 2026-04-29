# Stage 01 — Design: Remove Legacy Tests & Examples

## Overview

Delete all tests, examples, and documentation that depend on modules being removed in subsequent stages. This stage is purely destructive — no new code is written. The goal is to eliminate obsolete test suites so they don't fail during later refactor stages.

## Philosophy

Tests are not sacred. A test that exercises deleted code is worse than no test — it creates false confidence and maintenance burden. We delete tests aggressively and replace them with focused unit tests in Stage 02.

## Files to Delete

### Test Files (entire files)

| File | Reason |
|------|--------|
| `tests/test_storage*.py` | Tests `storage/` module (deleted in Stage 04) |
| `tests/test_memory*.py` | Tests `memory/` module (deleted in Stage 05) |
| `tests/test_short_term_memory.py` | Tests `memory/short_term.py` |
| `tests/test_long_term_memory.py` | Tests `memory/long_term.py` |
| `tests/test_local_storage.py` | Tests `storage/sqlite.py` |
| `tests/test_export_import.py` | Tests `storage/export.py` and `storage/importer.py` |
| `tests/test_cli_*.py` | Tests `cli/` module (deleted in Stage 07) |
| `tests/test_clients.py` | Tests `clients/` module (deleted in Stage 07) |
| `tests/test_client.py` | Tests `clients/client.py` |
| `tests/test_backend_connection.py` | Tests `clients/backend.py` |
| `tests/test_registry.py` | Tests `core/registry.py` (deleted in Stage 08) |
| `tests/test_user_modeling.py` | Tests `modeling/` module (deleted in Stage 06) |
| `tests/test_personality.py` | Tests `modeling/personality.py` |
| `tests/test_remote_runner.py` | Tests remote execution (clients deleted) |
| `tests/test_prompt_cache.py` | Caching is a consumer concern |
| `tests/test_session*.py` | Tests `session/` module (deleted in Stage 03) |

### Example Files

| File | Reason |
|------|--------|
| `docs/examples/example_main.py` | Uses session, memory, storage APIs that are being deleted |
| `docs/examples/README.md` | Documents obsolete APIs |

### Documentation Files

| File | Reason |
|------|--------|
| `docs/session.md` | Documents deleted `session/` module |
| `docs/memory.md` | Documents deleted `memory/` module |
| `docs/storage.md` | Documents deleted `storage/` module |
| `docs/cli.md` | Documents deleted `cli/` module |

## Deletion Strategy

### Order of Operations

1. **Delete test files first** — This immediately reveals which tests are "real" (test framework code) vs. "legacy" (test deleted code).
2. **Delete example files** — Removes broken references from docs.
3. **Delete documentation files** — Prevents confusion for new developers.
4. **Run pytest** — Verify that the remaining tests still pass.

### Safety Checks

Before deleting each file, verify:
- [ ] The file is not imported by any code in `tinycua_sdk/` (only in `tests/`)
- [ ] The file does not test a module that is staying
- [ ] The file is not referenced by `pyproject.toml`, `Makefile`, or CI config

### Verification Command

```bash
# After deletion, verify no broken imports remain
python -c "import tinycua_sdk"

# Run remaining tests to ensure nothing is broken
pytest tests/ -v
```

## Files to Keep

| File | Reason |
|------|--------|
| `tests/test_agent.py` | Tests `Agent` class (staying) |
| `tests/test_tool.py` | Tests `@tool` decorator and `Tool` class (staying) |
| `tests/test_skills.py` | Tests `Skill` dataclass and `SkillRegistry` (staying) |
| `tests/test_config.py` | Tests config classes (staying, refactored) |
| `tests/test_loop.py` | Tests `BaseLoop` (staying, refactored) |
| `tests/test_agent_templates.py` | Tests agent templates (staying, refactored) |

## Risks & Mitigation

| Risk | Mitigation |
|------|-----------|
| Accidentally delete a test for staying code | Review each file before deletion; check imports |
| CI breaks because it expects deleted tests | Update CI config to only run remaining tests |
| Coverage drops to 0% | Expected — Stage 02 adds new unit tests |

## Acceptance Criteria

- [ ] All listed test files are deleted.
- [ ] All listed example files are deleted.
- [ ] All listed documentation files are deleted.
- [ ] `pytest tests/` runs without import errors.
- [ ] Remaining tests (if any) still pass.
- [ ] No references to deleted files in `pyproject.toml`, CI, or Makefile.
