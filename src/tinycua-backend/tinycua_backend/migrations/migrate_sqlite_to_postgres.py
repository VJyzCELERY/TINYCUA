#!/usr/bin/env python3
r"""Migrate data from SQLite to PostgreSQL.

Supports --dry-run, --validate, and --rollback options.

Usage:
    python -m tinycua_backend.migrations.migrate_sqlite_to_postgres \\
        --sqlite-path /path/to/sqlite.db \\
        --postgres-url postgresql://user:pass@host:5432/tinycua \\
        [--dry-run] [--validate] [--rollback]
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import sqlite3

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

ALLOWED_TABLES = frozenset({"tenants", "users", "api_keys", "agents", "tools", "sessions", "messages"})


def validate_table_name(table: str) -> str:
    """Validate that a table name is in the allowed list.

    Args:
        table: Table name to validate

    Returns:
        The validated table name

    Raises:
        ValueError: If table name is not in ALLOWED_TABLES
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Invalid table name: {table}. Must be one of {ALLOWED_TABLES}")
    return table


def connect_sqlite(path: str) -> sqlite3.Connection:
    """Connect to SQLite database.

    Args:
        path: Path to SQLite database

    Returns:
        SQLite connection
    """
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Get row counts for all tables.

    Args:
        conn: SQLite connection

    Returns:
        Dictionary of table names to row counts
    """
    cursor = conn.cursor()
    tables = list(ALLOWED_TABLES)
    counts = {}
    for table in tables:
        try:
            safe_table = validate_table_name(table)
            cursor.execute(f"SELECT COUNT(*) FROM {safe_table}")
            counts[table] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            counts[table] = 0
    return counts


def migrate_tenants(
    sqlite_conn: sqlite3.Connection,
    postgres_conn,
    dry_run: bool = False,
) -> int:
    """Migrate tenants table.

    Args:
        sqlite_conn: SQLite connection
        postgres_conn: PostgreSQL connection
        dry_run: If True, don't actually migrate

    Returns:
        Number of records migrated
    """
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT id, name, created_at, updated_at FROM tenants")
    rows = cursor.fetchall()

    if dry_run:
        logger.info(f"[DRY RUN] Would migrate {len(rows)} tenants")
        return len(rows)

    for row in rows:
        postgres_conn.execute(
            """
            INSERT INTO tenants (id, name, created_at, updated_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (row["id"], row["name"], row["created_at"], row["updated_at"]),
        )
    postgres_conn.commit()
    logger.info(f"Migrated {len(rows)} tenants")
    return len(rows)


def migrate_users(
    sqlite_conn: sqlite3.Connection,
    postgres_conn,
    dry_run: bool = False,
) -> int:
    """Migrate users table.

    Args:
        sqlite_conn: SQLite connection
        postgres_conn: PostgreSQL connection
        dry_run: If True, don't actually migrate

    Returns:
        Number of records migrated
    """
    cursor = sqlite_conn.cursor()
    cursor.execute(
        "SELECT id, tenant_id, email, name, created_at, updated_at FROM users"
    )
    rows = cursor.fetchall()

    if dry_run:
        logger.info(f"[DRY RUN] Would migrate {len(rows)} users")
        return len(rows)

    for row in rows:
        postgres_conn.execute(
            """
            INSERT INTO users (id, tenant_id, email, name, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                row["id"],
                row["tenant_id"],
                row["email"],
                row["name"],
                row["created_at"],
                row["updated_at"],
            ),
        )
    postgres_conn.commit()
    logger.info(f"Migrated {len(rows)} users")
    return len(rows)


def migrate_api_keys(
    sqlite_conn: sqlite3.Connection,
    postgres_conn,
    dry_run: bool = False,
) -> int:
    """Migrate api_keys table.

    Args:
        sqlite_conn: SQLite connection
        postgres_conn: PostgreSQL connection
        dry_run: If True, don't actually migrate

    Returns:
        Number of records migrated
    """
    cursor = sqlite_conn.cursor()
    cursor.execute(
        "SELECT id, tenant_id, user_id, key_hash, name, created_at, updated_at FROM api_keys"
    )
    rows = cursor.fetchall()

    if dry_run:
        logger.info(f"[DRY RUN] Would migrate {len(rows)} API keys")
        return len(rows)

    for row in rows:
        postgres_conn.execute(
            """
            INSERT INTO api_keys (id, tenant_id, user_id, key_hash, name, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                row["id"],
                row["tenant_id"],
                row["user_id"],
                row["key_hash"],
                row["name"],
                row["created_at"],
                row["updated_at"],
            ),
        )
    postgres_conn.commit()
    logger.info(f"Migrated {len(rows)} API keys")
    return len(rows)


