# Task List: Stage 01 — Remove Legacy Tests & Examples

## Implementation Phase

<!-- id: 1 -->
- [x] Audit `tests/unit/` directory and identify all files matching deletion criteria
<!-- id: 2 -->
- [x] DELETE `tests/unit/test_storage*.py`
<!-- id: 3 -->
- [x] DELETE `tests/unit/test_memory*.py`
<!-- id: 4 -->
- [x] DELETE `tests/unit/test_memory_plugin.py`
<!-- id: 5 -->
- [x] DELETE `tests/unit/test_memory_snapshot.py`
<!-- id: 6 -->
- [x] DELETE `tests/unit/test_short_term_memory.py`
<!-- id: 7 -->
- [x] DELETE `tests/unit/test_long_term_memory.py`
<!-- id: 8 -->
- [x] DELETE `tests/unit/test_local_storage.py`
<!-- id: 9 -->
- [x] DELETE `tests/unit/test_export_import.py`
<!-- id: 10 -->
- [x] DELETE `tests/unit/test_cli_*.py` (no files matched; also deleted `test_agent_commands.py` as CLI test)
<!-- id: 11 -->
- [x] DELETE `tests/unit/test_clients.py`
<!-- id: 12 -->
- [x] DELETE `tests/unit/test_client.py`
<!-- id: 13 -->
- [x] DELETE `tests/unit/test_backend_connection.py`
<!-- id: 14 -->
- [x] DELETE `tests/unit/test_registry.py`
<!-- id: 15 -->
- [x] DELETE `tests/unit/test_user_modeling.py`
<!-- id: 16 -->
- [x] DELETE `tests/unit/test_personality.py`
<!-- id: 17 -->
- [x] DELETE `tests/unit/test_remote_runner.py`
<!-- id: 18 -->
- [x] DELETE `tests/unit/test_prompt_cache.py`
<!-- id: 19 -->
- [x] DELETE `tests/unit/test_context_tools.py` (file did not exist)
<!-- id: 20 -->
- [x] DELETE `tests/unit/test_context_compression.py`
<!-- id: 21 -->
- [x] DELETE `tests/unit/test_context_discovery.py`
<!-- id: 22 -->
- [x] Audit `tests/integration/` directory and identify all files matching deletion criteria
<!-- id: 23 -->
- [x] DELETE `tests/integration/test_memory_*.py`
<!-- id: 24 -->
- [x] DELETE `tests/integration/test_storage_agent.py`
<!-- id: 25 -->
- [x] DELETE `tests/integration/test_local_run.py`
<!-- id: 26 -->
- [x] DELETE `tests/integration/test_agent_delegation.py`
<!-- id: 27 -->
- [x] DELETE `tests/integration/test_hooks_pipeline.py`
<!-- id: 28 -->
- [x] DELETE `tests/integration/test_context_pipeline.py`
<!-- id: 29 -->
- [x] DELETE `tests/integration/test_runner_integration.py`
<!-- id: 30 -->
- [x] DELETE `docs/examples/example_main.py`
<!-- id: 31 -->
- [x] DELETE `docs/examples/README.md` (file did not exist)
<!-- id: 32 -->
- [x] DELETE `docs/session.md` (file did not exist)
<!-- id: 33 -->
- [x] DELETE `docs/memory.md` (file did not exist)
<!-- id: 34 -->
- [x] DELETE `docs/storage.md` (file did not exist)
<!-- id: 35 -->
- [x] DELETE `docs/cli.md` (file did not exist)
<!-- id: 36 -->
- [x] Audit `pyproject.toml`, CI config, and `Makefile` for references to deleted files
<!-- id: 37 -->
- [x] MODIFY `pyproject.toml` — remove any hardcoded paths to deleted tests/examples (no hardcoded paths found)
<!-- id: 38 -->
- [x] MODIFY CI configuration — update test commands to only run remaining tests (no CI config found with hardcoded paths)
<!-- id: 39 -->
- [x] MODIFY `Makefile` — remove any targets referencing deleted tests or examples (no hardcoded references found)

## Testing Phase

<!-- id: 40 -->
- [x] Run `python -c "import tinycua_sdk"` to confirm package imports without errors
<!-- id: 41 -->
- [x] Run `pytest tests/ --collect-only` to confirm no collection/import errors (432 tests collected)
<!-- id: 42 -->
- [x] Run `pytest tests/unit/test_agent.py -v` and verify it passes (6 passed)
<!-- id: 43 -->
- [x] Run `pytest tests/unit/test_tool.py -v` and verify it passes (7 passed)
<!-- id: 44 -->
- [x] Run `pytest tests/unit/test_skills.py -v` and verify it passes (21 passed)
<!-- id: 45 -->
- [x] Run `pytest tests/unit/test_config.py -v` and verify it passes (12 passed)
<!-- id: 46 -->
- [x] Run `pytest tests/unit/test_loop.py -v` and verify it passes (15 passed)
<!-- id: 47 -->
- [x] Run `pytest tests/unit/test_agent_templates.py -v` and verify it passes (24 passed)
<!-- id: 48 -->
- [x] Run `pytest tests/ -v` and verify all remaining tests pass (430 passed, 2 pre-existing failures in `test_tool_execution.py` unrelated to deletions)

## Verification Phase

<!-- id: 49 -->
- [x] Search `tests/` directory for any remaining imports of deleted modules (storage, memory, cli, clients, registry, modeling, session) — none found
<!-- id: 50 -->
- [x] Verify no deleted files are referenced in `pyproject.toml`
<!-- id: 51 -->
- [x] Verify no deleted files are referenced in CI configuration (`.github/workflows/`, `.gitlab-ci.yml`, etc.)
<!-- id: 52 -->
- [x] Verify no deleted files are referenced in `Makefile`
<!-- id: 53 -->
- [x] Confirm files-to-keep list is intact: `test_agent.py`, `test_tool.py`, `test_skills.py`, `test_config.py`, `test_loop.py`, `test_agent_templates.py`
<!-- id: 54 -->
- [x] If any test file partially tests staying code, split it and preserve the staying portion before marking deletion complete (none found)

## Documentation Phase

<!-- id: 55 -->
- [ ] Update project changelog or refactor log to note which tests/examples/docs were removed in Stage 01
<!-- id: 56 -->
- [ ] Document expected coverage drop and note that Stage 02 will add replacement unit tests

## Review and Merge

<!-- id: 57 -->
- [ ] Self-review: confirm all deletions align with spec.md and design.md
<!-- id: 58 -->
- [ ] Open pull request with clear description of deletions and expected CI impact
<!-- id: 59 -->
- [ ] Ensure CI passes with updated configuration
<!-- id: 60 -->
- [ ] Merge to main / development branch
<!-- id: 61 -->
- [ ] Tag or mark Stage 01 as complete in project tracker
