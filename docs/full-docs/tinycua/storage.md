# Storage Module Documentation

The storage module provides local data persistence for TinyCUA, including SQLite database management, key-value memory storage, session storage wrappers, and data migration (export/import).

---

## Module Structure

```
storage/
├── __init__.py              # Re-exports all public classes
├── local_storage.py         # SQLite database manager
├── local_memory_store.py    # Key-value memory store
├── local_session_store.py   # Session store wrapper
├── export_manager.py        # Data export to JSON/ZIP
└── import_manager.py        # Data import from JSON/ZIP
```

---

## `storage/__init__.py`

Re-exports all public storage classes for convenient imports:

```python
from tinycua.storage.export_manager import ExportManager, ExportOptions, ExportResult
from tinycua.storage.import_manager import ImportManager, ImportMode, ImportResult, ImportValidation
from tinycua.storage.local_memory_store import LocalMemoryStore
from tinycua.storage.local_session_store import LocalSessionStore
from tinycua.storage.local_storage import LocalStorageManager
```

---

## `storage/local_storage.py`

### Purpose

Manages the local SQLite database file (`~/.tinycua/data.db`) and provides access to the SDK's `SessionStore`.

### `LocalStorageManager` Class

**Singleton pattern:**
```python
class LocalStorageManager:
    _instance: Optional[LocalStorageManager] = None
    _initialized: bool = False
```

**Why singleton?** Ensures only one database connection pool exists, preventing SQLite locking issues when multiple parts of the app access the database concurrently.

### `__init__()`

```python
def __init__(self, db_path: Optional[Path] = None) -> None:
    self._db_path = db_path or DEFAULT_DB_PATH  # ~/.tinycua/data.db
    self._ensure_directory()
```

### `get_instance()` — Class Method

```python
@classmethod
def get_instance(cls, db_path: Optional[Path] = None) -> LocalStorageManager:
    if cls._instance is None:
        cls._instance = cls(db_path)
    return cls._instance
```

### `initialize()`

```python
def initialize(self) -> bool:
```

Creates database tables via the SDK's `SessionStore`:
```python
from tinycua_sdk.storage.store import SessionStore
store = SessionStore(self.database_url)
store.create_tables()
self._initialized = True
```

**Returns:** `True` on success, `False` on failure.

### `get_store()`

```python
def get_store(self):
```

Returns a new `SessionStore` instance or `None` on error.

**Note:** Returns a new instance each time, not a cached one. The SDK's `SessionStore` manages its own connection pooling.

### `backup()`

```python
def backup(self, backup_path: Optional[Path] = None) -> bool:
```

Creates a file copy of the database using `shutil.copy2()`.

**Default backup path:** `{db_path}.backup`

### `get_storage_info()`

```python
def get_storage_info(self) -> dict:
```

Returns:
```python
{
    "db_path": str,
    "exists": bool,
    "size_bytes": int,
    "initialized": bool,
}
```

---

## `storage/local_memory_store.py`

### Purpose

Provides a local key-value memory store using SQLite and SQLAlchemy ORM.

**Note from source code:**
> This component is implemented for future use. Integration with the agent system for persistent memory/knowledge storage will be completed in a future stage.

### `MemoryModel` SQLAlchemy Model

```python
class MemoryModel(Base):
    __tablename__ = "memory"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

### `LocalMemoryStore` Class

```python
class LocalMemoryStore:
    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            db_path = str(Path.home() / ".tinycua" / "data.db")
        self._db_url = f"sqlite:///{db_path}"
        self._engine = create_engine(self._db_url)
        self._Session = sessionmaker(bind=self._engine)
        self._ensure_tables()
