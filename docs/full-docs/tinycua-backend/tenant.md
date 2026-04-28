# Tenant Management

**Files**:
- `tinycua_backend/tenant/models.py`
- `tinycua_backend/tenant/manager.py`

---

## tenant/models.py — Tenant Model

**Purpose**: Defines the `Tenant` SQLAlchemy model and the `TenantType` enum for multi-tenancy.

### `TenantType(str, Enum)`

```python
class TenantType(str, Enum):
    STANDARD = "standard"
    SYSTEM = "system"
```

**Why `str, Enum`?** This creates a Python enum where each member is also a string. SQLAlchemy can store these directly in `String` columns.

- `STANDARD`: Normal tenant. Users, sessions, and resources belong to this tenant. Subject to all access control checks.
- `SYSTEM`: Special tenant for global administration. The global API key authenticates as the system tenant. Bypasses tenant restrictions in most endpoints.

### `Tenant(Base, UUIDMixin, TimestampMixin)`

**Table**: `tenants`

```python
class Tenant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_type: Mapped[TenantType] = mapped_column(
        String(20), nullable=False, default=TenantType.STANDARD
    )

    __table_args__ = (
        Index(
            "uq_system_tenant_type",
            "tenant_type",
            unique=True,
            sqlite_where=text("tenant_type = 'system'"),
            postgresql_where=text("tenant_type = 'system'"),
        ),
    )

    users: Mapped[list["User"]] = relationship("User", cascade="all, delete-orphan")
    api_keys: Mapped[list["APIKey"]] = relationship("APIKey", cascade="all, delete-orphan", back_populates="tenant")
    agents: Mapped[list["Agent"]] = relationship("Agent", cascade="all, delete-orphan")
    tools: Mapped[list["Tool"]] = relationship("Tool", cascade="all, delete-orphan")
```

**Fields**:
- `name`: Human-readable tenant name (e.g., "Acme Corp", "Tenant for user@example.com")
- `tenant_type`: Either `standard` or `system`

**Unique Constraint**: `uq_system_tenant_type`

```python
Index(
    "uq_system_tenant_type",
    "tenant_type",
    unique=True,
    sqlite_where=text("tenant_type = 'system'"),
    postgresql_where=text("tenant_type = 'system'"),
)
```

This is a **partial unique index**: it enforces uniqueness only for rows where `tenant_type = 'system'`. This ensures there can be at most one system tenant, while allowing unlimited standard tenants.

- `sqlite_where` and `postgresql_where` are both provided because SQLAlchemy's `Index` requires dialect-specific condition syntax for partial indexes.

**Relationships**:
- `users`: One-to-many with `User`. `cascade="all, delete-orphan"` means deleting a tenant deletes all its users.
- `api_keys`: One-to-many with `APIKey`. Also cascades delete.
- `agents`: One-to-many with `Agent`. Also cascades delete.
- `tools`: One-to-many with `Tool`. Also cascades delete.

**Cascading delete implications**: Deleting a tenant is destructive — it removes ALL associated data. The `delete_tenant` endpoint in `api/tenant.py` restricts this to system tenants only.

---

## tenant/manager.py — TenantManager

**Purpose**: Encapsulates CRUD operations for tenants in a service class pattern.

### `TenantManager.__init__(self, db)`

Stores the SQLAlchemy session for all operations.

### `create_tenant(name, tenant_type=TenantType.STANDARD) -> Tenant`

```python
def create_tenant(self, name: str, tenant_type: TenantType = TenantType.STANDARD) -> Tenant:
    tenant = Tenant(name=name, tenant_type=tenant_type)
    self._db.add(tenant)
    try:
        self._db.commit()
        self._db.refresh(tenant)
    except IntegrityError:
        self._db.rollback()
        raise ValueError(f"Tenant with name '{name}' already exists")
    return tenant
```

**Why might this raise `IntegrityError`?** Currently, there is no unique constraint on `tenants.name` in the model definition. The `IntegrityError` would only occur if:
1. The partial unique index on `tenant_type='system'` is violated (trying to create a second system tenant)
2. A database-level unique constraint on name exists that isn't visible in the code

The error message "Tenant with name '...' already exists" suggests the developer intended to add a name uniqueness constraint but may not have implemented it yet.

### `get_tenant(tenant_id) -> Tenant | None`

Looks up a tenant by UUID primary key. Returns `None` if not found.

### `get_tenant_by_name(name) -> Tenant | None`

Looks up a tenant by name. Case-sensitive exact match.

### `list_tenants() -> list[Tenant]`

Returns all tenants in the database.

### `update_tenant(tenant_id, name) -> Tenant`

```python
def update_tenant(self, tenant_id: uuid.UUID, name: str) -> Tenant:
    tenant = self.get_tenant(tenant_id)
    if not tenant:
        raise ValueError("Tenant not found")
    tenant.name = name
    self._db.commit()
    self._db.refresh(tenant)
    return tenant
```

Simple update with existence check. No partial update support (must provide a name).

### `delete_tenant(tenant_id) -> None`

```python
def delete_tenant(self, tenant_id: uuid.UUID) -> None:
    tenant = self.get_tenant(tenant_id)
    if not tenant:
        raise ValueError("Tenant not found")
    self._db.delete(tenant)
    self._db.commit()
```

**Cascade behavior**: Because of `cascade="all, delete-orphan"` on all relationships, deleting a tenant also deletes:
- All users belonging to the tenant
- All API keys
- All agents
- All tools

Sessions and messages are stored via the SDK's `SessionStore` and are NOT automatically deleted. The backend does not cascade to SDK tables.

### `list_tenant_users(tenant_id) -> list[User]`

Returns all users in a given tenant.

---

## Tenant Data Flow

```
Registration (api/auth.py)
    |
    |--> AuthService.register()
          |
          |--> Tenant(name=tenant_name)
          |      |
          |      |--> db.add(tenant)
          |      |--> db.flush()  (tenant gets UUID)
          |
          |--> User(tenant_id=tenant.id, ...)
          |      |
          |      |--> db.add(user)
          |      |--> db.flush()
          |
          |--> APIKey(tenant_id=tenant.id, ...)
                 |
                 |--> db.add(api_key)
                 |--> db.commit()
```

---

## Access Control Patterns

Tenants enforce access control at multiple layers:

1. **Authentication layer** (`auth/dependencies.py`):
   - `get_current_tenant()` resolves the tenant from JWT, API key, or global key
   - `CurrentTenant.is_system` determines admin privileges

2. **API layer** (`api/tenant.py`):
   - System tenant required for `list_tenants()` and `delete_tenant()`
   - Regular tenants can only view/update themselves

3. **Session layer** (`api/dependencies.py`):
   - `_verify_session_tenant()` checks `session.user_id` against `current.user_id` or `current.tenant.id`

4. **Search layer** (`api/sessions.py`):
   - Search results are filtered by `SessionModel.tenant_id == tenant_id`
