# Remote Module Documentation

The remote module manages connections to remote backend servers and synchronizes data between local and remote storage.

---

## Module Structure

```
remote/
├── __init__.py              # Re-exports public classes
├── connection_manager.py    # Backend connection lifecycle
└── sync_engine.py           # Data synchronization logic
```

---

## `remote/__init__.py`

```python
from tinycua.remote.connection_manager import RemoteConnectionManager, RemoteConfig, ConnectionStatus
from tinycua.remote.sync_engine import OfflineQueue, SyncEngine, SyncResult

__all__ = [
    "RemoteConnectionManager",
    "RemoteConfig",
    "ConnectionStatus",
    "SyncEngine",
    "SyncResult",
    "OfflineQueue",
]
```

---

## `remote/connection_manager.py`

### Purpose

Manages the lifecycle of connections to remote backend servers, including authentication, connection state tracking, and secure credential storage.

### `validate_backend_url()` Function

```python
def validate_backend_url(url: str) -> tuple[bool, str]:
```

**Validation rules:**
1. URL must not be empty
2. Must include scheme (`http://` or `https://`)
3. Scheme must be `http` or `https`
4. Must have valid host (netloc)
5. HTTP is only allowed for localhost

**Why restrict HTTP?** Prevents sending credentials over unencrypted connections to remote servers. Localhost is exempt because local development often uses HTTP.

### `RemoteConfig` Dataclass

```python
@dataclass
class RemoteConfig:
    backend_url: str
    email: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    api_key: str | None = None
```

Stores all configuration needed for remote connection.

### `ConnectionStatus` Dataclass

```python
@dataclass
class ConnectionStatus:
    connected: bool = False
    mode: str = "local"
    last_sync: str | None = None
    error: str | None = None
```

Tracks the current connection state.

### `RemoteConnectionManager` Class

```python
class RemoteConnectionManager:
    def __init__(
        self,
        backend_url: str | None = None,
        api_key: str | None = None,
        email: str | None = None,
        password: str | None = None,
        config: Optional[RemoteConfig] = None,
    ) -> None:
```

**Initialization options:**
- Pass individual parameters
- Or pass a `RemoteConfig` object

**Keyring integration:**
```python
try:
    import keyring
    from keyring.errors import KeyringError
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False
```

If `keyring` is available and email/password are provided, the password is stored securely.

### Secure Password Storage

```python
def _set_secure_password(self, email: str, password: str) -> bool:
    if not HAS_KEYRING or not email or not password:
        return False
    try:
        keyring.set_password(KEYRING_SERVICE, email, password)
        logger.info("Stored password securely for %s", email)
        return True
    except (KeyringError, OSError, ValueError) as e:
        logger.warning("Failed to store password in keyring: %s", e)
        return False
```

**Why keyring?** Uses the OS-native secure storage (macOS Keychain, Windows Credential Locker, Linux Secret Service) instead of storing passwords in plain text.

```python
def _get_secure_password(self, email: str) -> Optional[str]:
    if not HAS_KEYRING or not email:
        return None
    try:
        return keyring.get_password(KEYRING_SERVICE, email)
    except (KeyringError, OSError, ValueError) as e:
        logger.warning("Failed to retrieve password from keyring: %s", e)
        return None
```

### `load_config()`

```python
def load_config(self, config: RemoteConfig | None = None) -> bool:
```

Loads remote configuration from:
1. Passed `RemoteConfig` object (highest priority)
2. `UserConfig.load()` — reads `~/.tinycua/config.yaml`

```python
if user_config.backend_url:
    api_key_value = None
    if user_config.llm and user_config.llm.api_key:
        api_key_value = user_config.llm.api_key.get_secret_value()
    self.config = RemoteConfig(
        backend_url=user_config.backend_url,
        api_key=api_key_value,
    )
```

**Note:** The API key from LLM config is reused for backend authentication. This assumes the same credentials work for both LLM provider and backend.

### `connect()` — Async Connection with Retry

```python
async def connect(
    self,
    email: str | None = None,
    password: str | None = None,
    api_key: str | None = None,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    timeout: float = 30.0,
) -> bool:
```

**Connection flow:**

1. **Validate URL:**
   ```python
   is_valid, error_msg = validate_backend_url(self.config.backend_url)
   ```

2. **Rate limiting:**
   ```python
   time_since_last_attempt = now - self._last_connection_attempt
   if time_since_last_attempt < self._min_connection_interval:
       wait_time = self._min_connection_interval - time_since_last_attempt
       await asyncio.sleep(wait_time)
   ```
   Minimum 5 seconds between connection attempts.

3. **Resolve credentials:**
   ```python
   email = email or self.config.email
   password = password or (self._get_secure_password(email) if email else None)
   api_key = api_key or self.config.api_key
   ```

4. **Create client:**
   ```python
   self._client = BackendClient(
       base_url=self.config.backend_url,
       api_key=api_key,
       email=email,
       password=password,
       timeout=int(timeout),
   )
   ```

