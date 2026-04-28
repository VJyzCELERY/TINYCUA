# Authentication System

**Files**:
- `tinycua_backend/auth/core.py`
- `tinycua_backend/auth/jwt.py`
- `tinycua_backend/auth/passwords.py`
- `tinycua_backend/auth/service.py`
- `tinycua_backend/auth/models.py`
- `tinycua_backend/auth/schemas.py`
- `tinycua_backend/auth/dependencies.py`
- `tinycua_backend/auth/api_keys.py`

---

## auth/core.py — Backward-Compatible Re-Export Shim

**Purpose**: Maintains backward compatibility by re-exporting all authentication utilities from their focused submodules. This allows existing code to import from `auth.core` while the actual implementations live in specialized files.

**Re-exports**:
```python
from tinycua_backend.auth.api_keys import (
    MAX_API_KEYS_PER_REQUEST,
    MIN_API_KEY_LENGTH,
    create_api_key,
    hash_api_key,
    verify_api_key,
)
from tinycua_backend.auth.dependencies import (
    CurrentTenant,
    get_current_tenant,
    get_or_create_system_tenant,
)
from tinycua_backend.auth.jwt import create_jwt_token, decode_jwt_token
from tinycua_backend.auth.passwords import hash_password, verify_password, pwd_context
```

**Why a shim?** When the auth system was refactored into submodules (`passwords.py`, `jwt.py`, `api_keys.py`, `dependencies.py`), existing imports throughout the codebase would have broken. The shim preserves the old import paths while the new structure enables better maintainability.

---

## auth/passwords.py — Password Hashing

**Purpose**: Provides bcrypt password hashing and verification using `passlib`.

### `pwd_context`

```python
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
```

- `schemes=["bcrypt"]`: Only uses bcrypt
- `deprecated="auto"`: Automatically marks deprecated hashes and rehashes on verify
- `bcrypt__rounds=12`: 12 rounds of bcrypt (work factor). This is a balance between security and performance (~250ms per hash on modern hardware).

### `hash_password(password: str) -> str`

Hashes a raw password string using bcrypt. Returns the hash string (includes salt and algorithm metadata).

### `verify_password(password: str, hashed: str) -> bool`

Verifies a raw password against a bcrypt hash. Returns `True` if they match.

---

## auth/jwt.py — JWT Token Utilities

**Purpose**: Creates and validates JWT tokens for session-based authentication.

### `_get_jwt_secret() -> str`

```python
def _get_jwt_secret() -> str:
    config = get_config()
    secret = config.auth.jwt_secret or os.environ.get("JWT_SECRET", "")
    if not secret:
        raise RuntimeError("JWT secret not configured...")
    return secret
```

Resolves the JWT signing secret from:
1. `config.auth.jwt_secret`
2. `JWT_SECRET` environment variable

Raises `RuntimeError` if neither is set. This prevents the app from running with an insecure default secret.

### `create_jwt_token(user_id, tenant_id, email, expires_delta) -> str`

```python
def create_jwt_token(
    user_id: str,
    tenant_id: str,
    email: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    config = get_config()
    jwt_secret = _get_jwt_secret()
    if expires_delta is None:
        expires_delta = timedelta(hours=config.auth.jwt_expiration_hours)

    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    if email:
        payload["email"] = email
    return jwt.encode(payload, jwt_secret, algorithm=config.auth.jwt_algorithm)
```

**JWT payload fields**:
- `sub` (subject): User ID
- `tenant_id`: Tenant ID for tenant scoping
- `exp`: Expiration timestamp
- `iat`: Issued-at timestamp
- `jti`: JWT ID (unique UUID for token revocation support in the future)
- `email`: Optional user email

**Default expiration**: 24 hours (from `config.auth.jwt_expiration_hours`)

### `decode_jwt_token(token: str) -> dict[str, Any]`

```python
def decode_jwt_token(token: str) -> dict[str, Any]:
    config = get_config()
    jwt_secret = _get_jwt_secret()
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=[config.auth.jwt_algorithm])
        return dict(payload)
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid JWT token") from e
```

Validates signature, expiration, and algorithm. Raises `HTTPException(401)` on any validation failure.

---

## auth/api_keys.py — API Key Utilities

**Purpose**: Generates, hashes, and verifies API keys for programmatic access.

### Constants

```python
MIN_API_KEY_LENGTH = 32
MAX_API_KEYS_PER_REQUEST = 5
```

- `MIN_API_KEY_LENGTH`: Minimum length for an API key to be considered valid (used in `get_current_tenant` to quickly reject short tokens)
- `MAX_API_KEYS_PER_REQUEST`: Maximum number of API keys to check per prefix lookup (prevents DoS from too many keys sharing a prefix)

### `hash_api_key(key: str) -> str`

Uses the same bcrypt `CryptContext` as passwords to hash API keys. Why bcrypt for API keys? Because API keys are long-lived credentials that need strong protection if the database is compromised.

### `verify_api_key(key: str, hashed: str) -> bool`

Verifies a raw API key against its bcrypt hash.

