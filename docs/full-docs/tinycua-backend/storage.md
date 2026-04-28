# Storage Layer

**Files**:
- `tinycua_backend/storage/database.py`
- `tinycua_backend/storage/models.py`
- `tinycua_backend/storage/base.py`
- `tinycua_backend/storage/search_sqlite.py`
- `tinycua_backend/storage/search_postgres.py`
- `tinycua_backend/storage/search_backend.py`

---

## storage/base.py — Base Model and Mixins

**Purpose**: Defines the SQLAlchemy declarative base and reusable mixins used by all backend models.

### `Base(DeclarativeBase)`

```python
class Base(DeclarativeBase):
    pass
```

All backend SQLAlchemy models inherit from this `Base`. It provides the metadata registry for `Base.metadata.create_all()`.

### `TimestampMixin`

```python
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=partial(datetime.now, timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=partial(datetime.now, timezone.utc),
        onupdate=partial(datetime.now, timezone.utc),
    )
```

**Why `partial(datetime.now, timezone.utc)` instead of `datetime.now(timezone.utc)`?**

`mapped_column(default=...)` expects a callable (a function with no arguments). `datetime.now(timezone.utc)` would be called once at class definition time, producing a frozen timestamp. `partial(datetime.now, timezone.utc)` creates a callable that invokes `datetime.now(timezone.utc)` each time a new record is created.

- `created_at`: Set once at insertion
- `updated_at`: Set at insertion and updated on every `UPDATE` via `onupdate`

### `UUIDMixin`

```python
class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
```

Provides a UUID primary key for all models. `uuid.uuid4` generates random UUIDs (version 4).

---

## storage/database.py — Database Engine and Sessions

**Purpose**: Manages the SQLAlchemy engine, session factory, table creation, and caching of the SDK's `SessionStore`.

### Model Imports for Side Effects

```python
from tinycua_backend.tenant.models import Tenant
from tinycua_backend.auth.models import User, APIKey
from tinycua_backend.storage.models import Agent, Tool

del Tenant, User, APIKey, Agent, Tool
```

These imports are **only for side effects**. SQLAlchemy's declarative system registers models with `Base.metadata` when the class is defined. Without importing these modules, `Base.metadata` would be empty and `create_tables()` would create nothing.

```python
configure_mappers()
```

Forces SQLAlchemy to resolve all relationships immediately. This prevents lazy mapping issues in multi-threaded contexts.

### `is_postgresql(url: str) -> bool`

```python
def is_postgresql(url: str) -> bool:
    return url.startswith("postgresql") or url.startswith("postgres")
```

Simple URL-based detection. Used to conditionally apply PostgreSQL-specific engine options.

### `get_engine() -> Engine`

**Lazy initialization with double-checked locking**:

```python
def get_engine() -> Engine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                config = get_config()
                url = config.database.url
                engine_kwargs = {
                    "echo": False,
                    "pool_size": config.database.pool_size,
                    "max_overflow": config.database.max_overflow,
                    "pool_recycle": config.database.pool_recycle,
                    "pool_pre_ping": config.database.pool_pre_ping,
                }
                if is_postgresql(url):
                    engine_kwargs["poolclass"] = QueuePool
                _engine = create_engine(url, **engine_kwargs)
    return _engine
```

**Why double-checked locking?** Multiple workers might try to create the engine simultaneously. The outer `if` avoids the lock in the hot path; the inner `if` ensures only one thread creates the engine.

**Engine kwargs**:
- `echo=False`: Disable SQL logging (set to `True` for debugging)
- `pool_size=10`: Maintain 10 persistent connections
- `max_overflow=20`: Allow 20 additional temporary connections under load
- `pool_recycle=3600`: Recycle connections after 1 hour (prevents stale connections from database-side timeouts)
- `pool_pre_ping=True`: Verify connection health before use (avoids errors from stale pooled connections)
- `poolclass=QueuePool`: Explicitly use queue-based pooling for PostgreSQL

### `get_session_local() -> sessionmaker[Session]`

```python
def get_session_local() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        with _session_local_lock:
            if _SessionLocal is None:
                engine = get_engine()
                _SessionLocal = sessionmaker(
                    bind=engine, autocommit=False, expire_on_commit=False
                )
    return _SessionLocal
```

- `autocommit=False`: Transactions must be explicitly committed
- `expire_on_commit=False`: Keeps object attributes accessible after commit (useful for returning objects from service methods)

### `get_db() -> Generator[Session, None, None]`

