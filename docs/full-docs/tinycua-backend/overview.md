# tinycua-backend Overview

## Project Purpose

**tinycua-backend** is the FastAPI-based backend server for the TINYCUA ecosystem. It provides a RESTful API for session storage and management, multi-tenant authentication, and multi-device synchronization. The backend follows a **pure storage architecture** — it stores agent and tool configurations, sessions, and messages, but it does **not** execute agent logic (execution is delegated to the runner service).

## Role in the TINYCUA Ecosystem

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend/CLI  │────▶│  tinycua-backend │────▶│  tinycua-runner │
│   (Client)      │◄────│  (This Service)  │◄────│  (Execution)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  tinycua-sdk     │
                        │  (Storage layer) │
                        └──────────────────┘
```

- **Frontend/CLI**: Communicates with the backend via REST API
- **tinycua-backend**: Stores sessions, messages, users, tenants, agents, tools; handles auth
- **tinycua-runner**: Executes agents (separate service)
- **tinycua-sdk**: Shared storage layer (SessionStore) used by both backend and runner

## Architecture Overview

The backend is organized into layered modules:

```
tinycua_backend/
├── main.py              # FastAPI app initialization, lifespan, router mounting
├── config.py            # Configuration management with YAML + env override
├── exceptions.py        # Custom exception hierarchy
├── api/                 # HTTP API endpoints (FastAPI routers)
│   ├── auth.py          # Registration, login, current user
│   ├── sessions.py      # CRUD for sessions + search
│   ├── messages.py      # CRUD for messages within sessions
│   ├── tenant.py        # Tenant management (admin)
│   └── dependencies.py  # Shared API dependencies (get_store, get_session_or_404)
├── auth/                # Authentication system
│   ├── core.py          # Backward-compatible re-export shim
│   ├── jwt.py           # JWT token creation and validation
│   ├── passwords.py     # Bcrypt password hashing
│   ├── api_keys.py      # API key generation and verification
│   ├── service.py       # AuthService (register/login business logic)
│   ├── models.py        # User and APIKey SQLAlchemy models
│   ├── schemas.py       # Pydantic request/response schemas
│   └── dependencies.py  # get_current_tenant dependency (Bearer, API key, global key)
├── storage/             # Database and search layer
│   ├── base.py          # DeclarativeBase + mixins (UUIDMixin, TimestampMixin)
│   ├── database.py      # Engine, session factory, get_db, get_session_store
│   ├── models.py        # Agent and Tool SQLAlchemy models
│   ├── search_backend.py# Protocol for search backends
│   ├── search_sqlite.py # SQLite FTS5 implementation
│   └── search_postgres.py# PostgreSQL tsvector implementation
├── sync/                # Multi-device synchronization
│   ├── endpoints.py     # Sync REST endpoints
│   ├── service.py       # SyncService (business logic)
│   └── resolver.py      # Conflict detection and last-write-wins resolution
├── tenant/              # Tenant management
│   ├── models.py        # Tenant SQLAlchemy model
│   └── manager.py       # TenantManager CRUD operations
└── migrations/          # Database migrations
    └── migrate_sqlite_to_postgres.py  # One-way migration script
```

## Database Setup

The backend supports both **SQLite** and **PostgreSQL** through SQLAlchemy.

### Database URL Resolution

1. `config.yaml` → `database.url`
2. Environment variable `DATABASE_URL` overrides the config file

### Dual Table System

The backend manages **two sets of tables**:

1. **Backend-owned tables** (defined in `tinycua_backend/storage/models.py`, `auth/models.py`, `tenant/models.py`):
   - `tenants` — multi-tenancy
   - `users` — authentication
   - `api_keys` — programmatic access
   - `agents` — agent configurations
   - `tools` — custom tool definitions

2. **SDK-owned tables** (managed by `tinycua_sdk.storage.store.SessionStore`):
   - `sessions` — conversation sessions
   - `messages` — messages within sessions

Both table sets are created at startup in `main.py` lifespan:

```python
create_tables()                                    # Backend tables
SessionStore(config.database.url).create_tables()  # SDK tables
```

### Connection Pooling

For PostgreSQL, `database.py` configures:
- `pool_size` (default 10)
- `max_overflow` (default 20)
- `pool_recycle` (default 3600 seconds)
- `pool_pre_ping=True` — verifies connection health before use
- `poolclass=QueuePool` — SQLAlchemy's standard queue-based pool

For SQLite, these pooling options are passed but SQLite's file-based nature means concurrent write behavior depends on WAL mode (set by the SDK).

### Thread Safety

Both the engine (`_engine_lock`) and session factory (`_session_local_lock`) are protected by locks for lazy initialization. The `SessionStore` is also cached with a lock (`_session_store_lock`) and recreated if the database URL changes.

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Web Framework | FastAPI |
| ASGI Server | Uvicorn |
| ORM | SQLAlchemy 2.0 (DeclarativeBase, Mapped, mapped_column) |
| Validation | Pydantic v2 |
| Auth | python-jose (JWT), passlib+bcrypt (passwords/API keys) |
| Config | PyYAML + environment variable override |
| Search | SQLite FTS5 / PostgreSQL tsvector |
| Python | >= 3.12 |

## Key Design Decisions

1. **Pure Storage Backend**: The backend intentionally avoids importing execution logic from the SDK. It only uses `SessionStore` for CRUD operations on sessions and messages.

2. **Multi-tenancy**: Every resource belongs to a tenant. Users and API keys are scoped to tenants. The system tenant (`tenant_type='system'`) bypasses restrictions for global administration.

3. **Triple Authentication**: The `get_current_tenant` dependency supports three methods in priority order:
   - Global API key (config-based, grants system access)
   - JWT Bearer token (user-level, tenant-scoped)
   - Tenant API key (programmatic, tenant-scoped)

4. **SessionStore as Source of Truth**: Sessions and messages are stored through the SDK's `SessionStore`, not through backend SQLAlchemy models. This ensures compatibility with the runner and other SDK consumers.

5. **Pluggable Search**: A `SearchBackend` Protocol allows switching between SQLite FTS5 and PostgreSQL tsvector without changing endpoint code.

6. **Config Hot-Reload**: `ConfigWatcher` can monitor the config file and invoke a callback when changes are detected (optional, used via `init_config`).