```

### CRUD Operations

| Method | Signature | Returns |
|--------|-----------|---------|
| `set` | `(key: str, value: Any) -> bool` | True on success |
| `get` | `(key: str, default: Any = None) -> Any` | Value or default |
| `delete` | `(key: str) -> bool` | True if deleted |
| `list_keys` | `() -> list[str]` | Sorted list of keys |
| `clear` | `() -> bool` | True on success |

### `set()` Implementation Details

```python
def set(self, key: str, value: Any) -> bool:
    session = self._Session()
    try:
        existing = session.get(MemoryModel, key)
        if existing:
            existing.value = cast(str, json.dumps(value))
            existing.updated_at = datetime.utcnow()
        else:
            mem = MemoryModel(
                key=key,
                value=json.dumps(value),
                updated_at=datetime.utcnow(),
            )
            session.add(mem)
        session.commit()
        return True
    except (OSError, SQLAlchemyError, ValueError):
        logger.exception("Failed to set memory: %s", key)
        session.rollback()
        return False
    finally:
        session.close()
```

**Key points:**
- Uses `session.get(MemoryModel, key)` for primary key lookup
- Values are JSON-serialized before storage
- Uses explicit `session.commit()` / `session.rollback()`
- Always closes session in `finally` block
- `datetime.utcnow()` for timestamps

### `get()` Implementation Details

```python
def get(self, key: str, default: Any = None) -> Any:
    session = self._Session()
    try:
        mem = session.get(MemoryModel, key)
        if mem is None:
            return default
        return json.loads(cast(str, mem.value))
    except (OSError, SQLAlchemyError, ValueError):
        logger.exception("Failed to get memory: %s", key)
        return default
    finally:
        session.close()
```

Values are deserialized from JSON on retrieval.

---

## `storage/local_session_store.py`

### Purpose

Wraps the SDK's `SessionStore` with exception translation to TinyCUA's custom `StorageError`.

### `LocalSessionStore` Class

```python
class LocalSessionStore:
    def __init__(self, store: SessionStore) -> None:
        self._store = store
```

**Wrapper pattern:** Every method delegates to the underlying `SessionStore` and translates exceptions.

### Exception Translation Pattern

```python
def create_session(self, name: str, user_id: str | None = None, session_id: uuid.UUID | None = None) -> Session:
    try:
        return self._store.create_session(name=name, user_id=user_id, session_id=session_id)
    except (OSError, ValueError, TypeError) as exc:
        raise StorageError(f"Failed to create session: {exc}") from exc
```

**Why translate exceptions?** Provides a unified exception type (`StorageError`) that callers can catch without knowing the underlying store implementation.

### Methods

| Method | Delegates To | Raises |
|--------|-------------|--------|
| `create_session()` | `store.create_session()` | `StorageError` |
| `get_session()` | `store.get_session()` | `StorageError` |
| `get_session_by_name()` | `store.get_session_by_name()` | `StorageError` |
| `list_sessions()` | `store.list_sessions()` | `StorageError` |
| `update_session()` | `store.update_session()` | `StorageError` |
| `delete_session()` | `store.delete_session()` | `StorageError` |
| `add_message()` | `store.add_message()` | `StorageError` |
| `get_messages()` | `store.get_messages()` | `StorageError` |
| `get_recent_turns()` | `store.get_recent_turns()` | `StorageError` |

---

## `storage/export_manager.py`

### Purpose

Exports TinyCUA data (sessions, agents, memory, skills) to JSON or ZIP files.

### `ExportOptions` Dataclass

```python
@dataclass
class ExportOptions:
    include_sessions: bool = True
    include_agents: bool = True
    include_memory: bool = True
    include_skills: bool = True
    session_ids: list[str] | None = None
    agent_ids: list[str] | None = None
```

### `ExportResult` Dataclass

```python
@dataclass
class ExportResult:
    success: bool
    output_path: Path | None = None
    items_exported: int = 0
    error: str | None = None
```

### `ExportManager` Class

```python
class ExportManager:
    EXPORT_VERSION = "1.0"

    def __init__(
        self,
        session_store: LocalSessionStore,
        agent_manager: AgentManager,
        memory_store: LocalMemoryStore,
        skills_manager: SkillsManager,
    ) -> None:
