#!/usr/bin/env python3
"""FastAPI backend for Notion-like web app with SQLite storage."""

import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Configuration
PORT = int(os.environ.get("PORT", 8765))
DB_PATH = Path("/workspace/notion.db")

# Ensure database file exists for persistence
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
if not DB_PATH.exists():
    DB_PATH.touch()

app = FastAPI(title="Notion-like Block API", docs_url="/docs")


class BlockCreate(BaseModel):
    """Request model for creating/updating a block."""
    content: str
    type: str = "text"  # text, heading, bullet, etc.


# Database functions using synchronous SQLite driver
def init_db():
    """Initialize database schema."""
    import sqlite3
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            display_order INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            type TEXT DEFAULT 'text',
            parent_id TEXT,
            is_deleted BOOLEAN DEFAULT FALSE,
            deletion_order INTEGER,
            metadata TEXT
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocks_display_order ON blocks(display_order)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blocks_parent_id ON blocks(parent_id)")
    
    # Enable foreign keys and WAL mode for better concurrency
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    
    conn.commit()
    conn.close()


# Initialize database on startup
init_db()


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/blocks")
def list_blocks(limit: int = 100, order_by: str = "order"):
    """List all blocks with their order."""
    import sqlite3
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Get max display_order for new blocks
    cursor.execute("SELECT MAX(display_order) FROM blocks WHERE is_deleted = FALSE")
    max_order = cursor.fetchone()[0] or 0
    next_order = max_order + 1
    
    cursor.execute("""
        SELECT id, content, display_order, type, created_at, updated_at
        FROM blocks
        WHERE is_deleted = FALSE
        ORDER BY display_order ASC
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    
    conn.close()
    
    blocks = []
    for row in rows:
        blocks.append({
            "id": row[0],
            "content": row[1],
            "order": row[2],
            "type": row[3],
            "created_at": row[4],
            "updated_at": row[5]
        })
    
    return {
        "blocks": blocks,
        "next_order": next_order,
        "max_order": max_order,
        "total": len(blocks)
    }


@app.post("/blocks")
def create_block(data: BlockCreate):
    """Create a new block."""
    import sqlite3
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Get next order
    cursor.execute("SELECT MAX(display_order) FROM blocks WHERE is_deleted = FALSE")
    max_order = cursor.fetchone()[0] or 0
    order = max_order + 1
    
    block_id = str(uuid.uuid4())
    
    cursor.execute("""
        INSERT INTO blocks (id, content, display_order, type, created_at, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (block_id, data.content, order, data.type))
    
    conn.commit()
    new_id = cursor.lastrowid
    
    conn.close()
    
    return {
        "id": str(new_id),
        "content": data.content,
        "order": new_id,
        "type": data.type,
        "message": f"Block created with id: {new_id}"
    }


@app.put("/blocks/{block_id}")
def update_block(block_id: str, data: BlockCreate):
    """Update an existing block."""
    import sqlite3
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Get current display_order for this block
    cursor.execute("SELECT display_order FROM blocks WHERE id = ? AND is_deleted = FALSE", (block_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Block not found")
    
    current_order = row[0]
    
    # Update content and type
    cursor.execute("""
        UPDATE blocks
        SET content = ?, type = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND is_deleted = FALSE
    """, (data.content, data.type, block_id))
    
    conn.commit()
    row_count = cursor.rowcount
    
    if row_count == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Block not found or already deleted")
    
    # Re-fetch to return updated display_order
    cursor.execute("SELECT display_order FROM blocks WHERE id = ? AND is_deleted = FALSE", (block_id,))
    updated_order = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "id": block_id,
        "content": data.content,
        "order": updated_order,
        "type": data.type,
        "message": "Block updated successfully"
    }


@app.delete("/blocks/{block_id}")
def delete_block(block_id: str):
    """Soft delete a block."""
    import sqlite3
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Get current display_order for reordering
    cursor.execute("SELECT display_order FROM blocks WHERE id = ? AND is_deleted = FALSE", (block_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Block not found or already deleted")
    
    current_order = row[0]
    
    # Soft delete the block
    cursor.execute("""
        UPDATE blocks
        SET is_deleted = TRUE, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND is_deleted = FALSE
    """, (block_id,))
    
    conn.commit()
    row_count = cursor.rowcount
    
    if row_count == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Block not found or already deleted")
    
    # Get new max order for reordering
    cursor.execute("SELECT MAX(display_order) FROM blocks WHERE is_deleted = FALSE")
    max_order = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return {
        "id": block_id,
        "order": max_order + 1,
        "message": f"Block deleted successfully (new order: {max_order + 1})"
    }


@app.get("/")
def serve_frontend():
    """Serve the frontend HTML file."""
    from pathlib import Path
    html_path = Path("/workspace/index.html")
    if not html_path.exists():
        return JSONResponse(status_code=404, content={"error": "Frontend not found"})
    
    try:
        html_content = html_path.read_text(encoding='utf-8')
        return html_content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    # Ensure database is initialized
    init_db()
    
    print(f"Starting Notion-like app on port {PORT}...")
    print("API documentation available at http://localhost:" + str(PORT) + "/docs")
    print("Frontend available at http://localhost:" + str(PORT) + "/")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
