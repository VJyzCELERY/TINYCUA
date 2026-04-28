# Migrations

**File**: `tinycua_backend/migrations/migrate_sqlite_to_postgres.py`

---

## Purpose

A standalone command-line utility for migrating data from a SQLite database to PostgreSQL. Supports:
- **Dry-run mode**: Preview what would be migrated without writing data
- **Validation mode**: Compare row counts after migration
- **Rollback mode**: Truncate all target tables
- **Incremental mode**: Migrate only records updated/created after a given timestamp

**Why a script instead of Alembic?** This is a one-way data migration tool, not a schema migration tool. Both SQLite and PostgreSQL schemas are auto-created by `Base.metadata.create_all()` and `SessionStore.create_tables()`. This script only copies data.

---

## Allowed Tables

```python
ALLOWED_TABLES = frozenset({
    "tenants", "users", "api_keys", "agents", "tools",
    "sessions", "messages"
})
```

Only these tables can be migrated. This prevents accidental modification of unrelated tables.

### `validate_table_name(table: str) -> str`

```python
def validate_table_name(table: str) -> str:
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Invalid table name: {table}. Must be one of {ALLOWED_TABLES}")
    return table
```

Validates table names against the allowlist before using them in SQL queries. This is a security measure against SQL injection (though the script is interactive, defense in depth is good practice).

---

## Connection Helpers

### `connect_sqlite(path: str) -> sqlite3.Connection`

```python
def connect_sqlite(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn
```

- `row_factory = sqlite3.Row`: Allows column access by name (e.g., `row["email"]`)

### PostgreSQL Connection

```python
import psycopg2
postgres_conn = psycopg2.connect(args.postgres_url)
```

Uses `psycopg2` directly (not SQLAlchemy). This is a deliberate choice for a migration script because:
- Direct DBAPI is simpler for bulk inserts
- No ORM overhead
- Easier to handle `ON CONFLICT` and PostgreSQL-specific syntax

**Note**: `psycopg2` is an optional dependency. The script catches `ImportError` and prints an installation instruction.

---

## Table Migration Functions

Each table has a dedicated migration function with the same pattern:

```python
def migrate_<table>(sqlite_conn, postgres_conn, dry_run=False) -> int:
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT ... FROM <table>")
    rows = cursor.fetchall()

    if dry_run:
        logger.info("[DRY RUN] Would migrate %s <table>", len(rows))
        return len(rows)

    for row in rows:
        postgres_conn.execute("""
            INSERT INTO <table> (..., ...)
            VALUES (%s, %s, ...)
            ON CONFLICT (id) DO NOTHING
        """, (...))
    postgres_conn.commit()
    return len(rows)
```

### `migrate_tenants()`

Migrates: `id`, `name`, `created_at`, `updated_at`

### `migrate_users()`

Migrates: `id`, `tenant_id`, `email`, `name`, `created_at`, `updated_at`

**Note**: The SQLite schema includes a `name` column that doesn't exist in the backend's `User` model. This is legacy schema compatibility.

### `migrate_api_keys()`

Migrates: `id`, `tenant_id`, `user_id`, `key_hash`, `name`, `created_at`, `updated_at`

**Note**: The SQLite schema includes `user_id` which doesn't exist in the backend's `APIKey` model. Legacy compatibility.

### `migrate_agents()`

Migrates: `id`, `tenant_id`, `name`, `config`, `is_active`, `created_at`, `updated_at`

### `migrate_tools()`

Migrates: `id`, `tenant_id`, `name`, `description`, `source`, `parameters`, `is_active`, `external_dependencies`, `tool_dependencies`, `version`, `created_at`, `updated_at`

### `migrate_sessions()`

Migrates the full `sessions` schema:
```
id, tenant_id, user_id, name, agent_id, agent_config,
summary_md, full_context_md, has_summary, summary_updated_at,
parent_session_id, lineage_depth, is_active, created_at, updated_at
```

**Incremental support**:
```python
def migrate_sessions(..., since: Optional[datetime] = None) -> int:
    if since:
        cursor.execute("SELECT ... FROM sessions WHERE updated_at > %s", (since,))
```

SQLite uses `?` placeholders, but the script uses `%s` for the `since` parameter. This appears to be a bug — `%s` is psycopg2's placeholder, not sqlite3's. The SQLite query should use `?`.

