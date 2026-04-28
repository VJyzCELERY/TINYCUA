# Config Module Documentation

The config module manages user configuration, including loading, saving, and the first-time setup wizard.

---

## Module Structure

```
config/
├── __init__.py      # Re-exports public API
├── user_config.py   # Configuration load/save with merge logic
└── wizard.py        # Interactive first-time setup wizard
```

---

## `config/__init__.py`

```python
from tinycua.config.user_config import UserConfig
from tinycua.config.wizard import (
    SetupWizard, WizardError, WizardValidationError,
    is_first_startup, run_wizard, show_welcome,
)

__all__ = [
    "UserConfig", "SetupWizard", "WizardError",
    "WizardValidationError", "is_first_startup", "run_wizard", "show_welcome"
]
```

---

## `config/user_config.py`

### Purpose

User-facing configuration manager with a **three-way merge strategy**: YAML > env > defaults.

### `UserConfig` Class

This is a utility class with only class methods. It is never instantiated.

### `load()` — Class Method

```python
@classmethod
def load(cls, path: Path | None = None) -> SDKConfig:
```

**Merge strategy:**

```
1. Start with SDKConfig() defaults
2. Overlay SDKConfig.from_env() values
3. Overlay only explicitly set YAML values
```

**Why explicit-only YAML merge?** Pydantic models fill in defaults for missing fields. If we merged the full Pydantic model, environment variables set in step 2 would be overwritten by Pydantic defaults from step 3. By loading YAML as a plain dict and only overlaying explicitly present keys, we preserve the env > defaults priority.

**Implementation:**
```python
# Start with defaults
defaults = SDKConfig()

# Overlay env values
env_config = SDKConfig.from_env()
merged = cls._deep_merge(defaults, env_config)

# Overlay YAML values if file exists
yaml_path = path or cls.DEFAULT_CONFIG_FILE
if yaml_path.exists():
    with open(yaml_path, "r") as f:
        yaml_data: dict[str, Any] = yaml.safe_load(f) or {}

    if yaml_data:
        merged_dict = cls._to_dict(merged)
        yaml_dict = cls._flatten_yaml(yaml_data)
        merged_dict = cls._merge_dicts(merged_dict, yaml_dict)

        # Convert nested dicts back to Pydantic models
        if "llm" in merged_dict and isinstance(merged_dict["llm"], dict):
            merged_dict["llm"] = LLMConfig(**merged_dict["llm"])
        if "memory" in merged_dict and isinstance(merged_dict["memory"], dict):
            merged_dict["memory"] = MemoryConfig(**merged_dict["memory"])
        if "session" in merged_dict and isinstance(merged_dict["session"], dict):
            merged_dict["session"] = SessionConfig(**merged_dict["session"])

        merged = SDKConfig(**merged_dict)
```

### `save()` — Class Method

```python
@classmethod
def save(cls, config: SDKConfig, path: Path | None = None) -> None:
```

**Security:** Sets file permissions to `0o600` (owner read/write only):
```python
os.chmod(save_path, stat.S_IRUSR | stat.S_IWUSR)
```

**Why 0o600?** Configuration files may contain API keys and other secrets. Restricting access to the owner prevents other users on the system from reading credentials.

### `generate_default_config()` — Class Method

```python
@classmethod
def generate_default_config(cls, path: Path | None = None) -> SDKConfig:
```

Creates `~/.tinycua/config.yaml` with default values if it doesn't already exist.

### `_deep_merge()` — Class Method

```python
@classmethod
def _deep_merge(cls, base: SDKConfig, overlay: SDKConfig) -> SDKConfig:
```

Converts both configs to dicts, merges recursively, and reconstructs `SDKConfig`.

### `_merge_dicts()` — Class Method

```python
@classmethod
def _merge_dicts(cls, base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
```

Recursive dictionary merge where overlay takes priority. For nested dicts, recurses. For other values, overlay overwrites.

### `_to_dict()` — Class Method

```python
@classmethod
def _to_dict(cls, config: SDKConfig) -> dict[str, Any]:
```

Converts `SDKConfig` to a plain dict for YAML serialization.

**Note on API key handling:**
```python
"api_key": config.llm.api_key.get_secret_value()
```

Extracts the secret string from Pydantic's `SecretStr` for storage.

### `_flatten_yaml()` — Class Method

```python
@classmethod
def _flatten_yaml(cls, yaml_data: dict[str, Any]) -> dict[str, Any]:
```

Flattens raw YAML data to match `SDKConfig` structure. Only includes explicitly set keys.

**Handles nested sections:**
- `backend_url` (top-level)
- `environment` (top-level)
- `llm` (nested dict)
- `memory` (nested dict)
- `session` (nested dict)

