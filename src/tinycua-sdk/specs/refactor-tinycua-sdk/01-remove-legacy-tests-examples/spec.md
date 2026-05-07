# Stage 01 — Remove Legacy Tests & Examples

## Objective

Delete all tests and examples that reference modules being removed in the refactor. This stage must be done first so that later stages are not blocked by failing tests for deleted code.

## Files to Delete

### Unit Tests

| File | Reason |
|------|--------|
| `tests/unit/test_storage*.py` | `storage/` deleted |
| `tests/unit/test_memory*.py` | `memory/` deleted |
| `tests/unit/test_memory_plugin.py` | `memory/` deleted |
| `tests/unit/test_memory_snapshot.py` | `memory/` deleted |
| `tests/unit/test_short_term_memory.py` | `memory/` deleted |
| `tests/unit/test_long_term_memory.py` | `memory/` deleted |
| `tests/unit/test_local_storage.py` | `storage/` deleted |
| `tests/unit/test_export_import.py` | import/export deleted |
| `tests/unit/test_cli_*.py` | `cli/` deleted |
| `tests/unit/test_clients.py` | `clients/` deleted |
| `tests/unit/test_client.py` | `clients/` deleted |
| `tests/unit/test_backend_connection.py` | `clients/` deleted |
| `tests/unit/test_registry.py` | `core/registry.py` deleted |
| `tests/unit/test_user_modeling.py` | `modeling/` deleted |
| `tests/unit/test_personality.py` | `modeling/` deleted |
| `tests/unit/test_remote_runner.py` | remote runner deleted |
| `tests/unit/test_prompt_cache.py` | caching is consumer concern |
| `tests/unit/test_context_tools.py` | if it depends on memory/session |
| `tests/unit/test_context_compression.py` | context compression is consumer concern |
| `tests/unit/test_context_discovery.py` | if it depends on session |

### Integration Tests

| File | Reason |
|------|--------|
| `tests/integration/test_memory_*.py` | `memory/` deleted |
| `tests/integration/test_storage_agent.py` | `storage/` deleted |
| `tests/integration/test_local_run.py` | depends on storage/session |
| `tests/integration/test_agent_delegation.py` | if it depends on remote client |
| `tests/integration/test_hooks_pipeline.py` | if it depends on removed modules |
| `tests/integration/test_context_pipeline.py` | if it depends on removed modules |
| `tests/integration/test_runner_integration.py` | runner depends on removed modules |

### Examples

| File | Reason |
|------|--------|
| `docs/examples/example_main.py` | will be rewritten in stage 13 |

## Acceptance Criteria

- [ ] All listed test files are deleted.
- [ ] Remaining tests still pass (`pytest tests/unit/test_agent.py`, `pytest tests/unit/test_tool.py`, etc.).
- [ ] No test imports from deleted modules.
- [ ] `pytest --collect-only` does not error.

## Notes

- Do NOT delete tests for modules that are staying: `test_agent.py`, `test_tool.py`, `test_skills.py`, `test_config.py`, `test_loop.py`, `test_agent_templates.py`, etc.
- If a test file partially tests staying code, split it first or update it instead of deleting.