5. **Login (if credentials provided):**
   ```python
   if email and password:
       try:
           await self._client.login(email=email, password=password)
       except ...:
           logger.warning("Login failed: %s", e)
   ```

6. **Health check with retries:**
   ```python
   for attempt in range(max_retries):
       if await self._client.health_check():
           self._connected = True
           self._mode = "remote"
           self._status = ConnectionStatus(connected=True, mode="remote")
           return True
       # Exponential backoff
       delay = retry_delay * (2 ** attempt)
       await asyncio.sleep(delay)
   ```

**Retry strategy:** Exponential backoff (`retry_delay * 2^attempt`). With defaults: 1s, 2s, 4s delays.

**Returns:** `True` if connected, `False` after all retries exhausted.

### `disconnect()`

```python
async def disconnect(self) -> None:
```

Closes the HTTP client and resets state to local mode.

### `test_connection()`

```python
async def test_connection(self, url: str | None = None) -> tuple[bool, str]:
```

Tests connectivity without modifying connection state.

**Behavior:**
- If testing a different URL than current client: creates temporary client
- Always performs health check
- Returns `(True, "")` on success or `(False, error_message)` on failure

### `refresh_token()`

```python
async def refresh_token(self) -> bool:
```

Refreshes authentication token if the backend supports it.

```python
if hasattr(self._client, "refresh_token"):
    result = await self._client.refresh_token()
    if hasattr(result, "expires_at"):
        self._token_expires_at = result.expires_at
    else:
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
```

### `get_sync_engine()`

```python
def get_sync_engine(self) -> "SyncEngine":
    if self._sync_engine is None:
        from tinycua.remote.sync_engine import SyncEngine
        self._sync_engine = SyncEngine(connection_manager=self)
    return self._sync_engine
```

Lazy initialization of `SyncEngine`.

---

## `remote/sync_engine.py`

### Purpose

Synchronizes data between local SQLite storage and remote backend using last-write-wins conflict resolution.

### `SyncResult` Dataclass

```python
@dataclass
class SyncResult:
    success: bool
    items_synced: int = 0
    errors: list[str] = field(default_factory=list)
```

### `QueuedOperation` Dataclass

```python
@dataclass
class QueuedOperation:
    operation_type: str
    session_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

### `OfflineQueue` Class

Persistent queue for operations when offline.

```python
class OfflineQueue:
    def __init__(self, queue_file: Optional[Path] = None) -> None:
```

**Storage location:**
- If `platformdirs` is available: `{user_data_dir}/tinycua/offline_queue.json`
- Fallback: `~/.local/share/tinycua/offline_queue.json` or `$XDG_DATA_HOME/tinycua/offline_queue.json`

**Queue operations:**

| Method | Purpose |
|--------|---------|
| `enqueue(operation)` | Adds operation to queue and saves |
| `dequeue()` | Removes and returns oldest operation |
| `clear()` | Removes all operations |
| `size()` | Returns queue length |
| `is_empty()` | Checks if queue is empty |

**Persistence:** The queue is saved to JSON after every mutation. Uses blocking I/O with a note that async I/O could be considered for high-frequency operations.

### `ConflictResolver` Class

Implements **last-write-wins** conflict resolution.

```python
class ConflictResolver:
    @staticmethod
    def resolve(local_item: dict[str, Any], remote_item: dict[str, Any]) -> dict[str, Any]:
```

**Timestamp extraction:**
```python
@staticmethod
def _get_timestamp(item: dict[str, Any]) -> datetime | None:
    for key in ("updated_at", "created_at", "timestamp"):
        ts = item.get(key)
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError):
                continue
    return None
```

**Resolution logic:**
- If only one item exists, return it
- If neither has a timestamp, prefer local
- Compare timestamps; return the more recent one
- Ensures timezone-aware comparison (assumes UTC if no timezone)

### `SyncEngine` Class

```python
class SyncEngine:
    def __init__(self, connection_manager: RemoteConnectionManager) -> None:
        self._connection_manager = connection_manager
        self._last_sync: Optional[datetime] = None
        self._offline_queue = OfflineQueue()