---

## `config/wizard.py`

### Purpose

Interactive setup wizard for first-time TinyCUA users. Collects storage mode, account credentials, and LLM provider configuration.

### `is_first_startup()` Function

```python
def is_first_startup(config_dir: str | Path | None = None) -> bool:
```

**Returns `True` if NONE of these exist:**
- `~/.tinycua/config.yaml`
- `~/.tinycua/data.db`
- `~/.tinycua/credentials.enc`

**Why all three?** A user might have created a config but not initialized storage, or vice versa. Checking all three ensures a complete first-time experience.

### Exception Hierarchy

```python
class WizardError(Exception):
    """Base exception for wizard errors."""

class WizardValidationError(WizardError):
    """Exception for validation errors."""
```

### `SetupWizard` Class

```python
class SetupWizard:
    DEFAULT_LLM_PROVIDER = "lmstudio"
    DEFAULT_LLM_MODEL = "qwen/qwen3.5-9b"
    DEFAULT_LLM_BASE_URL = "http://localhost:1234/v1"
```

Defaults target LM Studio running locally, a popular choice for local LLM execution.

**State attributes:**
```python
self.storage_mode: str | None = None      # "local" or "remote"
self.username: str | None = None
self.email: str | None = None
self.password: str | None = None
self.llm_provider: str | None = None
self.llm_model: str | None = None
self.llm_base_url: str | None = None
self.llm_api_key: str | None = None
self._completed = False
```

### `set_storage_mode()`

```python
def set_storage_mode(self, mode: str) -> None:
    if mode not in ("local", "remote"):
        raise WizardError("Storage mode must be 'local' or 'remote'")
    self.storage_mode = mode
```

### `set_account()`

```python
def set_account(self, username: str, email: str, password: str) -> None:
    self.validate_account(username, email, password)
    self.username = username
    self.email = email
    self.password = password
```

Validates before setting.

### Credential Encryption

### `_get_fernet_key()`

```python
def _get_fernet_key(self) -> bytes:
```

Derives or retrieves a Fernet encryption key for credential storage.

**Priority:**
1. **OS keyring** — Stores key in system secure storage
2. **Environment variable** — `TINYCUA_FERNET_KEY`
3. **Generated random key** — Falls back to random bytes with warning

**Fallback key derivation:**
```python
salt = platform.node().encode()
try:
    salt += os.getlogin().encode()
except OSError:
    salt += b"unknown_user"
salt += b"tinycua_salt_v1"

kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=salt[:16],
    iterations=480000,
)
key = base64.urlsafe_b64encode(kdf.derive(password))
```

**Why PBKDF2 with 480k iterations?** OWASP recommendation for PBKDF2-HMAC-SHA256. Slows down brute-force attacks.

**Key file security:**
```python
key_file.write_bytes(key)
key_file.chmod(0o600)
```

### `save_credentials()`

```python
def save_credentials(self) -> None:
```

Encrypts and saves credentials to `~/.tinycua/credentials.enc`.

```python
fernet = Fernet(self._get_fernet_key())
data = json.dumps({
    "username": self.username,
    "email": self.email,
    "password": self.password,
}).encode()
encrypted = fernet.encrypt(data)
credentials_file.write_bytes(encrypted)
credentials_file.chmod(0o600)
```

### `load_credentials()`

```python
def load_credentials(self) -> bool:
```

Supports Fernet-encrypted format only:

```python
# Fernet decryption
try:
    fernet = Fernet(self._get_fernet_key())
    data = fernet.decrypt(encrypted)
    ...
except (InvalidToken, ValueError, TypeError, OSError):
    return False
```

### `validate_account()`

```python
def validate_account(
    self,
    username: str,
    email: str,
    password: str,
    confirm_password: str | None = None,
) -> None:
```

**Validation rules:**
- Username: not empty
- Email: not empty, matches regex pattern
- Password: ≥ 8 characters
- Password: at least one uppercase letter
- Password: at least one lowercase letter
- Password: at least one digit
- Password: at least one special character
- Confirm password: matches password (if provided)

**Email regex:**
```python
r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
```

**Special characters:**
```python
r"[!@#$%^&*(),.?\":{}|<>]"
```

### `set_llm_config()`

```python
def set_llm_config(
    self,
    provider: str,
    model: str,
    base_url: str,
    api_key: str | None = None,
) -> None:
```

Stores LLM configuration parameters.

### `complete()`

```python
def complete(self) -> SDKConfig:
```