### `create_api_key() -> str`

```python
def create_api_key() -> str:
    return f"tcu_{secrets.token_urlsafe(32)}"
```

Generates a URL-safe random token with a `tcu_` prefix:
- `secrets.token_urlsafe(32)`: Produces ~43 characters of base64url-encoded randomness
- Total length: ~47 characters
- Prefix allows quick visual identification and prefix-based database indexing

---

## auth/models.py — User and APIKey Models

### `User(Base, UUIDMixin, TimestampMixin)`

**Table**: `users`

```python
class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", "tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

**Fields**:
- `id`: UUID primary key (from `UUIDMixin`)
- `tenant_id`: Foreign key to `tenants.id`
- `email`: User's email address
- `password_hash`: Bcrypt hash. Nullable to support password-less users (e.g., API-key-only access in the future)
- `created_at`, `updated_at`: Timestamps (from `TimestampMixin`)

**Constraint**: `(email, tenant_id)` must be unique. This allows the same email to exist in different tenants.

### `APIKey(Base, UUIDMixin)`

**Table**: `api_keys`

```python
class APIKey(Base, UUIDMixin):
    __tablename__ = "api_keys"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="api_keys")
```

**Fields**:
- `key_hash`: Bcrypt hash of the full API key (never store raw keys)
- `key_prefix`: First 8 characters of the raw key. Used for fast database lookup without storing the full key
- `name`: Human-readable label (e.g., "Default API Key")
- `scopes`: JSON list of permission scopes (not currently enforced but reserved for future RBAC)
- `expires_at`: Optional expiration datetime
- `is_active`: Soft-delete flag
- `last_used_at`: Audit timestamp updated on each use

---

## auth/schemas.py — Pydantic Schemas

### `RegisterRequest`

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    tenant_name: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v
```

**Validation**:
- `email`: Must be a valid email format (`EmailStr` from Pydantic)
- `password`: Minimum 8 characters
- Password complexity via custom `@field_validator`: requires uppercase, lowercase, digit, and special character

### `LoginRequest`

```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    tenant_id: str | None = None
```

- `tenant_id` is optional. If omitted, the system searches across all tenants for the email.

### `TokenResponse`

```python
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    user_id: str
    api_key: str | None = None
```

Standard OAuth2-style token response. `api_key` is included on registration so the user receives their programmatic access key immediately.

---

## auth/dependencies.py — Authentication Dependency

**Purpose**: The heart of the authentication system. `get_current_tenant` is used as a FastAPI `Depends()` in nearly every protected endpoint.

### `CurrentTenant`

```python
class CurrentTenant:
    def __init__(self, tenant: Tenant, user_id: str | None = None):
        self.tenant = tenant
        self.user_id = user_id

    @property
    def is_system(self) -> bool:
        return self.tenant.tenant_type == TenantType.SYSTEM
```

Wraps the authenticated tenant and optional user ID. The `is_system` property is the primary gate for admin-level operations.

### `get_or_create_system_tenant(db: Session) -> Tenant`

```python
def get_or_create_system_tenant(db: Session) -> Tenant:
    system_tenant = db.query(Tenant).filter(Tenant.tenant_type == TenantType.SYSTEM).first()
    if system_tenant:
        return system_tenant

    system_tenant = Tenant(name="System", tenant_type=TenantType.SYSTEM)
    db.add(system_tenant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        system_tenant = db.query(Tenant).filter(Tenant.tenant_type == TenantType.SYSTEM).first()
        if system_tenant:
            return system_tenant
        raise
    db.refresh(system_tenant)
    return system_tenant
```

**Race condition handling**: If two requests simultaneously try to create the system tenant, one will hit an `IntegrityError` (due to the unique constraint on `tenant_type='system'`). The loser rolls back and retries the select.

### `get_current_tenant(authorization, db)` — The Auth Pipeline

**Priority order** (first match wins):

1. **Global API Key** (system access)
2. **JWT Bearer Token** (user access)
3. **Tenant API Key** (programmatic access)

**Step 1: Parse Authorization header**
```python
if not authorization:
    raise HTTPException(401, "Missing authorization header")
try:
    scheme, token = authorization.split(" ", 1)
except ValueError:
    raise HTTPException(401, "Invalid authorization header format")
```

Expects `Authorization: <scheme> <token>`.

**Step 2: Global API Key**
```python
config = get_config()
if config.auth.api_key and hmac.compare_digest(token, config.auth.api_key):
    system_tenant = await asyncio.to_thread(get_or_create_system_tenant, db)
    return CurrentTenant(tenant=system_tenant, user_id="system")
```

- Uses `hmac.compare_digest()` for **timing-safe comparison** to prevent timing attacks
- If the token matches the configured global API key, grants system-level access
- The system tenant is created on-demand if it doesn't exist

