# Storage Layer Documentation

The `storage/` package provides a unified storage layer for sessions and messages, supporting both SQLite (local development) and PostgreSQL (production) via SQLAlchemy.

**Package path:** `tinycua_sdk/storage/`

---

## store.py - SessionStore

### Purpose

`SessionStore` is the primary unified storage interface. It uses SQLAlchemy ORM for database operations and supports both SQLite and PostgreSQL backends.

### Constructor

```python
class SessionStore:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.session_factory = sessionmaker(bind=self.engine)
        self._db_type = self._detect_db_type()
```

**Database detection:**
```python
def _detect_db_type(self) -> str:
    if self.database_url.startswith("postgresql"):
        return "postgresql"
    return "sqlite"
```

### PostgreSQL Features

```python
def has_pgvector(self) -> bool:
    if not self.is_postgresql:
        return False
    try:
        import pgvector.sqlalchemy
        return True
    except ImportError:
        return False
```

Checks if `pgvector` is available for vector storage. Used by `Message.embedding` column.

### Table Creation

```python
def create_tables(self) -> None:
    Base.metadata.create_all(self.engine)
```

Creates all tables defined in `models.py`. Safe to call multiple times (SQLAlchemy uses `CREATE TABLE IF NOT EXISTS`).

### Session Management

#### create_session()

```python
def create_session(
    self,
    name: str,
    user_id: str | None = None,
    tenant_id: str | None = None,
    session_id: uuid.UUID | None = None,
    parent_session_id: uuid.UUID | None = None,
) -> Session
```

**Features:**
- Optional explicit `session_id` for external session management
- **Session lineage**: Tracks parent-child relationships via `parent_session_id`
- **Lineage depth**: Automatically calculated from parent's depth + 1

```python
lineage_depth = 0
if parent_session_id:
    parent = db.get(Session, parent_session_id)
    if parent:
        lineage_depth = getattr(parent, "lineage_depth", 0) + 1
```

**Why lineage?** Enables conversation branching (e.g., "fork this conversation" feature).

#### get_lineage()

```python
def get_lineage(self, session_id: uuid.UUID) -> list[Session]:
    lineage = []
    current = db.get(Session, session_id)
    while current:
        lineage.insert(0, current)  # Prepend to maintain root→current order
        if current.parent_session_id:
            current = db.get(Session, current.parent_session_id)
        else:
            break
    return lineage
```

Traverses parent chain from current session to root. Returns sessions in order from oldest ancestor to current.

### Message Operations

#### add_message()

```python
def add_message(
    self,
    session_id: uuid.UUID,
    role: str,
    content: str,
    reasoning: str | None = None,
) -> Message | None
```

**Turn indexing:**
```python
stmt = select(Message).where(Message.session_id == session_id)
existing_messages = db.execute(stmt).scalars().all()
turn_index = len(existing_messages)
```

Automatically assigns turn index based on existing message count. This maintains conversation order.

**Returns None if session doesn't exist:**
```python
session = db.get(Session, session_id)
if not session:
    return None
```

#### get_recent_turns()

```python
def get_recent_turns(self, session_id: uuid.UUID, count: int = 3) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.session_id == session_id)
        .where(Message.is_archived == False)
        .order_by(Message.turn_index.desc())
        .limit(count)
    )
    results = db.execute(stmt).scalars().all()
    return list(reversed(results))
```

Returns recent non-archived messages in ascending order. Uses `reversed()` because the query orders by `desc()`.

**Why archived filter?** Archived messages are excluded from active context but preserved for history.

### Context Retrieval

#### update_full_context()

```python
def update_full_context(self, session_id: uuid.UUID) -> str:
    session = db.get(Session, session_id)
    messages = db.execute(
        select(Message).where(Message.session_id == session_id)
        .order_by(Message.turn_index.asc())
    ).scalars().all()
    
    md_lines = [
        f"# Session: {session.name}",
        f"Created: {session.created_at.isoformat()}",
        "",
        "---",
        "",
    ]
    
    for msg in messages:
        md_lines.append(f"## Turn {msg.turn_index}")
        md_lines.append(f"**{msg.role.capitalize()}**: {msg.content}")
        md_lines.append("")
    
    full_context = "\n".join(md_lines)
    session.full_context_md = full_context
    db.commit()
    return full_context
```

Generates a Markdown representation of the entire conversation and stores it in `session.full_context_md`. This is used for:
- Full-text search (`search_grep`)
- Export functionality
- Human-readable conversation dumps

#### search_grep()