**Validation:**
```python
if self.storage_mode is None:
    raise WizardError("Storage mode not set")
if self.username is None:
    raise WizardError("Account not configured")
if self.llm_provider is None:
    raise WizardError("LLM provider not configured")
```

**Builds and saves config:**
```python
config = self._build_config()
self._save_config(config)
self._completed = True
return config
```

### `_build_config()`

```python
def _build_config(self) -> SDKConfig:
```

Constructs `SDKConfig` from wizard state.

**Local vs remote storage:**
```python
if self.storage_mode == "local":
    memory_url = f"sqlite:///{self.config_dir.as_posix()}/data.db"
else:
    memory_url = "sqlite:///./tinycua.db"
```

**LLM config:**
```python
llm_config = {
    "provider": self.llm_provider or self.DEFAULT_LLM_PROVIDER,
    "model": self.llm_model or self.DEFAULT_LLM_MODEL,
    "base_url": self.llm_base_url or self.DEFAULT_LLM_BASE_URL,
}
if self.llm_api_key:
    from pydantic import SecretStr
    llm_config["api_key"] = SecretStr(self.llm_api_key)
```

### `_save_config()`

```python
def _save_config(self, config: SDKConfig) -> None:
```

Saves config and creates database schema for local storage mode.

**Local database initialization:**
```python
if self.storage_mode == "local":
    db_path = self.config_dir / "data.db"
    if not db_path.exists():
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        conn.commit()
        conn.close()
```

**Why manual schema creation?** The wizard creates the database before the SDK's `SessionStore` is used, ensuring the database is ready on first run.

### Helper Functions

#### `is_lmstudio_available()`

```python
def is_lmstudio_available() -> bool:
```

Checks if LM Studio is running at `http://localhost:1234/v1/models`.

#### `test_connection(url)`

```python
def test_connection(url: str) -> bool:
```

Tests backend connectivity:
1. Tries `/health` endpoint
2. Falls back to base URL (accepts 200 or 404 as success)

#### `show_welcome()`

Prints a welcome banner for first-time users.

#### `prompt_storage_mode()`

Interactive prompt for local (1) or remote (2) storage.

#### `prompt_account_creation()`

Interactive prompt for username, email, and password with confirmation.

#### `prompt_llm_configuration()`

Interactive prompt for LLM provider, model, base URL, and optional API key.

#### `run_wizard()`

```python
def run_wizard() -> SDKConfig:
```

Orchestrates the complete setup wizard:

```python
config_dir = UserConfig.ensure_config_dir()
wizard = SetupWizard(config_dir=config_dir)

show_welcome()
mode = prompt_storage_mode()
wizard.set_storage_mode(mode)

account = prompt_account_creation()
wizard.set_account(account["username"], account["email"], account["password"])

llm_config = prompt_llm_configuration()
wizard.set_llm_config(...)

config = wizard.complete()

print("Setup Complete!")
print(f"Configuration saved to: {config_path}")
print(f"Database saved to: {db_path}")
print("Run 'tinycua repl' to begin.")

return config
```

---

## Config Data Flow

### First Startup Flow

```
User runs tinycua
    │
    ▼
main() checks is_first_startup()
    │
    ▼
No config exists?
    │
    ▼
run_wizard()
    │
    ├─ show_welcome()
    ├─ prompt_storage_mode()
    ├─ prompt_account_creation()
    ├─ prompt_llm_configuration()
    │
    ▼
SetupWizard.complete()
    │
    ├─ _build_config()
    ├─ _save_config()
    │   ├─ UserConfig.save() → config.yaml (0o600)
    │   ├─ save_credentials() → credentials.enc (Fernet, 0o600)
    │   └─ Create data.db with schema
    │
    ▼
Return SDKConfig
```

### Config Load Flow

```
Agent needs configuration
    │
    ▼
UserConfig.load()
    │
    ├─ SDKConfig() defaults
    ├─ SDKConfig.from_env() overlay
    └─ ~/.tinycua/config.yaml overlay (explicit keys only)
    │
    ▼
Return merged SDKConfig
```

---

## Security Considerations

1. **File permissions:** Config files use `0o600`, credential files use `0o600`.

2. **API key storage:** API keys are stored as Pydantic `SecretStr` in memory and written to YAML files. Consider using environment variables for production.

3. **Credential encryption:** Uses Fernet (AES-128-CBC + HMAC) with PBKDF2 key derivation.

4. **Keyring preference:** Tries OS-native secure storage before falling back to file-based keys.

5. **Legacy fallback removed:** The legacy base64-encoded credential fallback has been removed. Only Fernet-encrypted credentials are supported.

6. **Headless warning:** If keyring is unavailable and no environment key is set, a random key is generated with a warning about unstable operation.
