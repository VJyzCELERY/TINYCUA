# Implementation: Remove Storage

Delete the entire `storage/` package from `tinycua_sdk`. Persistence (databases, file I/O, session state) is a consumer concern. The SDK must be stateless and perform no I/O.

## Context

- **Spec Reference**: [spec.md](spec.md)
- **Design Reference**: [design.md](design.md)
- **Priority**: P0
- **Estimated Effort**: S

## Proposed Changes

### Storage Package Deletion

#### [DELETE] `tinycua_sdk/storage/__init__.py`

- **[Description of change]**: Remove package init that exports `SessionStore`, `get_session_store`, `MemorySnapshot`, `SnapshotManager`, `SnapshotError`, `LocalStorage`, `Exporter`, and `Importer`.
- **[Rationale]**: Entire storage package is being removed.

#### [DELETE] `tinycua_sdk/storage/models.py`

- **[Description of change]**: Remove SQLAlchemy ORM models (`Base`, `Message`, `Session`, `AgentRecord`).
- **[Rationale]**: Database schema definitions belong in the consumer, not the SDK.

#### [DELETE] `tinycua_sdk/storage/store.py`

- **[Description of change]**: Remove `SessionStore` and `get_session_store` CRUD utilities.
- **[Rationale]**: Session persistence is a consumer concern.

#### [DELETE] `tinycua_sdk/storage/snapshot.py`

- **[Description of change]**: Remove `MemorySnapshot`, `SnapshotManager`, and `SnapshotError`.
- **[Rationale]**: Snapshot management is stateful and belongs in the consumer.

#### [DELETE] `tinycua_sdk/storage/sqlite.py`

- **[Description of change]**: Remove `LocalStorage` (raw `sqlite3` implementation).
- **[Rationale]**: SQLite is an implementation detail and deployment decision, not a framework concern.

#### [DELETE] `tinycua_sdk/storage/importer.py`

- **[Description of change]**: Remove `Importer` logic.
- **[Rationale]**: Import logic is stateful and belongs in the consumer.

#### [DELETE] `tinycua_sdk/storage/export.py`

- **[Description of change]**: Remove `Exporter` logic.
- **[Rationale]**: Export logic is stateful and belongs in the consumer.

### Remove Storage References from Remaining Code

#### [MODIFY] `tinycua_sdk/context/injection.py`

- **[Description of change]**: Remove `from tinycua_sdk.storage.store import get_session_store` and any code that depends on it. Replace with consumer-provided data structures or plain parameters.
- **[Rationale]**: SDK must not reference storage.

#### [MODIFY] `tinycua_sdk/context/compression.py`

- **[Description of change]**: Remove `from tinycua_sdk.storage.models import Message`. Use SDK-native message types (e.g., `ChatMessage`, `Message` from a non-storage module, or plain dicts).
- **[Rationale]**: SDK must not import storage ORM models.

#### [MODIFY] `tinycua_sdk/middleware/hooks.py`

- **[Description of change]**: Remove `from tinycua_sdk.storage.models import Message`. Use SDK-native message types.
- **[Rationale]**: SDK must not import storage ORM models.

#### [MODIFY] `tinycua_sdk/memory/session.py`

- **[Description of change]**: Remove `from tinycua_sdk.storage.sqlite import LocalStorage`. Refactor to accept a consumer-provided store or operate in-memory only.
- **[Rationale]**: SDK must not reference storage backends.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `storage/` package | Remove | Entire package deleted |
| `context/injection.py` | Modify | Remove `get_session_store` dependency |
| `context/compression.py` | Modify | Remove `storage.models.Message` import |
| `middleware/hooks.py` | Modify | Remove `storage.models.Message` import |
| `memory/session.py` | Modify | Remove `LocalStorage` dependency |

## Data Model Changes

No new types added. Existing storage ORM types (`Message`, `Session`, `AgentRecord`, `Base`) are removed. Consumers must define their own persistence schema.

## API Changes

### Removed APIs

| Symbol | Location | Replacement |
|--------|----------|-------------|
| `SessionStore` | `storage/store.py` | Consumer implements own store |
| `get_session_store` | `storage/store.py` | Consumer implements own store |
| `Message` (ORM) | `storage/models.py` | Consumer defines own schema |
| `Session` (ORM) | `storage/models.py` | Consumer defines own schema |
| `LocalStorage` | `storage/sqlite.py` | Consumer implements own storage |
| `SnapshotManager` | `storage/snapshot.py` | Consumer implements own snapshots |
| `MemorySnapshot` | `storage/snapshot.py` | Consumer implements own snapshots |
| `Exporter` | `storage/export.py` | Consumer implements own export |
| `Importer` | `storage/importer.py` | Consumer implements own import |

## Verification Plan

### Automated Tests

- [ ] Run `pytest` in `src/tinycua-sdk/` — all remaining tests pass.
- [ ] Run `make lint` — no import errors or undefined references.

### Manual Verification

- [ ] Confirm `tinycua_sdk/storage/` directory no longer exists.
- [ ] Confirm no `from tinycua_sdk.storage` or `import tinycua_sdk.storage` strings remain in `src/tinycua-sdk/tinycua_sdk/`.
- [ ] Confirm no file I/O or database operations remain in `tinycua_sdk/`.

## Rollout Strategy

1. **Phase 1** (Deletion): Delete all files under `tinycua_sdk/storage/`.
2. **Phase 2** (Cleanup): Remove storage imports from `context/`, `middleware/`, and `memory/` modules.
3. **Phase 3** (Verification): Run `make lint` and `make test` until clean.

## Dependencies

### External Dependencies

None removed or added.

### Internal Dependencies

- **Requires**: Stage 01, Stage 02, Stage 03
- **Blocks**: None (can proceed in parallel with Stages 05–07)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hidden storage imports in non-obvious files | Medium | Use `rg` to search entire `tinycua_sdk/` tree before and after deletion |
| `memory/session.py` heavily depends on `LocalStorage` | Medium | Refactor to in-memory-only or accept an external store interface |
| Tests import deleted symbols | Low | Run `pytest` and delete/update broken tests |

---

*Generated from spec.md and design.md*
*Last updated: 2026-04-29*
