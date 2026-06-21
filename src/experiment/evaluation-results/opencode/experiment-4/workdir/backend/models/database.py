import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('notion.db')
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
    
    def _create_tables(self):
        cursor = self.conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                avatar_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Pages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pages (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                title TEXT,
                icon_data TEXT,
                cover_image_url TEXT,
                properties JSONB DEFAULT '{}',
                created_by TEXT REFERENCES users(id),
                is_favorite BOOLEAN DEFAULT 0,
                archived BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Blocks table - each block can be paragraph, heading, bullet list, etc.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blocks (
                id TEXT PRIMARY KEY,
                page_id TEXT REFERENCES pages(id) ON DELETE CASCADE,
                type TEXT NOT NULL DEFAULT 'text',
                text_content TEXT,
                color TEXT DEFAULT 'default',
                is_checked BOOLEAN DEFAULT 0,
                children JSONB DEFAULT '[]'
            )
        ''')
        
        # Comments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id TEXT PRIMARY KEY,
                page_id TEXT REFERENCES pages(id) ON DELETE CASCADE,
                user_id TEXT REFERENCES users(id),
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()

    def get_page(self, page_id: str):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM pages WHERE id = ?', (page_id,))
        return cursor.fetchone() if not cursor.description else None
    
    def create_page(
        self, 
        parent_id: Optional[str],
        title: str, 
        properties: Dict = {},
        created_by: str = 'default'
    ):
        page_id = f"page_{datetime.now().timestamp()}_{parent_id}" if not parent_id else None
        
        cursor = self.conn.cursor()
        if parent_id:
            cursor.execute('''
                INSERT INTO pages (id, parent_id, title, properties, created_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (page_id, parent_id, title, str(properties), created_by))
        else:
            cursor.execute('''
                INSERT INTO pages (id, title, properties, created_by)
                VALUES (?, ?, ?, ?)
            ''', (page_id, title, str(properties), created_by))
        
        self.conn.commit()
        return page_id
    
    def get_page_blocks(self, page_id: str):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM blocks WHERE page_id = ?', (page_id,))
        return [dict(row) for row in cursor.fetchall()] if not cursor.description else []
    
    def add_block(
        self, 
        page_id: str, 
        block_type: str, 
        text_content: Optional[str] = None,
        color: str = 'default',
        is_checked: bool = False,
        children: List[Dict] = []
    ):
        cursor = self.conn.cursor()
        
        if not page_id or page_id.startswith('page_'):
            # Create new page first
            import uuid
            page_id = str(uuid.uuid4())[:8]
            
            cursor.execute('''
                INSERT INTO pages (id, title) VALUES (?, ?)
            ''', (page_id, 'Untitled'))
        
        block_id = f"block_{datetime.now().timestamp()}_" + str(len(self.get_page_blocks(page_id)))
        
        cursor.execute('''
            INSERT INTO blocks (id, page_id, type, text_content, color, is_checked, children)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (block_id, page_id, block_type, text_content or '', color, is_checked, str(children)))
        
        self.conn.commit()
        return block_id
    
    def get_comments(self, page_id: str):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT c.*, u.name as user_name 
            FROM comments c
            LEFT JOIN users u ON c.user_id = u.id
            WHERE c.page_id = ?
            ORDER BY c.created_at DESC
        ''', (page_id,))
        return [dict(row) for row in cursor.fetchall()] if not cursor.description else []

    def add_comment(self, page_id: str, content: str):
        import uuid
        comment_id = f"comment_{datetime.now().timestamp()}_" + str(uuid.uuid4()[:8])
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO comments (id, page_id, user_id, content)
            VALUES (?, ?, 'default', ?)
        ''', (comment_id, page_id, content))
        
        self.conn.commit()
        return comment_id

    def get_user(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', ('default',))
        return dict(cursor.fetchone()) if not cursor.description else None
    
    def close(self):
        if hasattr(self, 'conn'):
            self.conn.close()

# Global database instance
db = Database()
