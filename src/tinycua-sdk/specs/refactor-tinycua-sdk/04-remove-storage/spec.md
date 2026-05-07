# Stage 04 — Remove Storage

## Objective

Delete the entire `storage/` package. Persistence is a consumer concern.

## Files to Delete

| File | Reason |
|------|--------|
| `storage/__init__.py` | Package init |
| `storage/models.py` | Session/Message ORM models — belong in consumer |
| `storage/store.py` | SessionStore — stateful CRUD |
| `storage/snapshot.py` | SnapshotManager — stateful |
| `storage/sqlite.py` | LocalStorage — raw sqlite3, stateful |
| `storage/importer.py` | Importer — stateful |
| `storage/export.py` | Exporter — stateful |

## Code Changes

### Remove Storage References

Search for imports from `tinycua_sdk.storage` across the codebase:
```bash
rg "from tinycua_sdk.storage" src/
rg "import tinycua_sdk.storage" src/
```

Update any code that imports from `storage` to either:
- Remove the import (if the code is also being deleted)
- Use consumer-provided data structures instead

### Update Agent

Remove any `SessionStore` references from `Agent` or `AgentExecutor`.

## Acceptance Criteria

- [ ] `storage/` directory does not exist.
- [ ] No imports from `tinycua_sdk.storage` remain in the codebase.
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02, Stage 03
