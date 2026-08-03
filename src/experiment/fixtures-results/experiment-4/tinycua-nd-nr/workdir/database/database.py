"""
SQLite database module for Notion-like text blocks.
Provides database schema, initialization, and basic CRUD operations.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

# Database path relative to workspace root
DB_PATH = Path(__file__).parent.parent / "data" / "blocks.db"


def get_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Initialize the database with the text blocks table.
    Creates the table if it doesn't exist, ensuring data persistence across restarts.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create text_blocks table with schema for persisted text blocks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS text_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(content)
        )
    """)
    
    # Create indexes for efficient block retrieval
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_content ON text_blocks(content)
    """)
    
    conn.commit()
    conn.close()


def get_all_blocks():
    """Retrieve all text blocks."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, content, created_at, updated_at FROM text_blocks ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def create_block(content: str):
    """Create a new text block with given content."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO text_blocks (content) VALUES (?)",
            (content,)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # Content already exists
        return None
    finally:
        conn.close()


def get_block(id: int):
    """Retrieve a block by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, content, created_at, updated_at FROM text_blocks WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def update_block(id: int, content: str):
    """Update a block's content."""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    try:
        cursor.execute(
            "UPDATE text_blocks SET content = ?, updated_at = ? WHERE id = ?",
            (content, now, id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_block(id: int):
    """Delete a block by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM text_blocks WHERE id = ?", (id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_all_blocks():
    """Delete all blocks (for testing/reset)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM text_blocks")
    conn.commit()
    conn.close()
    return True