```

### `export()` — JSON Export

```python
def export(self, output_path: Path, options: ExportOptions | None = None) -> ExportResult:
```

**Data structure:**
```json
{
  "version": "1.0",
  "exported_at": "2024-01-01T00:00:00Z",
  "data": {
    "sessions": [...],
    "agents": [...],
    "memory": {...},
    "skills": [...]
  }
}
```

### `export_zip()` — ZIP Export

```python
def export_zip(self, output_path: Path, options: ExportOptions | None = None) -> ExportResult:
```

Creates a ZIP archive containing a single `export.json` file.

### `_export_sessions()`

```python
def _export_sessions(self, session_ids: list[str] | None = None) -> list[dict[str, Any]]:
```

Exports sessions with full message history:
```python
{
    "id": str(session.id),
    "name": session.name,
    "user_id": session.user_id,
    "created_at": session.created_at.isoformat(),
    "updated_at": session.updated_at.isoformat(),
    "metadata": session.metadata or {},
    "messages": [
        {
            "id": str(msg.id),
            "role": msg.role,
            "content": msg.content,
            "reasoning": msg.reasoning,
            "turn_index": msg.turn_index,
            "created_at": msg.created_at.isoformat(),
        }
        for msg in messages
    ],
}
```

**Note:** Message content is exported verbatim. Sensitive data in messages will be included in the export.

### `_export_agents()`

```python
def _export_agents(self, agent_ids: list[str] | None = None) -> list[dict[str, Any]]:
```

**Security consideration:** Agent configs are serialized with `redact_sensitive=True`:
```python
config_json = agent.config.to_json(redact_sensitive=True)
```

This ensures API keys and other secrets are not included in exports.

### `_export_memory()`

```python
def _export_memory(self) -> dict[str, Any]:
```

Exports all memory key-value pairs as a flat dictionary.

### `_export_skills()`

```python
def _export_skills(self) -> list[dict[str, Any]]:
```

Exports skill metadata only (name, description, category). **Skill source code is not exported.**

---

## `storage/import_manager.py`

### Purpose

Imports TinyCUA data from JSON or ZIP files with validation, merge/replace modes, and rollback protection.

### `ImportMode` Enum

```python
class ImportMode(Enum):
    MERGE = "merge"
    REPLACE = "replace"
```

### `ImportValidation` Dataclass

```python
@dataclass
class ImportValidation:
    valid: bool
    version: str | None = None
    data_types: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    parsed_data: dict[str, Any] | None = None
```

### `ImportResult` Dataclass

```python
@dataclass
class ImportResult:
    success: bool
    items_imported: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
```

### `ImportManager` Class

```python
class ImportManager:
    SUPPORTED_VERSIONS = {"1.0"}
    MAX_IMPORT_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
```

### `validate()` — Import Validation

```python
def validate(self, input_path: Path) -> ImportValidation:
```

**Validation checks:**
1. File size ≤ 50 MB
2. File exists and is readable
3. Valid JSON
4. Has `version` field in supported versions
5. Has `data` section that is a dict
6. Data schema validation (types check for sessions, agents, memory, skills)

**Session count warning:** If more than 100 sessions, adds a warning about import time.

### `import_data()` — Main Import

```python
def import_data(
    self,
    input_path: Path,
    mode: ImportMode = ImportMode.MERGE,
    progress_callback: Callable[[str], None] | None = None,
) -> ImportResult:
```

**Replace mode safety:**
```python
if mode == ImportMode.REPLACE:
    _notify("Creating backup of existing data...")
    backup_path = self._backup_existing_data()
    _notify("Clearing existing data...")
    self._clear_existing_data(import_data_types)
```

**Import order:**
1. Sessions
2. Agents
3. Memory
4. Skills

**Error recovery for REPLACE mode:**
```python
except (OSError, ValueError, TypeError) as e:
    if backup_path is not None and mode == ImportMode.REPLACE:
        restore_ok = self._restore_from_backup(backup_path)
        if restore_ok:
            return ImportResult(
                success=False,
                error=f"Import failed and existing data was restored: {e}",
            )
        return ImportResult(
            success=False,
            error=f"Import failed and data restoration also failed. Data may be lost: {e}",
        )