```python
def get_db() -> Generator[Session, None, None]:
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

FastAPI dependency that yields a database session per request. The `finally` ensures the session is closed even if an exception occurs.

### `create_tables() -> None`

```python
def create_tables() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
```

Creates all backend tables (tenants, users, api_keys, agents, tools) if they don't exist. Called during app lifespan.

### `get_session_store() -> SessionStore`

```python
_session_store: SessionStore | None = None
_session_store_lock = threading.Lock()

def get_session_store() -> SessionStore:
    global _session_store
    config = get_config()
    if _session_store is None or _session_store.database_url != config.database.url:
        with _session_store_lock:
            if _session_store is None or _session_store.database_url != config.database.url:
                _session_store = SessionStore(config.database.url)
    return _session_store
```

**Caches the SDK's SessionStore** globally. Key behaviors:
- Lazy initialization on first call
- **URL change detection**: If the config's database URL changes (e.g., hot-reload), the store is recreated
- Thread-safe via `_session_store_lock`

**Why cache?** `SessionStore` creates an engine internally. Creating one per request would be expensive.

---

## storage/models.py — Agent and Tool Models

### `Agent(Base, UUIDMixin, TimestampMixin)`

**Table**: `agents`

```python
class Agent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agents"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
```

**Fields**:
- `tenant_id`: Owner tenant
- `name`: Human-readable agent name
- `config`: Arbitrary JSON configuration (model name, tools, prompts, etc.)
- `is_active`: Soft-delete / enable flag

**Design note**: The backend stores agent configurations but does not execute them. The runner service reads these configurations and executes the agent logic.

### `Tool(Base, UUIDMixin, TimestampMixin)`

**Table**: `tools`

```python
class Tool(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tools"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=True)
    source: Mapped[str] = mapped_column(String(50000), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    external_dependencies: Mapped[list[str]] = mapped_column(JSON, default=list)
    tool_dependencies: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
```

**Fields**:
- `source`: Source code or definition of the tool (up to 50KB)
- `parameters`: JSON schema for tool parameters
- `external_dependencies`: List of pip packages required
- `tool_dependencies`: List of other tools this tool depends on
- `version`: Semantic version string

**Why `String(50000)` for source?** VARCHAR limits vary by database. 50KB is large enough for most Python function definitions while still being indexable as a string (though not actually indexed).

---

## storage/search_backend.py — Search Protocol

**Purpose**: Defines the interface contract for full-text search implementations.

```python
class SearchBackend(Protocol):
    def initialize(self, engine: Engine) -> None: ...
    def index_message(self, engine: Engine, message_id: uuid.UUID, content: str) -> None: ...
    def search(self, engine: Engine, query: str, limit: int = 10) -> list[uuid.UUID]: ...
    def remove_message(self, engine: Engine, message_id: uuid.UUID) -> None: ...
    def reindex(self, engine: Engine) -> None: ...
```

**Protocol vs ABC**: Using `typing.Protocol` allows duck typing. Any class with these methods is a valid search backend, even if it doesn't inherit from a base class.

---

## storage/search_sqlite.py — SQLite FTS5 Search

**Purpose**: Full-text search using SQLite's built-in FTS5 extension.

### `SQLiteSearch(SearchBackend)`

#### `initialize(engine)`

```python
def initialize(self, engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {self.FTS_TABLE} USING fts5(
                message_id UNINDEXED,
                content,
                tokenize='porter'
            )
        """))
        conn.commit()
```

- `VIRTUAL TABLE`: FTS5 tables are virtual — they don't store rows in the same way as regular tables
- `message_id UNINDEXED`: Stores the UUID but does not tokenize/index it (used for lookups, not searching)
- `tokenize='porter'`: Uses Porter stemming (e.g., "running" matches "run")

#### `index_message(engine, message_id, content)`

Inserts a row into the FTS table. Must be called whenever a message is created.

**Note**: Currently, `index_message` and `remove_message` are not automatically called by the message creation endpoint. The search endpoint in `sessions.py` only searches existing indexed messages.

#### `search(engine, query, limit)`

```python
def search(self, engine: Engine, query: str, limit: int = 10) -> list[uuid.UUID]:
    with engine.connect() as conn:
        result = conn.execute(text(f"""
            SELECT message_id FROM {self.FTS_TABLE}
            WHERE {self.FTS_TABLE} MATCH :query
            ORDER BY rank
            LIMIT :limit
        """), {"query": query, "limit": limit})
        return [uuid.UUID(row[0]) for row in result.fetchall()]
```

- `MATCH :query`: FTS5 query syntax supports boolean operators, phrases, prefixes
- `ORDER BY rank`: FTS5's built-in ranking (BM25-like)

#### `remove_message(engine, message_id)`

Deletes the FTS row for a given message ID.

#### `reindex(engine)`

```python
def reindex(self, engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text(f"""
            INSERT INTO {self.FTS_TABLE}({self.FTS_TABLE})
            VALUES('rebuild')
        """))
        conn.commit()
```

FTS5 special syntax: inserting `'rebuild'` into the table itself triggers a full index rebuild.

---

## storage/search_postgres.py — PostgreSQL tsvector Search

**Purpose**: Full-text search using PostgreSQL's native `tsvector` and `GIN` index.

### `PostgreSQLSearch(SearchBackend)`

#### `initialize(engine)`

```python
def initialize(self, engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_messages_content_fts
            ON messages USING GIN(content_vector)
        """))
        conn.execute(text("""
            CREATE OR REPLACE FUNCTION messages_content_vector_trigger()
            RETURNS trigger AS $$
            BEGIN
                NEW.content_vector := to_tsvector('english', NEW.content);
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """))
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS messages_content_vector_update
            BEFORE INSERT OR UPDATE ON messages
            FOR EACH ROW EXECUTE FUNCTION messages_content_vector_trigger()
        """))
        conn.commit()
```

**Components created**:
1. **`unaccent` extension**: Removes accents for better matching (e.g., "café" matches "cafe")
2. **`GIN` index on `content_vector`**: Generalized Inverted Index, optimized for full-text search
3. **`messages_content_vector_trigger()`**: PL/pgSQL function that auto-generates `tsvector` from `content`
4. **`messages_content_vector_update` trigger**: Runs the function before every INSERT/UPDATE

**Note**: The `messages` table must have a `content_vector tsvector` column (defined by the SDK's schema, not the backend).

#### `index_message(engine, message_id, content)`

Manually updates `content_vector` for a specific message. Usually redundant because the trigger handles it automatically, but provided for explicit control.

#### `search(engine, query, limit)`

```python
def search(self, engine: Engine, query: str, limit: int = 10) -> list[uuid.UUID]:
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id FROM messages
            WHERE content_vector @@ plainto_tsquery('english', :query)
            ORDER BY ts_rank(content_vector, plainto_tsquery('english', :query)) DESC
            LIMIT :limit
        """), {"query": query, "limit": limit})
        return [uuid.UUID(row[0]) for row in result.fetchall()]
