"""
Database Initialization Script
Run this once to create/reset the database.
The app will auto-create tables on startup, but you can use this for testing.
"""
import sqlite3
import os

def init_database(db_path='database.db'):
    """Initialize all required database tables."""
    
    # Remove existing database if it exists (for fresh start)
    if os.path.exists(db_path):
        print(f"⚠️  Removing existing {db_path}...")
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        name TEXT DEFAULT 'User',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Pages table
    cursor.execute('''CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        icon TEXT DEFAULT '',
        cover_image BLOB,
        parent_page_id INTEGER REFERENCES pages(page_id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Blocks table
    cursor.execute('''CREATE TABLE IF NOT EXISTS blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_id INTEGER REFERENCES pages(id) ON DELETE CASCADE,
        type TEXT NOT NULL DEFAULT 'text',
        content TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Database tables (Notion databases)
    cursor.execute('''CREATE TABLE IF NOT EXISTS database_tables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        page_id INTEGER REFERENCES pages(page_id),
        title TEXT NOT NULL,
        columns_data JSON DEFAULT '{}',
        rows_data JSON DEFAULT '[]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Database columns table (for schema storage)
    cursor.execute('''CREATE TABLE IF NOT EXISTS database_columns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_id INTEGER REFERENCES pages(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        type TEXT DEFAULT 'text',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    print("✅ Database initialized successfully!")
    return True

if __name__ == '__main__':
    init_database()
