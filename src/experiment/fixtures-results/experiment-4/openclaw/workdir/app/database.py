import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'blocks.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Blocks table - each block is a line in a page
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id INTEGER NOT NULL,
            content TEXT DEFAULT '',
            order_idx INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE
        )
    ''')
    
    # Pages table - each page is a container for blocks
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT 'Untitled',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()  # Commit after creating tables
    conn.close()

def get_page_or_404(page_id):
    """Helper to fetch a page, returning None if not found."""
    conn = get_connection()
    try:
        page = conn.execute('SELECT * FROM pages WHERE id = ?', (page_id,)).fetchone()
        return page
    finally:
        conn.close()

def get_blocks_for_page(page_id):
    """Get blocks for a page in order."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            'SELECT content, order_idx FROM blocks WHERE page_id = ? ORDER BY order_idx ASC',
            (page_id,)
        )
        return cursor.fetchall()
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized")