```

- `plainto_tsquery('english', :query)`: Converts plain text to a tsquery, handling AND/OR implicitly
- `@@`: tsvector matches tsquery operator
- `ts_rank(...)`: Ranking function (normalized 0-1 score)

#### `search_with_content(engine, query, limit)`

Same as `search` but also returns the message content. Not currently used by the API but available for future features.

#### `remove_message(engine, message_id)`

No-op. PostgreSQL handles removal automatically via cascading deletes or the trigger.

#### `reindex(engine)`

```python
def reindex(self, engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE messages SET content_vector = to_tsvector('english', content)
        """))
        conn.commit()
        conn.execute(text("REINDEX INDEX idx_messages_content_fts"))
        conn.commit()
```

Updates all rows and rebuilds the GIN index.

#### `get_stats(engine)`

Returns statistics about indexing coverage:
```python
{
    "total_messages": 1000,
    "indexed_messages": 998,
    "pending_index": 2,
}
```

---

## Storage Layer Data Flow

```
Request arrives
    │
    ▼
get_db() dependency
    │
    ├──▶ get_session_local()
    │         └──▶ get_engine()
    │               └──▶ create_engine() with pooling (first call only)
    │
    └──▶ sessionmaker() creates Session
          └──▶ yield db to endpoint
                │
                ├──▶ db.query(Model)...  (backend tables)
                │
                └──▶ get_store()
                      └──▶ get_session_store()
                            └──▶ SessionStore(config.database.url) (cached)
                                  └──▶ store.create_session() / get_messages() / etc.
                                        (SDK tables: sessions, messages)
```

---

## Multi-Database Support

| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| Connection pooling | Limited (file locks) | QueuePool with configurable size |
| Full-text search | FTS5 virtual table | tsvector + GIN index |
| Concurrency | WAL mode recommended | Excellent |
| Migrations | Schema auto-created | Schema auto-created |

**Switching databases**: Change `database.url` in `config.yaml` or set `DATABASE_URL`. All code is database-agnostic except:
- `search_sqlite.py` / `search_postgres.py` (chosen by `main.py` based on URL prefix)
- `main.py` only initializes `SQLiteSearch` for SQLite URLs
