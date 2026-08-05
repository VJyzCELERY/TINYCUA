-- SQLite Schema for Notion-like Block Persistence
-- Supports selection-based editing/deletion, persistence across reloads/restarts

-- Main blocks table with primary key supporting efficient selection-based operations
CREATE TABLE IF NOT EXISTS blocks (
    id TEXT PRIMARY KEY,        -- Unique block identifier (UUID recommended for selection)
    content TEXT NOT NULL,      -- Block text content
    display_order INTEGER NOT NULL,     -- Display order for block sorting
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Optional metadata fields
    type TEXT DEFAULT 'text',   -- Block type (text, heading, bullet, etc.)
    parent_id TEXT,             -- Optional parent for nested blocks
    is_deleted BOOLEAN DEFAULT FALSE,
    deletion_order INTEGER,     -- Order among deleted blocks for reordering
    metadata TEXT               -- JSON blob for additional properties
);

-- Index on order for efficient block ordering queries
CREATE INDEX IF NOT EXISTS idx_blocks_order ON blocks(order);

-- Index on parent_id for nested block lookups
CREATE INDEX IF NOT EXISTS idx_blocks_parent_id ON blocks(parent_id);

-- Schema migration notes:
-- 1. Initial schema creation (above) - creates all tables and indexes
-- 2. Data persistence: SQLite handles persistence automatically across restarts
-- 3. Migration strategy for schema evolution:
--    a. Use ALTER TABLE for adding new columns (SQLite supports this for additions)
--    b. For column modifications, consider CREATE TABLE AS SELECT pattern
--    c. Indexes can be added with CREATE INDEX IF NOT EXISTS
--    d. Schema versioning recommended in metadata column for tracking changes
-- 4. Data persistence guarantees:
--    a. SQLite file stores all data on disk automatically
--    b. No daemonization needed - data persists on disk
--    c. Use WAL mode for better concurrency: PRAGMA journal_mode = 'wal'
--    d. Schema changes are backward compatible with existing data