```

### `sync_sessions()`

```python
async def sync_sessions(self) -> SyncResult:
```

**Logic:**
1. Checks connection; if offline, queues operation
2. Fetches local sessions via `_get_local_sessions()`
3. Fetches remote sessions via `client.list_sessions()`
4. Merges using `_merge_sessions()` (last-write-wins)
5. Pushes merged sessions to backend
6. Saves new remote sessions to local storage
7. Updates last sync timestamp

**Note:** Uses `client.update_session()` for existing sessions and `client.create_session()` for new ones.

### `sync_messages()`

```python
async def sync_messages(self, session_id: str) -> SyncResult:
```

Syncs messages for a specific session.

**Logic:**
1. Fetches remote and local messages
2. Merges using `_merge_messages()`
3. Saves merged messages locally
4. Pushes merged messages to remote

### `sync_memory()`

```python
async def sync_memory(self) -> SyncResult:
```

Syncs memory data for all sessions.

**Logic:**
1. Iterates over all local sessions
2. For each session, fetches remote and local memory
3. Merges using `_merge_memory()`
4. Saves merged memory to remote

### `replay_offline_queue()`

```python
async def replay_offline_queue(self) -> SyncResult:
```

Replays queued operations after reconnection.

**Supported operation types:**
- `sync_memory` → calls `sync_memory()`
- `sync_sessions` → calls `sync_sessions()`
- `sync_messages` → calls `sync_messages(session_id)`

**Error handling:** Individual operation failures are logged but don't stop processing the rest of the queue.

### `push_all()`

```python
async def push_all(self) -> SyncResult:
```

Pushes all local sessions to remote backend.

**Logic:**
1. Gets all local sessions
2. For each session, calls `_push_session()`
3. Updates last sync timestamp

### `pull_all()`

```python
async def pull_all(self) -> SyncResult:
```

Pulls all remote sessions to local storage.

**Logic:**
1. Fetches all remote sessions
2. For each session, calls `_pull_session()`
3. Updates last sync timestamp

### `_get_from_store()` — Generic Helper

```python
def _get_from_store(self, method_name: str, *args, default=None):
```

Calls methods on `LocalStorageManager`'s current store with error handling.

**Why this helper?** Reduces repetitive try/except boilerplate across all sync methods.

### `_get_local_sessions()`

```python
async def _get_local_sessions(self) -> list[dict[str, Any]]:
```

Returns sessions as dictionaries with `id`, `name`, and `updated_at` fields.

### `_get_local_messages()`

```python
async def _get_local_messages(self, session_id: str) -> list[dict[str, Any]]:
```

Returns messages for a session as dictionaries.

### `_get_local_memory()`

```python
async def _get_local_memory(self, session_id: str) -> dict[str, Any]:
```

Returns memory content and updated_at timestamp.

### `_merge_sessions()`

```python
def _merge_sessions(self, local_sessions: list[dict], remote_sessions: list[dict]) -> list[dict]:
```

Merges sessions by ID using `ConflictResolver.resolve()`. Sessions without IDs are skipped.

### `_merge_messages()`

```python
def _merge_messages(self, local_messages: list[dict], remote_messages: list[dict]) -> tuple[list[dict], int]:
```

Merges messages by ID. Returns `(merged_messages, count)`.

### `_merge_memory()`

```python
def _merge_memory(self, local_memory: dict[str, Any], remote_memory: dict[str, Any]) -> dict[str, Any]:
```

Delegates to `ConflictResolver.resolve()`.

### `_push_session()`

```python
async def _push_session(self, client: "BackendClient", session: dict[str, Any]) -> SyncResult:
```

Pushes a single session to remote:
- If session has ID: calls `client.update_session()`
- If no ID: calls `client.create_session()`

### `_pull_session()`

```python
async def _pull_session(self, session: dict[str, Any]) -> SyncResult:
```

Pulls a single session from remote to local:
- Creates session with preserved ID (or new UUID if invalid)
- Uses `LocalStorageManager.get_instance().get_store().create_session()`

---

## Remote Data Flow

### Connection Flow

```
User runs /connect <url>
    │
    ▼
ChatScreen._cmd_connect()
    │
    ▼
TinyCUAApp.init_remote(url, api_key)
    │
    ▼
RemoteConnectionManager.__init__()
    │
    ▼
User runs /sync
    │
    ▼
ChatScreen._cmd_sync()
    │
    ▼
SyncEngine.push_all()
    │
    ├─ Get local sessions
    ├─ For each session:
    │   └─ Push to backend
    │
    ▼
Update status with sync results
```

### Offline Operation Flow

```
User runs /sync while offline
    │
    ▼
SyncEngine.sync_sessions()
    │
    ▼
Not connected → queue operation
    │
    ▼
OfflineQueue.enqueue({"type": "sync_sessions"})
    │
    ▼
Later: connection restored
    │
    ▼
SyncEngine.replay_offline_queue()
    │
    ▼
Dequeue and execute queued operations
```

---

## Design Decisions

1. **Last-write-wins:** Simple conflict resolution that works well for single-user scenarios. More complex strategies (merge, manual resolution) could be added later.

2. **Offline queue:** Operations are queued when offline and replayed on reconnection. This provides a basic offline-first experience.

3. **Exponential backoff:** Connection retries use exponential backoff to avoid overwhelming the backend or network.

4. **Keyring integration:** Passwords are stored in OS-native secure storage when available, falling back to unencrypted storage only when necessary.

5. **Lazy sync engine:** `SyncEngine` is only created when needed via `get_sync_engine()`.

6. **Blocking I/O for queue:** The offline queue uses blocking file I/O for simplicity. This is acceptable because queue operations are infrequent.

7. **Rate limiting:** Minimum 5-second interval between connection attempts prevents accidental DoS.

8. **HTTP localhost exemption:** Allows HTTP for localhost to support local development without TLS certificates.
