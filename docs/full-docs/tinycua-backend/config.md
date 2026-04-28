# Configuration

**File**: `tinycua_backend/config.py`

---

## Purpose

Manages application configuration through a hierarchy of sources:
1. **Defaults** (hardcoded in Pydantic models)
2. **YAML file** (`config.yaml`)
3. **Environment variables** (override YAML values)

Supports optional hot-reload via `ConfigWatcher`.

---

## Pydantic Config Models

### `RunnerConfig`

```python
class RunnerConfig(BaseModel):
    url: str = "http://localhost:8001"
    token: str = ""
```

- `url`: URL of the tinycua-runner service
- `token`: Authentication token for runner communication (currently not actively used in the backend)

### `DatabaseConfig`

```python
class DatabaseConfig(BaseModel):
    url: str = "postgresql://user:pass@localhost:5432/tinycua"
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
```

- `url`: SQLAlchemy database URL (supports `sqlite:///` and `postgresql://`)
- `pool_size`: Number of persistent connections in the pool
- `max_overflow`: Extra connections allowed beyond `pool_size` under load
- `pool_recycle`: Seconds before a connection is recycled (prevents stale connections)
- `pool_pre_ping`: Verify connection health before use

### `AuthConfig`

```python
class AuthConfig(BaseModel):
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    api_key: str = ""  # Global API key for simple access
```

- `jwt_secret`: Symmetric key for JWT signing (loaded from `JWT_SECRET` env var)
- `jwt_algorithm`: JWT algorithm (default HS256)
- `jwt_expiration_hours`: Token lifetime
- `api_key`: Global API key for system-level access (loaded from `API_KEY` env var)

**Security note**: `jwt_secret` and `api_key` default to empty strings. The application raises errors at runtime if they are not configured.

### `ServerConfig`

```python
class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = []
```

- `host`: Bind address
- `port`: Listen port
- `cors_origins`: Allowed CORS origins (overridden by `TINYCUA_CORS_ORIGINS` env var in `main.py`)

### `Config(BaseModel)`

```python
class Config(BaseModel):
    runner: RunnerConfig = RunnerConfig()
    database: DatabaseConfig = DatabaseConfig()
    auth: AuthConfig = AuthConfig()
    server: ServerConfig = ServerConfig()
```

Root configuration container. Each section is a nested Pydantic model with its own defaults.

---

## Config Loading

### `Config.load(path=".config.yaml") -> Config`

```python
@classmethod
def load(cls, path: str = ".config.yaml") -> "Config":
    config_path = Path(path)
    if not config_path.exists():
        return cls()

    with open(config_path) as f:
        data = yaml.safe_load(f) or {}

    config = cls(**data)

    # Override with environment variables
    if os.environ.get("RUNNER_TOKEN"):
        config.runner.token = os.environ["RUNNER_TOKEN"]
    if os.environ.get("JWT_SECRET"):
        config.auth.jwt_secret = os.environ["JWT_SECRET"]
    if os.environ.get("API_KEY"):
        config.auth.api_key = os.environ["API_KEY"]
    if os.environ.get("DATABASE_URL"):
        config.database.url = os.environ["DATABASE_URL"]
    if os.environ.get("DATABASE_POOL_SIZE"):
        config.database.pool_size = int(os.environ["DATABASE_POOL_SIZE"])
    if os.environ.get("DATABASE_MAX_OVERFLOW"):
        config.database.max_overflow = int(os.environ["DATABASE_MAX_OVERFLOW"])
    if os.environ.get("TINYCUA_CORS_ORIGINS"):
        config.server.cors_origins = os.environ["TINYCUA_CORS_ORIGINS"].split(",")

    return config
```

**Priority order** (highest wins):
1. Environment variables
2. YAML file values
3. Pydantic defaults

**Supported environment variables**:
| Environment Variable | Overrides |
|---------------------|-----------|
| `RUNNER_TOKEN` | `runner.token` |
| `JWT_SECRET` | `auth.jwt_secret` |
| `API_KEY` | `auth.api_key` |
| `DATABASE_URL` | `database.url` |
| `DATABASE_POOL_SIZE` | `database.pool_size` |
| `DATABASE_MAX_OVERFLOW` | `database.max_overflow` |
| `TINYCUA_CORS_ORIGINS` | `server.cors_origins` |

