# main.py — FastAPI Application Entry Point

**File**: `tinycua_backend/main.py`

**Purpose**: Initializes and configures the FastAPI application, defines the application lifespan (startup/shutdown), configures CORS, mounts all API routers, and provides a health check endpoint.

---

## Module-Level Setup

### Logging

```python
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

Standard Python logging is configured at module load time with `INFO` level. All startup/shutdown events are logged through this logger.

### CORS Origins Parsing

```python
_cors_origins_env = os.environ.get("TINYCUA_CORS_ORIGINS", "")
_cors_origins: list[str] = (
    [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    if _cors_origins_env
    else []
)
if "*" in _cors_origins:
    raise ValueError(
        "Cannot use origins='*' with allow_credentials=True. "
        "Specify explicit origins or disable credentials."
    )
```

**What it does**:
1. Reads `TINYCUA_CORS_ORIGINS` from the environment at import time
2. Splits by comma and strips whitespace to produce a list of allowed origins
3. **Explicitly rejects wildcard `*`** when credentials are enabled (`allow_credentials=True`). This is a security measure because browsers reject `Access-Control-Allow-Origin: *` when credentials are sent.

**Why at module level?** CORS configuration is baked into the middleware at app creation time, so it must be resolved before `FastAPI()` is instantiated.

---

## Lifespan Handler

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
```

FastAPI's modern lifespan API replaces the older `startup`/`shutdown` event handlers. The lifespan runs once when the ASGI server starts and cleans up when it shuts down.

### Startup Sequence

1. **Log startup**
   ```python
   logger.info("Starting tinycua-backend...")
   ```

2. **Initialize configuration**
   ```python
   config_dir = Path(__file__).parent.parent
   config_path = config_dir / "config.yaml"
   init_config(str(config_path))
   config = get_config()
   ```
   Looks for `config.yaml` in the parent directory of `main.py` (i.e., the project root). Calls `init_config()` to load YAML and overlay environment variables.

3. **Create backend tables**
   ```python
   create_tables()
   ```
   Calls `tinycua_backend.storage.database.create_tables()`, which runs `Base.metadata.create_all(bind=engine)` for all backend SQLAlchemy models (tenants, users, api_keys, agents, tools).

4. **Create SDK tables**
   ```python
   SessionStore(config.database.url).create_tables()
   ```
   Creates `sessions` and `messages` tables via the SDK's storage layer. A new `SessionStore` is instantiated here with the configured database URL.

5. **Initialize FTS search (SQLite only)**
   ```python
   if config.database.url.startswith("sqlite"):
       search = SQLiteSearch()
       search.initialize(SessionStore(config.database.url).engine)
   ```
   If using SQLite, creates the `messages_fts` virtual table for full-text search using FTS5.

### Shutdown

```python
yield
logger.info("Shutting down tinycua-backend...")
```

The `yield` separates startup from shutdown. After `yield`, the application begins shutting down. Currently, no explicit cleanup is performed beyond logging.

---

## FastAPI App Instance

```python
app = FastAPI(
    title="tinycua-backend",
    description="Backend API for session storage and management",
    version="0.1.0",
    lifespan=lifespan,
)
```

- `title` / `description` / `version`: Metadata exposed in OpenAPI docs (`/docs`)
- `lifespan`: Binds the async context manager defined above

---

## Middleware

### CORS Middleware

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Adds Cross-Origin Resource Sharing support:
- `allow_origins`: The parsed list from the environment variable
- `allow_credentials=True`: Allows cookies and authorization headers in cross-origin requests
- `allow_methods=["*"]`: Allows all HTTP methods
- `allow_headers=["*"]`: Allows all headers

**Security note**: The wildcard origin is blocked at module level (see above) because `allow_credentials=True` combined with ` origins=["*"]` is a CORS vulnerability.

**Why no TenantMiddleware?** A comment in the code explains:
```python
# TenantMiddleware removed: endpoints rely on Depends(get_current_tenant)
# which supports all auth methods (Bearer, API key, global key)
```
The project previously had a middleware-based approach but moved to explicit FastAPI `Depends()` injection for greater flexibility and per-endpoint control.

---

## Router Inclusion

```python
app.include_router(auth_router)          # /v1/auth/*
app.include_router(sessions.router)      # /v1/sessions/*
app.include_router(messages_router)      # /v1/sessions/{id}/messages
app.include_router(tenant_router)        # /v1/tenants/*
app.include_router(sync_router)          # /v1/sync/*
```

All API routers are mounted at the root level. Each router defines its own `prefix` internally:
- `auth_router` → `/v1/auth`
- `sessions.router` → `/v1/sessions`
- `messages_router` → `/v1/sessions` (shares prefix with sessions)
- `tenant_router` → `/v1/tenants`
- `sync_router` → `/v1/sync`

**Note**: `messages.py` and `sessions.py` both use `/v1/sessions` prefix, so message endpoints appear under `/v1/sessions/{session_id}/messages`.

---

## Health Check Endpoint

```python
@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}
```

Simple health check returning `{"status": "healthy"}`. Used by load balancers and monitoring systems.

---

## Main Block

```python
if __name__ == "__main__":
    import uvicorn
    from tinycua_backend.config import init_config, get_config

    config_dir = Path(__file__).parent.parent
    config_path = config_dir / "config.yaml"
    init_config(str(config_path))
    config = get_config()
    uvicorn.run(app, host=config.server.host, port=config.server.port)
```

When `main.py` is executed directly (`python -m tinycua_backend.main`):
1. Reloads config (since lifespan won't run in this direct-execution path before config is needed)
2. Runs Uvicorn with host/port from config

**Why config is loaded twice?** In production, Uvicorn imports the module and the lifespan handler loads config. In direct execution, Uvicorn is started manually, so config must be loaded beforehand.

---

## Data Flow at Startup

```
uvicorn starts
    │
    ▼
lifespan enters
    │
    ├──▶ init_config() loads config.yaml + env vars
    │
    ├──▶ create_tables()    ──▶ SQLAlchemy Base.metadata.create_all()
    │                              creates: tenants, users, api_keys,
    │                                       agents, tools
    │
    ├──▶ SessionStore.create_tables()
    │         ──▶ creates: sessions, messages
    │
    └──▶ SQLiteSearch.initialize()  (if sqlite)
              ──▶ creates: messages_fts (FTS5 virtual table)
    │
    yield  ←── app is now ready to accept requests
    │
lifespan exits ──▶ logs shutdown
```

---

## Important Imports Note

```python
from tinycua_sdk.storage.store import SessionStore
```

The comment above this import is critical:
```python
# NOTE: SessionStore is imported from tinycua_sdk for storage-only purposes.
# The backend does not use any execution logic from the SDK (agent loops,
# tools, memory management, etc.). This import is strictly for creating and
# managing the session/message database tables via the SDK's storage layer.
```

This reinforces the architectural boundary: the backend only uses the SDK's storage layer, never its execution engine.
