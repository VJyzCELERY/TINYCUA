"""Local SQLite storage for sessions, agents, and memory."""

import json
import os
import sqlite3
from datetime import datetime
from typing import Any
from contextlib import contextmanager


CURRENT_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    user_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    summary_md TEXT,
    has_summary INTEGER DEFAULT 0,
    full_context_md TEXT
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    config_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    agent_id TEXT,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_session_id ON memory(session_id);
CREATE INDEX IF NOT EXISTS idx_memory_agent_id ON memory(agent_id);
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory(memory_type);

CREATE TABLE IF NOT EXISTS schema_version (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


class LocalStorage:
    """Local SQLite storage for persistent data.

    Provides CRUD operations for sessions, agents, and memory.
    Uses SQLite for local-only storage without external dependencies.

    Usage:
        storage = LocalStorage("./data")
        storage.save_session("session-1", "My Session")
    """

    def __init__(self, data_dir: str = "./data"):
        """Initialize local storage.

        Args:
            data_dir: Directory to store SQLite database
        """
        self.data_dir = data_dir
        self.db_path = os.path.join(data_dir, "tinycua.db")
        self._ensure_directory()
        self._init_database()

    def _ensure_directory(self) -> None:
        """Ensure data directory exists."""
        os.makedirs(self.data_dir, exist_ok=True)

    def _init_database(self) -> None:
        """Initialize database with schema."""
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            conn.commit()
        self._set_schema_version(SCHEMA_VERSION)

    def _set_schema_version(self, version: str) -> None:
        """Set the schema version in the database."""
        with self._connect() as conn:
            now = datetime.utcnow().isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, now),
            )
            conn.commit()

    def get_schema_version(self) -> str | None:
        """Get the current schema version.

        Returns:
            Schema version string or None if not set
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return row["version"]
            return None

    def migrate(self) -> dict[str, Any]:
        """Run database migrations if needed.

        This method checks the current schema version and applies
        any necessary migrations to bring the database up to date.

        Returns:
            Dictionary with migration status
        """
        current = self.get_schema_version()
        target = SCHEMA_VERSION

        if current == target:
            return {"status": "current", "current": current, "target": target}

        migrations = self._get_migrations(current, target)
        applied = []

        with self._connect() as conn:
            for migration_version, sql in migrations:
                if sql:
                    conn.executescript(sql)
                    conn.commit()
                now = datetime.utcnow().isoformat()
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (migration_version, now),
                )
                conn.commit()
                applied.append(migration_version)

        return {
            "status": "migrated",
            "current": current,
            "target": target,
            "applied": applied,
        }

    def _get_migrations(self, from_version: str | None, to_version: str) -> list[tuple[str, str]]:
        """Get list of migrations to apply.

        Args:
            from_version: Current schema version
            to_version: Target schema version

        Returns:
            List of (version, sql) tuples
        """
        migrations = []

        if from_version is None:
            migrations.append((to_version, ""))
            return migrations

        return migrations

    @contextmanager
    def _connect(self):
        """Get database connection context manager.

        Yields:
            sqlite3.Connection instance
        """
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def _row_to_dict(self, row: sqlite3.Row, columns: list[str]) -> dict[str, Any]:
        """Convert SQL row to dictionary.

        Args:
            row: SQL row tuple
            columns: Column names

        Returns:
            Dictionary representation
        """
        result = {k: v for k, v in zip(columns, row)}
        for key, value in result.items():
            if key.endswith("_json") and value:
                try:
                    result[key] = json.loads(value)
                except json.JSONDecodeError:
                    pass
            elif key.endswith("_at") and value:
                try:
                    result[key] = datetime.fromisoformat(value)
                except ValueError:
                    pass
            elif key in ("has_summary",) and value is not None:
                result[key] = bool(value)
        return result

    def save_session(
        self,
        session_id: str,
        name: str,
        user_id: str | None = None,
        summary_md: str | None = None,
        has_summary: bool = False,
        full_context_md: str | None = None,
    ) -> dict[str, Any]:
        """Save or update a session.

        Args:
            session_id: Session ID
            name: Session name
            user_id: Optional user ID
            summary_md: Optional summary markdown
            has_summary: Whether session has summary
            full_context_md: Optional full context markdown

        Returns:
            Saved session dictionary
        """
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO sessions
                (id, name, user_id, created_at, updated_at, summary_md, has_summary, full_context_md)
                VALUES (?, ?, ?, COALESCE((SELECT created_at FROM sessions WHERE id = ?), ?), ?, ?, ?, ?)""",
                (
                    session_id,
                    name,
                    user_id,
                    session_id,
                    now,
                    now,
                    summary_md,
                    1 if has_summary else 0,
                    full_context_md,
                ),
            )
            conn.commit()
        return self.load_session(session_id)

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        """Load a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session dictionary or None if not found
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            )
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return self._row_to_dict(row, columns)
            return None

    def list_sessions(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """List all sessions, optionally filtered by user_id.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            List of session dictionaries
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            if user_id:
                cursor = conn.execute(
                    "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC"
                )
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [self._row_to_dict(row, columns) for row in rows]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False if not found
        """
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    def save_agent(
        self,
        agent_id: str,
        name: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Save or update an agent.

        Args:
            agent_id: Agent ID
            name: Agent name
            config: Agent configuration dictionary

        Returns:
            Saved agent dictionary
        """
        now = datetime.utcnow().isoformat()
        config_json = json.dumps(config)
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO agents
                (id, name, config_json, created_at, updated_at)
                VALUES (?, ?, ?, COALESCE((SELECT created_at FROM agents WHERE id = ?), ?), ?)""",
                (agent_id, name, config_json, agent_id, now, now),
            )
            conn.commit()
        return self.load_agent(agent_id)

    def load_agent(self, agent_id: str) -> dict[str, Any] | None:
        """Load an agent by ID.

        Args:
            agent_id: Agent ID

        Returns:
            Agent dictionary or None if not found
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return self._row_to_dict(row, columns)
            return None

    def list_agents(self) -> list[dict[str, Any]]:
        """List all agents.

        Returns:
            List of agent dictionaries
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM agents ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [self._row_to_dict(row, columns) for row in rows]

    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent.

        Args:
            agent_id: Agent ID

        Returns:
            True if deleted, False if not found
        """
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            conn.commit()
            return cursor.rowcount > 0

    def save_memory(
        self,
        memory_id: str,
        memory_type: str,
        content: str,
        session_id: str | None = None,
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Save or update memory.

        Args:
            memory_id: Memory ID
            memory_type: Type of memory (short_term, long_term, etc.)
            content: Memory content
            session_id: Optional session ID
            agent_id: Optional agent ID
            metadata: Optional metadata dictionary

        Returns:
            Saved memory dictionary
        """
        now = datetime.utcnow().isoformat()
        metadata_json = json.dumps(metadata) if metadata else None
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO memory
                (id, session_id, agent_id, memory_type, content, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (memory_id, session_id, agent_id, memory_type, content, now, metadata_json),
            )
            conn.commit()
        return self.load_memory(memory_id)

    def load_memory(self, memory_id: str) -> dict[str, Any] | None:
        """Load memory by ID.

        Args:
            memory_id: Memory ID

        Returns:
            Memory dictionary or None if not found
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM memory WHERE id = ?", (memory_id,))
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return self._row_to_dict(row, columns)
            return None

    def list_memory(
        self,
        session_id: str | None = None,
        agent_id: str | None = None,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List memory entries with optional filters.

        Args:
            session_id: Optional session ID to filter by
            agent_id: Optional agent ID to filter by
            memory_type: Optional memory type to filter by

        Returns:
            List of memory dictionaries
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM memory WHERE 1=1"
            params = []
            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)
            if agent_id:
                query += " AND agent_id = ?"
                params.append(agent_id)
            if memory_type:
                query += " AND memory_type = ?"
                params.append(memory_type)
            query += " ORDER BY created_at DESC"
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [self._row_to_dict(row, columns) for row in rows]

    def delete_memory(self, memory_id: str) -> bool:
        """Delete memory.

        Args:
            memory_id: Memory ID

        Returns:
            True if deleted, False if not found
        """
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM memory WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0

    def export_all(self) -> dict[str, Any]:
        """Export all data from the database.

        Returns:
            Dictionary containing all sessions, agents, and memory
        """
        return {
            "sessions": self.list_sessions(),
            "agents": self.list_agents(),
            "memory": self.list_memory(),
        }

    def import_data(
        self,
        data: dict[str, Any],
        mode: str = "merge",
    ) -> dict[str, Any]:
        """Import data into the database.

        Args:
            data: Dictionary with sessions, agents, and memory keys
            mode: 'merge' to add to existing, 'replace' to clear first

        Returns:
            Summary of imported data
        """
        if mode == "replace":
            with self._connect() as conn:
                conn.execute("DELETE FROM memory")
                conn.execute("DELETE FROM sessions")
                conn.execute("DELETE FROM agents")
                conn.commit()

        imported = {"sessions": 0, "agents": 0, "memory": 0}

        for session in data.get("sessions", []):
            self.save_session(
                session_id=session["id"],
                name=session.get("name", ""),
                user_id=session.get("user_id"),
                summary_md=session.get("summary_md"),
                has_summary=session.get("has_summary", False),
                full_context_md=session.get("full_context_md"),
            )
            imported["sessions"] += 1

        for agent in data.get("agents", []):
            self.save_agent(
                agent_id=agent["id"],
                name=agent.get("name", ""),
                config=agent.get("config_json", {}),
            )
            imported["agents"] += 1

        for memory in data.get("memory", []):
            self.save_memory(
                memory_id=memory["id"],
                memory_type=memory.get("memory_type", "short_term"),
                content=memory.get("content", ""),
                session_id=memory.get("session_id"),
                agent_id=memory.get("agent_id"),
                metadata=memory.get("metadata_json"),
            )
            imported["memory"] += 1

        return imported


__all__ = ["LocalStorage", "SCHEMA", "CURRENT_VERSION", "SCHEMA_VERSION"]