```python
def search_grep(self, session_id: uuid.UUID, query: str, limit: int = 5) -> list[dict[str, Any]]:
    session = db.get(Session, session_id)
    if not session or not session.full_context_md:
        return []
    
    full_context = session.full_context_md
    lines = full_context.split("\n")
    matching_lines = []
    current_turn = []
    
    for line in lines:
        if query.lower() in line.lower():
            current_turn.append(line)
        elif line.startswith("## Turn "):
            if current_turn:
                matching_lines.extend(current_turn)
                matching_lines.append("")
            current_turn = [line]
        elif line.strip():
            current_turn.append(line)
    
    result_text = "\n".join(matching_lines[: limit * 50])
    return [{"content": result_text, "matches": len(matching_lines)}]
```

Simple text search on `full_context_md`. Groups results by turn for context preservation.

**Why `limit * 50`?** Limits result length while preserving full turns. Each "result" can contain up to 50 lines.

### Summary Management

```python
def update_summary(self, session_id: uuid.UUID, summary_md: str) -> Session | None:
    session = db.get(Session, session_id)
    if not session:
        return None
    session.summary_md = summary_md
    session.has_summary = True
    session.summary_updated_at = datetime.utcnow()
    db.commit()
    return session

def get_summary(self, session_id: uuid.UUID) -> str | None:
    session = db.get(Session, session_id)
    if not session:
        return None
    return session.summary_md
```

Stores conversation summaries for quick context retrieval without loading all messages.

### Factory Function

```python
_default_store: SessionStore | None = None

def get_session_store(database_url: str | None = None) -> SessionStore:
    global _default_store
    
    if database_url is not None:
        store = SessionStore(database_url)
        store.create_tables()
        return store
    
    if _default_store is not None:
        return _default_store
    
    resolved_url = "sqlite:///./tinycua.db"
    try:
        from tinycua_sdk.core.config import SDKConfig
        resolved_url = SDKConfig().memory.database_url
    except (OSError, ValueError, ImportError, TypeError):
        pass
    
    _default_store = SessionStore(resolved_url)
    _default_store.create_tables()
    return _default_store
```

**Config resolution chain:**
1. If `database_url` parameter provided → use it (new instance, not cached)
2. If default store already exists → return it
3. Try `SDKConfig().memory.database_url`
4. Fallback to `"sqlite:///./tinycua.db"`

**Why lazy import of SDKConfig?** Avoids circular imports and keeps startup fast.

---

## models.py - Database Models

### Purpose

Defines SQLAlchemy ORM models for sessions and messages with SQLite/PostgreSQL compatibility.

### Base

```python
class Base(DeclarativeBase):
    pass
```

Uses SQLAlchemy 2.0 declarative base.

### get_embedding_column()

```python
def get_embedding_column():
    try:
        from pgvector.sqlalchemy import Vector
        return mapped_column(Vector(1536), nullable=True)
    except ImportError:
        return mapped_column(JSON, nullable=True)
```

**Dynamic column type:**
- If `pgvector` available → `Vector(1536)` (OpenAI ada-002 dimension)
- Otherwise → `JSON` column storing list of floats

**Why 1536 dimensions?** Matches OpenAI's text-embedding-ada-002 model. Can be adjusted for other embedding models.

### Session Model

```python
class Session(Base):
    __tablename__ = "sdk_sessions"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    has_summary: Mapped[bool] = mapped_column(Boolean, default=False)
    summary_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    summary_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_context_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("sdk_sessions.id"), nullable=True)
    lineage_depth: Mapped[int] = mapped_column(Integer, default=0)
    
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    parent_session: Mapped[Optional["Session"]] = relationship("Session", remote_side="Session.id", back_populates="child_sessions", foreign_keys=[parent_session_id])
    child_sessions: Mapped[list["Session"]] = relationship("Session", back_populates="parent_session", foreign_keys=[parent_session_id])
```

**Table name:** `sdk_sessions` (not `sessions`) to avoid conflicts with backend's sessions table.

**Self-referential relationship:** Session can have a parent session, enabling conversation trees:
```
Session A (root)
└── Session B (child of A)
    └── Session C (child of B)
```

**Cascade delete:** `cascade="all, delete-orphan"` on `messages` relationship ensures deleting a session also deletes all its messages.

### Message Model

```python
class Message(Base):
    __tablename__ = "messages"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sdk_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding: Mapped[Optional[list[float]]] = get_embedding_column()
    importance: Mapped[int] = mapped_column(Integer, default=5)
    memory_type: Mapped[str] = mapped_column(String(50), default="working")
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    session: Mapped["Session"] = relationship("Session", back_populates="messages")
```

