"""
Notion Clone - Flask Backend
Complete implementation with blocks, databases, images, and proper API structure.
This is the main application entry point. Run this file to start!
"""
import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, session
from functools import wraps
import base64

app = Flask(__name__, static_folder='../frontend/public', static_url_path='')
CORS(app)
app.secret_key = os.urandom(24)  # For session tokens

# Configuration
SESSION_TIMEOUT = 3600  # 1 hour in seconds
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

# Database setup
def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with all required tables."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Users table - authentication and profile
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT DEFAULT 'User',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Pages table (Notion-style pages)
        cursor.execute('''CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            icon TEXT DEFAULT '',
            cover_image BLOB,  # Store image as binary
            parent_page_id INTEGER REFERENCES pages(page_id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Blocks table (Notion blocks - text, headings, lists, etc.)
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
            page_id INTEGER REFERENCES pages(id),  # Link to parent page
            title TEXT NOT NULL,
            columns_data JSON DEFAULT '{}',
            rows_data JSON DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        db.commit()
        print("✓ Database initialized successfully!")
    return True

# Initialize on startup
init_db()

# ============== Authentication Middleware ==============
def get_user_from_session():
    """Get current user from session."""
    if 'user_id' in session:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id FROM users WHERE id=?', (session['user_id'],))
        return cursor.fetchone()

# Decorator for protected routes
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        user = get_user_from_session()
        if not user:
            return jsonify({'error': 'Invalid session'}), 401
        request.user = user
        return f(*args, **kwargs)
    return decorated

# ============== API ENDPOINTS ==============

@app.route('/')
def index():
    """Serve the main page."""
    if 'user_id' in session:
        # User is logged in - show app
        user = get_user_from_session()
        return send_from_directory('../frontend/public', 'index.html')
    else:
        # Show auth screen
        email = session.get('email', '') or ''
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Notion Clone - Sign In</title>
    <link rel="stylesheet" href="/css/style_enhanced.css">
</head>
<body>
<div style="display:flex;align-items:center;justify-content:center;height:100vh;background:#f7f7f5;padding-top:24px;">
  <div class="auth-box">
    <h2>📝 Notion Clone</h2>
    <p style="color:#6b6c6f;margin-bottom:20px;">Sign in to start creating your workspace.</p>
    <form id="login-form" class="auth-form">
      <input type="email" placeholder="Email address" name="email" value="{email}" autofocus required style="padding:14px 16px;border:2px solid #e0e0e0;border-radius:8px;font-size:15px;outline:none;transition:border-color .2s;">    <button type="submit" class="btn-primary">Continue</button>
    </form>
    <p style="margin-top:16px;color:#9a9892;font-size:13px;">No password needed - it's just for you!</p>
  </div>
</div>
<script src="/js/auth.js"></script>
</body></html>'''
        return html

@app.route('/api/login', methods=['POST'])
def login():
    """Simple email-based authentication."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    email = data.get('email', '').strip().lower()
    name = data.get('name') or f'User {email}'
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Create user if doesn't exist
    try:
        cursor.execute(
            'INSERT INTO users (email, name) VALUES (?, ?)',
            (email, name)
        )
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # User exists - get their ID
        cursor.execute('SELECT id FROM users WHERE email=?', (email,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'User not found'}), 404
        user_id = result['id']
    
    # Set session tokens
    session.permanent = True
    app.config['PERMANENT_SESSION_LIFETIME'] = SESSION_TIMEOUT
    session['user_id'] = user_id
    session['email'] = email
    session['name'] = name
    
    return jsonify({
        'success': True,
        'userId': str(user_id),  # Return as string for frontend compatibility
        'email': email,
        'name': name
    })

@app.route('/api/users/<int:user_id>/pages', methods=['GET'])
def get_pages(user_id):
    """Get all pages (root level) for a user."""
    db = get_db()
    cursor = db.cursor()
    
    # Get root pages only
    cursor.execute('''SELECT id, title, icon, cover_image,
                   created_at, updated_at,
                   parent_page_id,
                   (SELECT COUNT(*) FROM blocks WHERE page_id = p.id) as block_count
                    FROM pages p
                    WHERE user_id = ? AND parent_page_id IS NULL
                    ORDER BY updated_at DESC''', 
            (user_id,))
    rows = cursor.fetchall()
    return jsonify({
        'userId': str(user_id),
        'pages': [dict(row) for row in rows]
    })

@app.route('/api/users/<int:user_id>/pages', methods=['POST'])
def create_page(user_id):
    """Create a new page."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    title = data.get('title') or 'Untitled'
    icon = data.get('icon', '')
    cover_image_data = data.get('coverImage')  # Base64 encoded image if any
    parent_page_id = data.get('parentPageId')
    
    db = get_db()
    cursor = db.cursor()
    
    try:
        page_id = int(parent_page_id) if parent_page_id else None
        
        # Insert new page (or use existing id for nested pages)
        sql = '''INSERT INTO pages (
title, icon, cover_image,
user_id, created_at, updated_at)
VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'''
        values = (title, icon or '', None if not cover_image_data else base64.b64decode(cover_image_data), user_id)
        cursor.execute(sql, values)
        db.commit()
        new_page_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # Use existing page ID
        cursor.execute('SELECT id FROM pages WHERE parent_page_id=? AND title=?', (parent_page_id or '', title))
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Page not found'}), 404
        new_page_id = int(result['id'])
    
    # Create initial text block with page title as h1
    create_block(new_page_id, 'h2', f"#{title}")
    
    return jsonify({
        'pageId': str(new_page_id),
        'userId': str(user_id)
    }), 201

@app.route('/api/users/<int:user_id>/pages/<int:page_id>', methods=['GET'])
def get_page_content(user_id, page_id):
    """Get a specific page and its blocks."""
    db = get_db()
    cursor = db.cursor()
    
    # Get page info
    cursor.execute('SELECT id, title, icon, cover_image FROM pages WHERE user_id=? AND id=?', (user_id, page_id))
    row = cursor.fetchone()
    if not row:
        return jsonify({'error': 'Page not found'}), 404
    
    # Get blocks in order (oldest first)
    cursor.execute(
        '''SELECT type, content FROM blocks WHERE page_id=? ORDER BY id ASC''',
        (page_id,) ,)
    blocks = cursor.fetchall()
    
    return jsonify({
        'id': str(page_id),
        'title': row['title'],
        'icon': row['icon'] or '',
        'coverImage': base64.b64encode(row['cover_image'] or b'').decode() if row['cover_image'] else None,
        'blocks': [dict(b) for b in blocks]
    })

@app.route('/api/users/<int:user_id>/pages/<int:page_id>', methods=['PUT'])
def update_page(user_id, page_id):
    """Update a page's metadata."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    title = data.get('title')
    icon = data.get('icon', '')
    cover_image_data = data.get('coverImage')
    page_title_in_url = request.args.get('pageTitleInUrl') or ''
    
    db = get_db()
    cursor = db.cursor()
    
    # Get existing page
    cursor.execute('SELECT id FROM pages WHERE user_id=? AND title=?', (user_id, page_title_in_url))
    row = cursor.fetchone()
    if not row:
        return jsonify({'error': 'Page not found'}), 404
    
    # Update fields
    sql = '''UPDATE pages SET title=?, icon=? WHERE id=?'''
    values = (title or '', icon or None, int(row['id']))
    cursor.execute(sql, values)
    db.commit()
    
    if cover_image_data:
        try:
            cursor.execute('''UPDATE pages SET cover_image=? WHERE id=?''',
                (base64.b64decode(cover_image_data), int(row['id'])))
            db.commit()
        except Exception as e:
            print(f"Cover image update error: {e}")
    
    return jsonify({
        'pageId': str(int(row['id']))
    })

@app.route('/api/users/<int:user_id>/pages/<int:page_id>/blocks', methods=['POST'])
def create_block(user_id, page_id):
    """Add a block to a page."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    block_type = data.get('type') or 'text'
    content = data.get('content', '')
    parent_block_id = data.get('parentBlockId')
    
    db = get_db()
    cursor = db.cursor()
    
    sql = '''INSERT INTO blocks (page_id, type, content) VALUES (?, ?, ?)'''
    values = (int(page_id), block_type or 'text', content)
    if parent_block_id is not None:
        # For nested lists - simplified approach
        cursor.execute(sql + ' WHERE id > ?', (values[0],))
    else:
        cursor.execute(sql, values)
    
    db.commit()
    new_block_id = cursor.lastrowid
    return jsonify({
        'blockId': str(new_block_id),
        'pageId': str(int(page_id)),
        'type': block_type,
        'content': content
    }), 201

@app.route('/api/users/<int:user_id>/pages/<int:page_id>', methods=['PUT'])
def update_page_blocks(user_id, page_id):
    """Replace all blocks in a page."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Get existing blocks for this page
    db = get_db()
    cursor = db.cursor()
    
    # Clear all blocks first
    sql_delete = '''DELETE FROM blocks WHERE page_id=?'''
    cursor.execute(sql_delete, (int(page_id),))
    db.commit()
    
    # Add new blocks from request
    blocks_data = data.get('blocks', [])
    for block in blocks_data:
        sql_insert = '''INSERT INTO blocks (page_id, type, content) VALUES (?, ?, ?)'''
        values = (int(page_id), block['type'], block.get('content', ''))
        cursor.execute(sql_insert, values)
    
    db.commit()
    return jsonify({
        'updated': True,
        'pageId': str(int(page_id))
    })

@app.route('/api/users/<int:user_id>/pages/tables', methods=['POST'])
def create_table(user_id):
    """Create a database table."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    title = data.get('title') or 'Untitled'
    columns_data = data.get('columns', [])
    page_title_in_url = request.args.get('pageTitleInUrl') or ''
    
    db = get_db()
    cursor = db.cursor()
    
    # Create table entry
    try:
        cursor.execute(
            '''INSERT INTO database_tables (user_id, title, columns_data)
             VALUES (?, ?, ?)''',
            (user_id, title or 'Untitled Table', json.dumps(columns_data))
        )
        db.commit()
        table_page_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # Use existing page ID if exists
        cursor.execute('''SELECT id FROM database_tables WHERE user_id=? AND title=?''', (user_id, title or 'Untitled'))
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Table not found'}), 404
        table_page_id = int(row['id'])
    
    # Insert columns into pages as a special "table" page type (for compatibility)
    for col_data in columns_data:
        cursor.execute('''INSERT INTO database_columns (page_id, name) VALUES (?, ?)''',
            (str(table_page_id), col_data.get('name')))
    
    return jsonify({
        'pageId': str(int(table_page_id)),
        'userId': str(user_id)
    }), 201

@app.route('/api/users/<int:user_id>/pages/tables/<string:table_title>', methods=['PUT'])
def update_table_content(user_id, table_title):
    """Add rows to a database table."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    rows_data = data.get('rows', [])
    db = get_db()
    cursor = db.cursor()
    
    # Find the table page ID and add rows to database_tables
    try:
        cursor.execute(
            '''SELECT id FROM pages WHERE user_id=? AND title LIKE ?''',
            (user_id, f'%{table_title}%') if not str(table_title).startswith('📊') else ()
        )
        row = cursor.fetchone()
    except:
        return jsonify({'error': 'Table not found'}), 404
    
    table_page_id = int(row['id'])
    columns_data_json = json.loads(cursor.execute(
        '''SELECT columns_data FROM database_tables WHERE page_id=?''',
        (table_page_id,)
    ).fetchone()[0]) or {}
    column_names = list(columns_data_json.keys()) if isinstance(columns_data_json, dict) else []
    
    for row_data in rows_data:
        try:
            # Create a new entry in database_tables with the data
            cursor.execute(
                '''INSERT INTO database_tables (user_id, title, columns_data)
                 VALUES (?, ?, ?)''',
                (user_id, f'📊 {table_title}', json.dumps(row_data))
            )
        except sqlite3.IntegrityError:
            pass  # Skip duplicates
    
    db.commit()
    return jsonify({'updated': True})

# ============== Utility Functions ==============
def create_block(page_id, block_type, content=''):
    """Helper function to create a new block."""
    db = get_db()
    cursor = db.cursor()
    sql = '''INSERT INTO blocks (page_id, type, content) VALUES (?, ?, ?)'''
    cursor.execute(sql, (int(page_id), block_type or 'text', content))
    return True

if __name__ == '__main__':
    print("🚀 Starting Notion Clone...")
    app.run(debug=True, host='0.0.0.0', port=5000)
