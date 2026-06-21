"""
Notion Clone - Enhanced Flask Backend
Complete implementation with blocks, databases, images, and proper API structure.
Run this file instead of app.py for the full experience!
"""
import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, session
from functools import wraps
import base64
import re

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
            parent_page_id INTEGER REFERENCES pages(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Blocks table (Notion blocks - text, headings, lists, etc.)
        cursor.execute('''CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id INTEGER REFERENCES pages(id) ON DELETE CASCADE,
            type TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            parent_block_id INTEGER REFERENCES blocks(id),  # For nested lists
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    """Get current user from session or request."""
    if 'user_id' in session:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id FROM users WHERE id=?', (session['user_id'],))
        return cursor.fetchone()
    
def require_auth(f):
    """Decorator to protect routes."""
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
        return render_auth_page()

def render_auth_page():
    """Render the login/auth page."""
    from flask import render_template_string
    email = session.get('email', '') or ''
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Notion Clone - Sign In</title>
    <link rel="stylesheet" href="/css/style.css">
    <style>
        body {{ background: #f7f7f5; }}
        .auth-container {{ max-width: 420px; margin: 18vh auto; padding: 32px; background: white; border-radius: 16px; box-shadow: 0 8px 24px rgba(9,10,18,.1); }}
        .auth-container h2 {{ font-size: 26px; margin-bottom: 8px; color: #37352f; }}
        .auth-form {{ display: flex; flex-direction: column; gap: 14px; }}
        input[type="email"], input[type="text"] {{ padding: 14px 16px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 15px; outline: none; transition: all .2s; }}
        input:focus {{ border-color: #ea4c9d; }}
        button {{ background: linear-gradient(135deg, #ea4c9d, #ff7eb6); color: white; padding: 14px 24px; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; transition: transform .2s, box-shadow .2s; }}
        button:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(234,76,157,.4); }}
    </style>
</head>
<body>
<div class="auth-container">
<h2>📝 Notion Clone</h2>
<p style="color: #6b6c6f; margin-bottom: 20px;">Sign in to start creating your workspace.</p>
<form id="login-form" class="auth-form">
    <input type="email" placeholder="Email address" name="email" value="{email}" autofocus required>
    <button type="submit">Continue</button>
</form>
<p style="margin-top: 16px; color: #9a9892; font-size: 13px;">No password needed - it\'s just for you!</p>
</div>
<script src="/js/auth.js"></script>
</body>
</html>'''
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
    
    # Create user if doesn\'t exist
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
    
    # Create initial text block
    create_block(new_page_id, 'h1', title)
    
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
    
    sql = '''INSERT INTO blocks (page_id, type, content, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)'''
    values = (int(page_id), block_type or 'text', content or '')
    if parent_block_id is not None:
        cursor.execute(sql + ' WHERE id > ?', (values[0],))  # Simplified - should use proper ordering
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

@app.route('/api/users/<int:user_id>/pages/<int:page_id>/blocks', methods=['PUT'])
def update_block(user_id, page_id):
    """Update a specific block."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    block_type = data.get('type')
    content = data.get('content', '')
    parent_block_id = data.get('parentBlockId')
    page_title_in_url = request.args.get('pageTitleInUrl') or ''
    
    db = get_db()
    cursor = db.cursor()
    
    # Get existing blocks for this page
    cursor.execute('''SELECT id, type FROM blocks WHERE page_id=?''', (int(page_id),))
    rows = cursor.fetchall()
    return jsonify({
        'pageId': str(int(page_id)),
        'blocks': [dict(r) for r in rows]
    })

@app.route('/api/users/<int:user_id>/pages/<int:page_id>/blocks', methods=['DELETE'])
def delete_block(user_id, page_id):
    """Delete a block."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    block_to_delete = int(data.get('blockId'))
    db = get_db()
    cursor = db.cursor()
    
    # Delete the specific block
    sql = '''DELETE FROM blocks WHERE id=? AND page_id=?'''
    cursor.execute(sql, (block_to_delete, int(page_id)))
    db.commit()
    return jsonify({'deleted': True})

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
    
    # Insert columns into pages as a special "table" page type
    for col_data in columns_data:
        cursor.execute('''INSERT INTO database_columns (page_id, name) VALUES (?, ?)''',
            (str(table_page_id), col_data.get('name')))
    
    return jsonify({
        'pageId': str(int(table_page_id)),
        'userId': str(user_id)
    }), 201

@app.route('/api/users/<int:user_id>/pages/tables/<table_title>', methods=['GET'])
def get_table_schema(user_id, table_title):
    """Get a database table's schema."""
    db = get_db()
    cursor = db.cursor()
    
    # Get columns for this table
    try:
        cursor.execute(
            '''SELECT * FROM pages WHERE id IN (
                SELECT page_id FROM database_tables WHERE user_id=? AND title=?
             )''',
            (user_id, f'📊 {table_title}') if not table_title.startswith('📊') else ()
        )
    except:
        cursor.execute(
            '''SELECT * FROM pages WHERE id IN (
                SELECT page_id FROM database_tables WHERE user_id=? AND title LIKE ?
             )''',
            (user_id, f'%{table_title}%') if not table_title.startswith('📊') else ()
        )
    
    rows = cursor.fetchall()
    columns = []
    for row in rows:
        try:
            columns_data = json.loads(row.get('columns', '{}')) or {}
            columns.extend(columns_data.keys())
        except:
            pass
    return jsonify({'tableId': str(int(rows[0]['id'])), 'columns': list(set(columns))})

@app.route('/api/users/<int:user_id>/pages/tables/<string:page_title_in_url>', methods=['PUT'])
def update_table_content(user_id, page_title_in_url):
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
            (user_id, f'%{page_title_in_url}%') if not page_title_in_url.startswith('📊') else ()
        )
        row = cursor.fetchone()
    except:
        return jsonify({'error': 'Table not found'}), 404
    
    table_page_id = int(row['id'])
    columns_data = json.loads(cursor.execute(
        '''SELECT columns_data FROM database_tables WHERE page_id=?''',
        (table_page_id,)
    ).fetchone()[0]) or {}
    column_names = list(columns_data.keys()) if isinstance(columns_data, dict) else []
    
    for row_data in rows_data:
        try:
            # Create a new entry in database_tables with the data
            cursor.execute(
                '''INSERT INTO database_tables (user_id, title, columns_data)
                 VALUES (?, ?, ?)''',
                (user_id, f'📊 {page_title_in_url}', json.dumps(row_data))
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