**Fields explained:**
- `reasoning`: Agent's chain-of-thought or reasoning text
- `turn_index`: Position in the conversation turn sequence
- `is_archived`: Whether message is excluded from active context
- `embedding`: Vector embedding for semantic search
- `importance`: Priority score (1-10) for retention decisions
- `memory_type`: Category ("working", "long_term", "ephemeral")
- `is_pinned`: Whether message should always be retained

---

## sqlite.py - LocalStorage

### Purpose

`LocalStorage` provides a SQLite-based storage alternative using raw SQL (not SQLAlchemy). Suitable for lightweight local usage without SQLAlchemy overhead.

### Schema

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    user_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    summary_md TEXT,
    has_summary INTEGER DEFAULT 0,
    full_context_md TEXT
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    config_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    agent_id TEXT,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_session_id ON memory(session_id);
CREATE INDEX IF NOT EXISTS idx_memory_agent_id ON memory(agent_id);
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory(memory_type);
```

**Why TEXT for dates?** SQLite has limited datetime support. ISO format strings are portable and sort correctly.

**Indexes:** Added on frequently queried columns for performance.

### Schema Versioning

```python
CURRENT_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

class LocalStorage:
    def _set_schema_version(self, version: str) -> None:
        with self._connect() as conn:
            now = datetime.utcnow().isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, now),
            )
```

Tracks schema version for future migrations.

### CRUD Operations

**Sessions:**
```python
def save_session(self, session_id, name, user_id=None, summary_md=None, has_summary=False, full_context_md=None)
def load_session(self, session_id)
def list_sessions(self, user_id=None)
def delete_session(self, session_id)
```

**Agents:**
```python
def save_agent(self, agent_id, name, config)
def load_agent(self, agent_id)
def list_agents(self)
def delete_agent(self, agent_id)
```

**Memory:**
```python
def save_memory(self, memory_id, memory_type, content, session_id=None, agent_id=None, metadata=None)
def load_memory(self, memory_id)
def list_memory(self, session_id=None, agent_id=None, memory_type=None)
def delete_memory(self, memory_id)
```

### Data Conversion

```python
def _row_to_dict(self, row: sqlite3.Row, columns: list[str]) -> dict[str, Any]:
    result = {k: v for k, v in zip(columns, row)}
    for key, value in result.items():
        if key.endswith("_json") and value:
            try:
                result[key] = json.loads(value)
            except json.JSONDecodeError:
                pass
        elif key.endswith("_at") and value:
            try:
                result[key] = datetime.fromisoformat(value)
            except ValueError:
                pass
        elif key in ("has_summary",) and value is not None:
            result[key] = bool(value)
    return result
```

Smart deserialization:
- `*_json` fields → parsed as JSON
- `*_at` fields → parsed as ISO datetime
- `has_summary` → converted from SQLite INTEGER (0/1) to Python bool

### Import/Export

```python
def export_all(self) -> dict[str, Any]:
    return {
        "sessions": self.list_sessions(),
        "agents": self.list_agents(),
        "memory": self.list_memory(),
    }

def import_data(self, data: dict[str, Any], mode: str = "merge") -> dict[str, Any]:
    if mode == "replace":
        # Clear existing data
    # Import sessions, agents, memory
```

Supports merge and replace modes for data migration.

---

## export.py - Exporter

### Purpose

Exports TINYCUA data to JSON or ZIP format for backup and migration.

### Export Formats

#### JSON Export

```python
def export_json(self) -> dict[str, Any]:
    data = self.storage.export_all()
    return {
        "version": CURRENT_VERSION,
        "exported_at": datetime.utcnow().isoformat(),
        "sessions": self._sanitize_datetime(data["sessions"]),
        "agents": self._sanitize_datetime(data["agents"]),
        "memory": self._sanitize_datetime(data["memory"]),
    }
```

Converts datetime objects to ISO strings for JSON serialization.

#### ZIP Export

```python
def export_zip(self) -> dict[str, Any]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data.json", json.dumps(data_copy, indent=2))
        zf.writestr("MEMORY.md", self._generate_memory_md(data["memory"]))
        zf.writestr("USER.md", self._generate_user_md(data["agents"]))
    
    return {
        "version": CURRENT_VERSION,
        "exported_at": datetime.utcnow().isoformat(),
        "zip_data": buffer.getvalue(),
        "size": len(buffer.getvalue()),
    }