def migrate_agents(
    sqlite_conn: sqlite3.Connection,
    postgres_conn,
    dry_run: bool = False,
) -> int:
    """Migrate agents table.

    Args:
        sqlite_conn: SQLite connection
        postgres_conn: PostgreSQL connection
        dry_run: If True, don't actually migrate

    Returns:
        Number of records migrated
    """
    cursor = sqlite_conn.cursor()
    cursor.execute(
        "SELECT id, tenant_id, name, config, is_active, created_at, updated_at FROM agents"
    )
    rows = cursor.fetchall()

    if dry_run:
        logger.info(f"[DRY RUN] Would migrate {len(rows)} agents")
        return len(rows)

    for row in rows:
        postgres_conn.execute(
            """
            INSERT INTO agents (id, tenant_id, name, config, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                row["id"],
                row["tenant_id"],
                row["name"],
                row["config"],
                row["is_active"],
                row["created_at"],
                row["updated_at"],
            ),
        )
    postgres_conn.commit()
    logger.info(f"Migrated {len(rows)} agents")
    return len(rows)


def migrate_tools(
    sqlite_conn: sqlite3.Connection,
    postgres_conn,
    dry_run: bool = False,
) -> int:
    """Migrate tools table.

    Args:
        sqlite_conn: SQLite connection
        postgres_conn: PostgreSQL connection
        dry_run: If True, don't actually migrate

    Returns:
        Number of records migrated
    """
    cursor = sqlite_conn.cursor()
    cursor.execute(
        """SELECT id, tenant_id, name, description, source, parameters,
           is_active, external_dependencies, tool_dependencies, version,
           created_at, updated_at FROM tools"""
    )
    rows = cursor.fetchall()

    if dry_run:
        logger.info(f"[DRY RUN] Would migrate {len(rows)} tools")
        return len(rows)

    for row in rows:
        postgres_conn.execute(
            """
            INSERT INTO tools (id, tenant_id, name, description, source, parameters,
                              is_active, external_dependencies, tool_dependencies, version,
                              created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                row["id"],
                row["tenant_id"],
                row["name"],
                row["description"],
                row["source"],
                row["parameters"],
                row["is_active"],
                row["external_dependencies"],
                row["tool_dependencies"],
                row["version"],
                row["created_at"],
                row["updated_at"],
            ),
        )
    postgres_conn.commit()
    logger.info(f"Migrated {len(rows)} tools")
    return len(rows)


def migrate_sessions(
    sqlite_conn: sqlite3.Connection,
    postgres_conn,
    dry_run: bool = False,
    since: Optional[datetime] = None,
) -> int:
    """Migrate sessions table.

    Args:
        sqlite_conn: SQLite connection
        postgres_conn: PostgreSQL connection
        dry_run: If True, don't actually migrate
        since: Only migrate sessions updated after this timestamp

    Returns:
        Number of records migrated
    """
    cursor = sqlite_conn.cursor()
    if since:
        cursor.execute(
            """SELECT id, tenant_id, user_id, name, agent_id, agent_config,
                      summary_md, full_context_md, has_summary, summary_updated_at,
                      parent_session_id, lineage_depth, is_active, created_at, updated_at
               FROM sessions WHERE updated_at > %s""",
            (since,),
        )
    else:
        cursor.execute(
            """SELECT id, tenant_id, user_id, name, agent_id, agent_config,
                      summary_md, full_context_md, has_summary, summary_updated_at,
                      parent_session_id, lineage_depth, is_active, created_at, updated_at
               FROM sessions"""
        )
    rows = cursor.fetchall()

    if dry_run:
        logger.info(f"[DRY RUN] Would migrate {len(rows)} sessions")
        return len(rows)

    for row in rows:
        postgres_conn.execute(
            """
            INSERT INTO sessions (id, tenant_id, user_id, name, agent_id, agent_config,
                                  summary_md, full_context_md, has_summary, summary_updated_at,
                                  parent_session_id, lineage_depth, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                row["id"],
                row["tenant_id"],
                row["user_id"],
                row["name"],
                row["agent_id"],
                row["agent_config"],
                row["summary_md"],
                row["full_context_md"],
                row["has_summary"],
                row["summary_updated_at"],
                row["parent_session_id"],
                row["lineage_depth"],
                row["is_active"],
                row["created_at"],
                row["updated_at"],
            ),
        )
    postgres_conn.commit()
    logger.info(f"Migrated {len(rows)} sessions")
    return len(rows)


def migrate_messages(
    sqlite_conn: sqlite3.Connection,
    postgres_conn,
    dry_run: bool = False,
    since: Optional[datetime] = None,
) -> int:
    """Migrate messages table.

    Args:
        sqlite_conn: SQLite connection
        postgres_conn: PostgreSQL connection
        dry_run: If True, don't actually migrate
        since: Only migrate messages created after this timestamp

    Returns:
        Number of records migrated
    """
    cursor = sqlite_conn.cursor()
    if since:
        cursor.execute(
            """SELECT id, session_id, turn_index, role, content, message_metadata,
                      created_at, updated_at FROM messages WHERE created_at > %s""",
            (since,),
        )
    else:
        cursor.execute(
            """SELECT id, session_id, turn_index, role, content, message_metadata,
                      created_at, updated_at FROM messages"""
        )
    rows = cursor.fetchall()

    if dry_run:
        logger.info(f"[DRY RUN] Would migrate {len(rows)} messages")
        return len(rows)

    for row in rows:
        postgres_conn.execute(
            """
            INSERT INTO messages (id, session_id, turn_index, role, content, message_metadata,
                                 created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                row["id"],
                row["session_id"],
                row["turn_index"],
                row["role"],
                row["content"],
                row["message_metadata"],
                row["created_at"],
                row["updated_at"],
            ),
        )
    postgres_conn.commit()
    logger.info(f"Migrated {len(rows)} messages")
    return len(rows)