**Step 3: JWT Bearer Token**
```python
if scheme.lower() == "bearer":
    try:
        payload = decode_jwt_token(token)
        tenant_id = payload.get("tenant_id")
        user_id = payload.get("sub")
        tenant_uuid = uuid.UUID(tenant_id)
        tenant = await asyncio.to_thread(lambda: db.query(Tenant).filter(...).first())
        if not tenant:
            raise HTTPException(401, "Invalid tenant")
        return CurrentTenant(tenant=tenant, user_id=user_id)
    except HTTPException:
        raise
    except (JWTError, ValueError, KeyError):
        pass  # Fall through to API key
```

- Validates JWT signature and expiration via `decode_jwt_token()`
- Looks up the tenant in the database to ensure it still exists
- Uses `asyncio.to_thread()` to run blocking SQLAlchemy queries without blocking the event loop
- Any JWT validation failure is caught and falls through to API key auth (allows API keys that happen to look like JWTs)

**Step 4: Tenant API Key**
```python
if len(token) < MIN_API_KEY_LENGTH:
    raise HTTPException(401, "Invalid API key")

key_prefix = token[:8]
api_keys = await asyncio.to_thread(
    lambda: db.query(APIKey)
    .filter(APIKey.is_active.is_(True), APIKey.key_prefix == key_prefix)
    .limit(MAX_API_KEYS_PER_REQUEST)
    .all()
)
```

- Quick length check rejects obviously invalid keys
- Looks up active API keys by the 8-character prefix (fast index lookup)
- Limits to `MAX_API_KEYS_PER_REQUEST` (5) to prevent DoS

```python
matched_key = None
for api_key in api_keys:
    if verify_api_key(token, api_key.key_hash):
        matched_key = api_key
        break
```

Bcrypt-verifies each candidate key. Stops at first match.

```python
now = datetime.now(timezone.utc)
if matched_key.expires_at and matched_key.expires_at < now:
    raise HTTPException(401, "API key has expired")

matched_key.last_used_at = now
await asyncio.to_thread(db.commit)
```

Checks expiration and updates `last_used_at` for audit purposes.

```python
tenant = await asyncio.to_thread(
    lambda: db.query(Tenant).filter(Tenant.id == matched_key.tenant_id).first()
)
if not tenant:
    raise HTTPException(401, "Invalid API key")
return CurrentTenant(tenant=tenant)
```

Looks up the tenant associated with the API key and returns it without a user_id (API keys are tenant-scoped, not user-scoped).

---

## auth/service.py — AuthService

**Purpose**: Encapsulates registration and login business logic.

### `AuthService.__init__(self, db)`

Stores the database session for all operations.

### `AuthService.register(email, password, tenant_name) -> TokenResponse`

**Transaction flow**:
1. Create `Tenant` with the provided name (or auto-generated)
2. `db.flush()` — writes tenant to DB to get its UUID
3. Create `User` with `tenant_id`, email, and password hash
4. `db.flush()` — attempts to write user
   - If `IntegrityError` (duplicate email in tenant): rollback and raise `ValueError`
5. Create `APIKey` for the tenant
6. `db.commit()` — final commit
   - If `IntegrityError`: rollback and raise `ValueError`
7. Refresh user and create JWT token
8. Return `TokenResponse` with token, tenant_id, user_id, and raw API key

**Why two flush points?** To catch the duplicate email early (step 4) before creating the API key, avoiding unnecessary work. However, there's a small race condition window between flush and commit.

### `AuthService.login(email, password, tenant_id) -> TokenResponse`

1. Validates `tenant_id` as UUID
2. Looks up user by email + tenant_id
3. Verifies password against bcrypt hash
4. Creates JWT token
5. Returns `TokenResponse`

Raises `ValueError("Invalid credentials")` for any failure (user not found, wrong password) to prevent information leakage.

---

## Authentication Data Flow

```
Client Request
    │
    ├──▶ Authorization: Bearer <jwt>
    │         │
    │         ▼
    │    get_current_tenant()
    │         │
    │         ├──▶ Check global API key? → System tenant
    │         │
    │         ├──▶ Decode JWT → validate signature/exp
    │         │      └──▶ Lookup tenant in DB
    │         │            └──▶ CurrentTenant(tenant, user_id)
    │         │
    │         └──▶ (fallback) Lookup API key by prefix
    │                └──▶ Bcrypt verify
    │                      └──▶ Check expiration
    │                            └──▶ Update last_used_at
    │                                  └──▶ CurrentTenant(tenant)
    │
    └──▶ Authorization: tcu_xxxx (API key)
              └──▶ Same fallback path as above
```

---

## Security Considerations

1. **Timing attacks**: Prevented via `hmac.compare_digest()` for global API keys and dummy hash for missing users in login.
2. **Bcrypt rounds**: 12 rounds provides ~250ms per hash, slowing brute force.
3. **JWT expiration**: 24-hour default limits window of compromise.
4. **Key prefix indexing**: API keys are looked up by prefix first, so only a small subset needs bcrypt verification.
5. **No raw key storage**: Only bcrypt hashes are stored; the raw key is shown once at creation.
6. **Tenant isolation**: Every auth method resolves to a `CurrentTenant`, and endpoints verify tenant ownership.