```

Creates a ZIP containing:
- `data.json`: Full structured data
- `MEMORY.md`: Human-readable memory entries
- `USER.md`: Agent/user info

**Why include Markdown files?** Provides human-readable exports alongside machine-readable JSON.

---

## importer.py - Importer

### Purpose

Imports TINYCUA data from JSON or ZIP format with validation.

### Validation

```python
def validate_import(self, data: dict[str, Any]) -> dict[str, Any]:
    errors = []
    warnings = []
    
    if "version" not in data:
        errors.append("Missing 'version' field")
    else:
        version = data.get("version", "")
        if version < MIN_VERSION:
            errors.append(f"Version {version} is below minimum {MIN_VERSION}")
        elif version != CURRENT_VERSION:
            warnings.append(f"Version {version} differs from current {CURRENT_VERSION}")
    
    if "sessions" in data and not isinstance(data["sessions"], list):
        errors.append("'sessions' must be a list")
    # ... similar for agents and memory
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
```

**Version comparison:** Uses string comparison (`version < MIN_VERSION`). This works for simple `x.y.z` versions but may not handle all semver cases correctly.

### Import Methods

```python
def import_json(self, data: dict[str, Any], mode: str = "merge") -> dict[str, Any]
def import_zip(self, zip_data: bytes, mode: str = "merge") -> dict[str, Any]
def import_from_file(self, filepath: str, mode: str = "merge") -> dict[str, Any]
```

Auto-detects format from file extension (`.zip` vs. `.json`).

---

## snapshot.py - Memory Snapshots

### Purpose

Provides immutable point-in-time snapshots of session memory with integrity verification.

### MemorySnapshot Dataclass

```python
@dataclass
class MemorySnapshot:
    id: str
    created_at: datetime
    data: dict[str, Any]
    checksum: str
```

**Immutable design:** The dataclass itself doesn't enforce immutability, but the API treats snapshots as read-only after creation.

### Checksum Computation

```python
@staticmethod
def compute_checksum(data: dict[str, Any]) -> str:
    json_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()

def verify_integrity(self) -> bool:
    expected = self.compute_checksum(self.data)
    return self.checksum == expected
```

Uses SHA256 of sorted JSON for deterministic checksums. `sort_keys=True` ensures consistent ordering regardless of dict insertion order.

### SnapshotManager

```python
class SnapshotManager:
    def __init__(self, store: SessionStore)
```

#### create_snapshot()

```python
def create_snapshot(self, session_id: uuid.UUID, metadata: dict | None = None) -> MemorySnapshot:
    session = self.store.get_session(session_id)
    messages = self.store.list_messages(session_id)  # Note: uses get_messages in actual code
    
    snapshot_data = {
        "session_id": str(session_id),
        "session_name": session.name,
        "messages": [...],
        "metadata": metadata or {},
    }
    
    checksum = MemorySnapshot.compute_checksum(snapshot_data)
    snapshot = MemorySnapshot(id=str(uuid.uuid4()), created_at=datetime.now(), data=snapshot_data, checksum=checksum)
    self._save_snapshot(snapshot)
    return snapshot
```

**Why include full message list?** Snapshots capture the complete state at a point in time, not just metadata.

#### load_snapshot()

```python
def load_snapshot(self, snapshot_id: str) -> MemorySnapshot | None:
    # Load from database
    snapshot = MemorySnapshot(id=row.id, created_at=row.created_at, data=data, checksum=row.checksum)
    
    if not snapshot.verify_integrity():
        raise SnapshotError(f"Snapshot {snapshot_id} integrity check failed")
    
    return snapshot
```

Verifies checksum on load. Raises `SnapshotError` if corrupted.

**Why raise on corruption rather than return None?** Data corruption is an exceptional condition that should not be silently ignored.

---

## Inter-Module Data Flow

### Session Store Flow
```
Agent execution
  → SessionStore.create_session(name)
    → SQL INSERT INTO sdk_sessions
    → Return Session ORM object
  → SessionStore.add_message(session_id, role, content)
    → SQL INSERT INTO messages
    → Auto-assign turn_index
    → Return Message ORM object
  → SessionStore.get_recent_turns(session_id, count=3)
    → SQL SELECT ... ORDER BY turn_index DESC LIMIT 3
    → Return list[Message]
```

### Export Flow
```
User requests export
  → Exporter.export_json()
    → LocalStorage.export_all()
      → SELECT * FROM sessions/agents/memory
    → _sanitize_datetime()
    → Return dict
  → Exporter.export_zip()
    → Same data gathering
    → _generate_memory_md()
    → _generate_user_md()
    → zipfile.ZipFile.write()
    → Return zip bytes
```

### Snapshot Flow
```
User requests snapshot
  → SnapshotManager.create_snapshot(session_id)
    → Get session + messages
    → Build snapshot_data dict
    → compute_checksum()
    → INSERT INTO snapshots
    → Return MemorySnapshot
```