```

**Why this matters:** Replace mode is destructive. If import fails, the manager attempts to restore from a backup. If restoration also fails, it reports potential data loss.

### `_backup_existing_data()`

Creates a temporary backup using `ExportManager`:
```python
backup_dir = Path(tempfile.gettempdir()) / "tinycua_import_backups"
backup_dir.mkdir(parents=True, exist_ok=True)
backup_dir.chmod(0o700)
backup_path = backup_dir / f"backup-{uuid.uuid4()}.json"
```

**Security:** Backup directory has `0o700` permissions (owner only).

### `_import_sessions()`

```python
def _import_sessions(self, sessions_data: list[dict[str, Any]]) -> tuple[int, list[str]]:
```

- Creates sessions with preserved IDs (if valid UUID)
- Imports all messages for each session
- Handles invalid session IDs gracefully (creates new UUID)

### `_import_agents()`

```python
def _import_agents(self, agents_data: list[dict[str, Any]]) -> tuple[int, list[str]]:
```

**Security measures:**
```python
config.pop("api_key", None)  # Strip API key
```

Imported agents never include API keys, even if present in the export file. Prevents credential leakage from tampered exports.

**Duplicate handling:** Skips agents with names that already exist.

### `_import_skills()`

```python
def _import_skills(self, skills_data: list[dict[str, Any]]) -> tuple[int, list[str]]:
```

**Important:** Skills are NOT actually imported. Only metadata is preserved, and a warning is generated:
```python
warnings.append(f"Skill '{name}' not imported; skill files must be installed manually")
```

**Why?** Skills contain executable code. Importing them automatically would be a security risk. Users must manually install skill files and then import will pick them up.

### `import_zip()` — ZIP Import

```python
def import_zip(self, input_path: Path, mode: ImportMode = ImportMode.MERGE, progress_callback: Callable[[str], None] | None = None) -> ImportResult:
```

**ZIP security checks:**
1. No nested ZIP files
2. Compression ratio ≤ 100:1 (ZIP bomb detection)
3. Each member ≤ 50 MB
4. Looks for `export.json` or `manifest.json` first

**Extraction:** Uses `tempfile.TemporaryDirectory()` for safe extraction.

---

## Storage Data Flow

### Export Flow

```
User requests export
    │
    ▼
ExportManager._collect_export_data()
    │
    ├─ _export_sessions() ──▶ LocalSessionStore
    ├─ _export_agents() ────▶ AgentManager
    ├─ _export_memory() ────▶ LocalMemoryStore
    └─ _export_skills() ────▶ SkillsManager
    │
    ▼
Serialize to JSON
    │
    ▼
Write to file (or ZIP)
```

### Import Flow

```
User selects import file
    │
    ▼
ImportManager.validate()
    │
    ├─ Check file size
    ├─ Parse JSON
    ├─ Check version
    ├─ Validate schema
    └─ Return validation result
    │
    ▼
ImportManager.import_data()
    │
    ├─ If REPLACE: backup existing data
    ├─ If REPLACE: clear existing data
    │
    ▼
Import in order:
    ├─ sessions + messages
    ├─ agents (without api_key)
    ├─ memory key-values
    └─ skills (metadata only, warn)
    │
    ▼
If failed and REPLACE: restore from backup
```

---

## Security Considerations

1. **Path validation:** `_validate_path()` in `app.py` prevents directory traversal in export/import paths.

2. **Sensitive data redaction:** Agent configs are exported with `redact_sensitive=True`.

3. **API key stripping:** Imported agent configs have `api_key` removed.

4. **Skill code not imported:** Only metadata is imported; executable code must be manually installed.

5. **ZIP bomb protection:** Compression ratio and size limits prevent malicious archives.

6. **Replace mode backup:** Automatic backup and restore protect against failed imports.

7. **File permissions:** Backup directories use `0o700`, config files use `0o600`.