def validate_migration(
    sqlite_conn: sqlite3.Connection,
    postgres_conn,
) -> dict[str, bool]:
    """Validate that migration was successful.

    Args:
        sqlite_conn: SQLite connection
        postgres_conn: PostgreSQL connection

    Returns:
        Dictionary of validation results
    """
    results = {}

    sqlite_counts = get_table_counts(sqlite_conn)
    postgres_cursor = postgres_conn.cursor()

    for table in sqlite_counts.keys():
        try:
            safe_table = validate_table_name(table)
            postgres_cursor.execute(f"SELECT COUNT(*) FROM {safe_table}")
            postgres_count = postgres_cursor.fetchone()[0]
            results[table] = sqlite_counts[table] == postgres_count
            if not results[table]:
                logger.warning(
                    f"Table {table}: SQLite has {sqlite_counts[table]} rows, "
                    f"PostgreSQL has {postgres_count} rows"
                )
        except Exception as e:
            logger.error(f"Error validating table {table}: {e}")
            results[table] = False

    return results


def rollback_migration(postgres_conn) -> None:
    """Rollback migration by truncating all tables.

    Args:
        postgres_conn: PostgreSQL connection
    """
    cursor = postgres_conn.cursor()
    tables = ["messages", "sessions", "tools", "agents", "api_keys", "users", "tenants"]

    for table in tables:
        try:
            safe_table = validate_table_name(table)
            cursor.execute(f"TRUNCATE TABLE {safe_table} CASCADE")
            logger.info(f"Truncated table {table}")
        except Exception as e:
            logger.error(f"Error truncating table {table}: {e}")

    postgres_conn.commit()
    logger.info("Rollback complete")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate data from SQLite to PostgreSQL"
    )
    parser.add_argument(
        "--sqlite-path",
        required=True,
        help="Path to SQLite database",
    )
    parser.add_argument(
        "--postgres-url",
        required=True,
        help="PostgreSQL connection URL",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually migrating",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate migration after completing",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback the migration (truncate all tables)",
    )
    parser.add_argument(
        "--since",
        type=str,
        help="Only migrate records updated after this timestamp (ISO format)",
    )

    args = parser.parse_args()

    sqlite_path = Path(args.sqlite_path)
    if not sqlite_path.exists():
        logger.error(f"SQLite database not found: {args.sqlite_path}")
        return 1

    sqlite_conn = connect_sqlite(args.sqlite_path)

    try:
        import psycopg2

        postgres_conn = psycopg2.connect(args.postgres_url)
    except ImportError:
        logger.error("psycopg2 is required. Install with: pip install psycopg2-binary")
        return 1
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        return 1

    if args.rollback:
        rollback_migration(postgres_conn)
        return 0

    since = None
    if args.since:
        try:
            since = datetime.fromisoformat(args.since)
        except ValueError:
            logger.error(
                "Invalid timestamp format. Use ISO format: YYYY-MM-DDTHH:MM:SS"
            )
            return 1

    if args.dry_run:
        logger.info("=" * 50)
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info("=" * 50)

    logger.info("Starting migration...")

    migrate_tenants(sqlite_conn, postgres_conn, dry_run=args.dry_run)
    migrate_users(sqlite_conn, postgres_conn, dry_run=args.dry_run)
    migrate_api_keys(sqlite_conn, postgres_conn, dry_run=args.dry_run)
    migrate_agents(sqlite_conn, postgres_conn, dry_run=args.dry_run)
    migrate_tools(sqlite_conn, postgres_conn, dry_run=args.dry_run)
    migrate_sessions(sqlite_conn, postgres_conn, dry_run=args.dry_run, since=since)
    migrate_messages(sqlite_conn, postgres_conn, dry_run=args.dry_run, since=since)

    if args.validate and not args.dry_run:
        logger.info("=" * 50)
        logger.info("Validating migration...")
        logger.info("=" * 50)
        results = validate_migration(sqlite_conn, postgres_conn)
        all_valid = all(results.values())
        if all_valid:
            logger.info("Validation passed: All tables match")
        else:
            logger.warning("Validation failed: Some tables don't match")
            for table, valid in results.items():
                if not valid:
                    logger.warning(f"  - {table}: FAILED")
            return 1
    elif args.validate and args.dry_run:
        logger.warning("Skipping validation in dry-run mode")

    sqlite_conn.close()
    postgres_conn.close()

    logger.info("Migration complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