**Why `yaml.safe_load`?** `safe_load` prevents arbitrary code execution from malicious YAML files (unlike `load`).

---

## Config Watcher (Hot Reload)

### `ConfigWatcher`

```python
class ConfigWatcher:
    def __init__(self, path: str, callback: Callable[[Config], None]):
        self.path = Path(path)
        self.callback = callback
        self._running = False
        self._config: Config | None = None
```

Watches a config file for changes and invokes a callback with the new configuration.

### `start()`

```python
def start(self) -> None:
    self._running = True
    self._config = Config.load(str(self.path))
    thread = threading.Thread(target=self._watch, daemon=True)
    thread.start()
```

Starts a **daemon thread** that polls the file's modification time every second.

**Why a daemon thread?** Daemon threads are automatically killed when the main process exits. This prevents the watcher from keeping the application alive unexpectedly.

### `_watch()`

```python
def _watch(self) -> None:
    if not self.path.exists():
        return
    mtime = self.path.stat().st_mtime
    while self._running:
        time.sleep(1)
        try:
            new_mtime = self.path.stat().st_mtime
        except OSError:
            continue
        if new_mtime != mtime:
            mtime = new_mtime
            try:
                self._config = Config.load(str(self.path))
                self.callback(self._config)
            except (OSError, ValueError):
                logger.warning("Config reload failed for %s", self.path, exc_info=True)
```

**Polling-based detection**: Compares `st_mtime` (modification time) every second. If changed, reloads config and calls the callback.

**Limitations**:
- 1-second polling is simple but not instantaneous
- Rapid successive changes might be missed if they happen within the same second
- No file content hash comparison (only mtime)

### `get_config()`

```python
def get_config(self) -> Config:
    if self._config is None:
        self._config = Config.load(str(self.path))
    return self._config
```

Returns the current config, loading it if necessary.

---

## Global Config Functions

### `get_config() -> Config`

```python
_config: Config | None = None
_config_lock = threading.Lock()

def get_config() -> Config:
    global _config
    if _config is None:
        with _config_lock:
            if _config is None:
                _config = Config.load()
    return _config
```

**Double-checked locking** pattern for lazy initialization:
1. Fast path: return cached config
2. Slow path: acquire lock and load if still None

**Why not use `ConfigWatcher.get_config()`?** The global `get_config()` is a simpler API that doesn't require a watcher instance. Most code calls this function.

### `init_config(path, reload_callback=None) -> Config`

```python
def init_config(
    path: str = ".config.yaml", reload_callback: Callable[[Config], None] | None = None
) -> Config:
    global _config_watcher
    global _config

    with _config_lock:
        _config = Config.load(path)

    if reload_callback:
        with _config_watcher_lock:
            _config_watcher = ConfigWatcher(path, reload_callback)
            _config_watcher.start()

    return _config
```

**Called once at application startup** (in `main.py` lifespan).

**Parameters**:
- `path`: Path to YAML config file
- `reload_callback`: Optional function called whenever the file changes

**Thread safety**:
- `_config_lock` protects the config assignment
- `_config_watcher_lock` protects watcher creation

**Current usage**: `main.py` calls `init_config()` without a reload callback, so hot-reload is not currently enabled.

---

## Example config.yaml

```yaml
runner:
  url: "http://localhost:8001"
  token: "runner-secret-token"

database:
  url: "postgresql://tinycua:password@localhost:5432/tinycua"
  pool_size: 20
  max_overflow: 30

auth:
  jwt_secret: "super-secret-jwt-key-change-in-production"
  jwt_algorithm: "HS256"
  jwt_expiration_hours: 24
  api_key: "global-admin-api-key"

server:
  host: "0.0.0.0"
  port: 8000
  cors_origins:
    - "http://localhost:3000"
    - "https://app.tinycua.com"
```

---

## Design Decisions

1. **Pydantic for validation**: All config values are type-checked at load time. Invalid values raise Pydantic validation errors immediately.

2. **Environment override**: Environment variables take precedence over the file. This supports 12-factor app principles and containerized deployments.

3. **Lazy loading**: Config is loaded on first access, not at import time. This prevents errors if the config file doesn't exist during module import.

4. **Optional hot-reload**: The watcher infrastructure exists but is not used in the current deployment. It can be enabled by passing a callback to `init_config()`.