### `migrate_messages()`

Migrates: `id`, `session_id`, `turn_index`, `role`, `content`, `message_metadata`, `created_at`, `updated_at`

Also supports `since` filtering on `created_at`.

Same placeholder issue: uses `%s` in SQLite query instead of `?`.

---

## Validation

### `validate_migration(sqlite_conn, postgres_conn) -> dict[str, bool]`

```python
def validate_migration(sqlite_conn, postgres_conn) -> dict[str, bool]:
    sqlite_counts = get_table_counts(sqlite_conn)
    postgres_cursor = postgres_conn.cursor()

    for table in sqlite_counts.keys():
        safe_table = validate_table_name(table)
        postgres_cursor.execute(f"SELECT COUNT(*) FROM {safe_table}")
        postgres_count = postgres_cursor.fetchone()[0]
        results[table] = sqlite_counts[table] == postgres_count
```

Compares row counts per table. Returns `True` for each table where counts match.

**Limitations**:
- Only checks row counts, not data integrity
- Does not verify foreign key constraints
- Does not check for data corruption

---

## Rollback

### `rollback_migration(postgres_conn)`

```python
def rollback_migration(postgres_conn) -> None:
    cursor = postgres_conn.cursor()
    tables = ["messages", "sessions", "tools", "agents", "api_keys", "users", "tenants"]
    for table in tables:
        cursor.execute(f"TRUNCATE TABLE {table} CASCADE")
```

Truncates all tables in reverse dependency order (children before parents). Uses `CASCADE` to handle foreign key references.

**Warning**: `TRUNCATE` is irreversible. This is a true rollback of the migration, not a transaction rollback.

---

## CLI Usage

```bash
python -m tinycua_backend.migrations.migrate_sqlite_to_postgres \
    --sqlite-path /path/to/sqlite.db \
    --postgres-url postgresql://user:pass@host:5432/tinycua \
    [--dry-run] [--validate] [--rollback] [--since YYYY-MM-DDTHH:MM:SS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--sqlite-path` | Yes | Path to SQLite database file |
| `--postgres-url` | Yes | PostgreSQL connection URL |
| `--dry-run` | No | Show what would be migrated without writing |
| `--validate` | No | Compare row counts after migration |
| `--rollback` | No | Truncate all target tables |
| `--since` | No | Only migrate records updated after this ISO timestamp |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (file not found, connection failed, validation failed, invalid timestamp) |

---

## Migration Order

```
1. tenants      (no dependencies)
2. users        (depends on tenants)
3. api_keys     (depends on tenants, users)
4. agents       (depends on tenants)
5. tools        (depends on tenants)
6. sessions     (depends on tenants, users)
7. messages     (depends on sessions)
```

Tables are migrated in dependency order to satisfy foreign key constraints.

---

## Data Flow

```
SQLite Database
    |
    |--> connect_sqlite()
          |
          |--> migrate_tenants() --------> PostgreSQL
          |--> migrate_users() ----------> PostgreSQL
          |--> migrate_api_keys() -------> PostgreSQL
          |--> migrate_agents() ---------> PostgreSQL
          |--> migrate_tools() ----------> PostgreSQL
          |--> migrate_sessions() -------> PostgreSQL
          |--> migrate_messages() -------> PostgreSQL
          |
          |--> validate_migration() (if --validate)
                |
                |--> Compare row counts
                      |
                      |--> All match? SUCCESS
                      |--> Mismatch? WARNING + exit 1
```

---

## Known Issues

1. **SQLite placeholder bug**: `migrate_sessions()` and `migrate_messages()` use `%s` in SQLite queries. SQLite uses `?` for parameter substitution. This would cause an error when using `--since`.

2. **Schema drift**: The migration includes columns (`users.name`, `api_keys.user_id`) that don't exist in the current backend models. This suggests the SQLite schema may be from an earlier version.

3. **No transaction across tables**: Each table migration commits independently. If the script fails mid-migration, the database will be in a partially migrated state.

4. **UUID format**: SQLite stores UUIDs as strings. PostgreSQL stores them as `UUID` type. psycopg2 handles the conversion automatically.

5. **JSON columns**: SQLite stores JSON as TEXT. PostgreSQL has a native `JSON` type. psycopg2 automatically serializes Python dicts to PostgreSQL JSON.
