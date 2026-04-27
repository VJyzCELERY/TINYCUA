# Local Storage Guide

## Overview

TINYCUA uses SQLite for local data persistence, enabling offline functionality and session history.

## Storage Location

All local data is stored in:
```
~/.tinycua/data.db
```

The storage directory is automatically created on first run:
```
~/.tinycua/
```

## Database Schema

The database contains three main tables:

### sessions table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Session unique identifier |
| tenant_id | TEXT | Tenant identifier (nullable) |
| user_id | TEXT | User identifier (nullable) |
| agent_id | TEXT | Agent identifier (nullable) |
| name | TEXT | Session name |
| created_at | DATETIME | Creation timestamp |
| updated_at | DATETIME | Last update timestamp |

### messages table
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Message unique identifier |
| session_id | UUID (FK) | Parent session ID |
| role | TEXT | Message role (user/assistant/tool/metadata) |
| content | TEXT | Message content |
| turn_index | INTEGER | Message order index |
| created_at | DATETIME | Creation timestamp |

### memory table
| Column | Type | Description |
|--------|------|-------------|
| key | TEXT (PK) | Memory key |
| value | TEXT | JSON-encoded memory value |
| updated_at | DATETIME | Last update timestamp |

## Offline Mode

TINYCUA automatically detects network availability and operates in offline mode when no connection is available.

### Offline Mode Detection

The system checks network availability by:
1. Attempting to reach the configured backend
2. Falling back to local-only mode if unreachable

### Offline Mode Behavior

When offline:
- All session and message operations work normally using local SQLite storage
- Agent execution uses local models only (if configured)
- Status bar displays "LOCAL MODE" indicator
- All data persists locally and syncs when connection restored

### Status Indicator

The TUI status bar shows:
- **Online**: Connected to backend, full functionality
- **LOCAL MODE**: Offline, local storage only

## Usage

### Initializing Storage

Storage is automatically initialized when the TUI starts:

```python
from tinycua.storage import LocalStorageManager

manager = LocalStorageManager.get_instance()
manager.initialize()
```

### Using Session Store

```python
from tinycua.storage import LocalStorageManager

manager = LocalStorageManager.get_instance()
store = manager.get_store()

session = store.create_session(name="My Session")
messages = store.get_messages(session.id)
```

### Using Memory Store

```python
from tinycua.storage import LocalMemoryStore

memory = LocalMemoryStore()
memory.set("user_preferences", {"theme": "dark"})
prefs = memory.get("user_preferences")
```

## Backup

To backup the database:

```python
from tinycua.storage import LocalStorageManager

manager = LocalStorageManager.get_instance()
manager.backup(Path("~/.tinycua/data.db.backup"))
```

Or manually:
```bash
cp ~/.tinycua/data.db ~/.tinycua/data.db.backup
```