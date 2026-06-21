from flask import Flask, jsonify, request
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)
DB_PATH = '/workspace/experiment-4/backend/notion.db'

def get_connection():
    """Get a fresh connection for each operation"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/health', methods=['GET'])
def health():
    conn = get_connection()
    
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM pages WHERE archived=0')
        page_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM blocks')
        block_count = cursor.fetchone()[0]
        
        return jsonify({
            'status': 'healthy',
            'pages_count': page_count,
            'blocks_count': block_count,
            'timestamp': datetime.now().isoformat()
        })
    finally:
        conn.close()

@app.route('/api/pages', methods=['POST'])
def create_page():
    data = request.json
    
    try:
        timestamp = datetime.now().timestamp()
        page_id = f"page_{int(timestamp)}_hello"
        title = data.get('title') or 'Untitled'
        
        conn = get_connection()
        cursor = conn.cursor()
        
        properties_str = json.dumps(data.get('properties', {})) if data.get('properties') else '{}'
        
        cursor.execute("INSERT INTO pages (id, title, properties) VALUES (?, ?, ?)", (page_id, title, properties_str))
        
        conn.commit()
        
        row = conn.execute('SELECT * FROM pages WHERE id=? AND archived=0', (page_id,)).fetchone()
        
        if not row or len(row) == 0:
            return jsonify({'error': 'Page creation failed'}), 500
        
        page = dict(row)
        result = {**page}
        result['last_edited_time'] = page.get('updated_at') or page.get('created_at')
        result['url'] = f"/api/pages/{page_id}"
        
        return jsonify(result), 201
        
    finally:
        conn.close()

@app.route('/api/pages/<string:page_id>', methods=['GET'])
def get_page(page_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        row = conn.execute('SELECT * FROM pages WHERE id=? AND archived=0', (page_id,)).fetchone()
        
        if not row or len(row) == 0:
            return jsonify({'error': 'Page not found'}), 404
        
        page = dict(row)
        
        cursor.execute("SELECT type, text_content FROM blocks WHERE page_id=? ORDER BY id ASC LIMIT 3", (page['id'],))
        
        block_rows = cursor.fetchall() if row else []
        
        result = {**page}
        result['last_edited_time'] = page.get('updated_at') or page.get('created_at')
        result['url'] = f"/api/pages/{page_id}"
        result['children'] = [dict(r) for r in block_rows] if row else []
        
        return jsonify(result)
        
    finally:
        conn.close()

@app.route('/api/search', methods=['GET'])
def search():
    query = request.args.get('query', '')
    
    try:
        if not query or len(query) < 2:
            return jsonify({'object': 'list', 'results': []})
        
        conn = get_connection()
        cursor = conn.cursor()
        
        results = conn.execute("SELECT id, title FROM pages WHERE archived=0 AND (title LIKE ? OR LOWER(title) LIKE ?) LIMIT 10", ('%' + query.replace('%', '%') + '%', '%' + query.lower() + '%'))
        
        rows = cursor.fetchall() if row else []
        
        return jsonify({
            'object': 'list',
            'results': [{'id': r[0], 'title': r[1]} for r in results]
        })
        
    finally:
        conn.close()

@app.route('/api/pages/<string:page_id>/blocks', methods=['POST'])
def create_block(page_id):
    data = request.json
    
    try:
        existing_page = get_connection().execute('SELECT id FROM pages WHERE id=? AND archived=0', (page_id,)).fetchone()
        
        if not existing_page or len(existing_page) == 0:
            return jsonify({'error': 'Page not found'}), 404
        
        timestamp = datetime.now().timestamp()
        block_type = data.get('type') or 'text'
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("INSERT INTO blocks (id, page_id, type) VALUES (?, ?, ?)", (f"block_{int(timestamp)}", page_id, block_type))
        
        conn.commit()
        
        return jsonify({'object': 'block'}), 201
        
    finally:
        conn.close()

@app.route('/api/pages/<string:page_id>/comments', methods=['POST'])
def create_comment(page_id):
    data = request.json
    
    try:
        existing_page = get_connection().execute('SELECT id FROM pages WHERE id=? AND archived=0', (page_id,)).fetchone()
        
        if not existing_page or len(existing_page) == 0:
            return jsonify({'error': 'Page or comment thread not found'}), 404
        
        content = data.get('content')[:500]
        timestamp = datetime.now().timestamp()
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("INSERT INTO comments (id, page_id, user_id, content) VALUES (?, ?, ?, ?)", (f"comment_{int(timestamp)}", page_id, 'default', content))
        
        conn.commit()
        
        return jsonify({'object': 'comment'}), 201
        
    finally:
        conn.close()

@app.errorhandler(400)
def bad_request(e):
    return jsonify({'error': {'detail': str(e)}}), 400

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print('Starting Notion-like App backend...')
    print(f'Database: SQLite ({DB_PATH})')
    
    # Initialize database tables on startup
    try:
        conn = get_connection()
        
        cursor = conn.cursor()
        
        # Create all required tables
        for table_name, columns in [
            ('users', 'id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL'),
            ('pages', "id TEXT PRIMARY KEY, parent_id TEXT, title TEXT DEFAULT 'Untitled', icon_data TEXT, cover_image_url TEXT, properties JSONB DEFAULT '{}', created_by TEXT REFERENCES users(id), is_favorite BOOLEAN DEFAULT 0, archived BOOLEAN DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ('blocks', "id TEXT PRIMARY KEY, page_id TEXT REFERENCES pages(id) ON DELETE CASCADE, type TEXT NOT NULL DEFAULT 'text', text_content TEXT, color TEXT DEFAULT 'default', is_checked BOOLEAN DEFAULT 0, children JSONB DEFAULT '[]'"),
            ('comments', "id TEXT PRIMARY KEY, page_id TEXT REFERENCES pages(id) ON DELETE CASCADE, user_id TEXT REFERENCES users(id), content TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        ]:
            
            if table_name == 'users':
                sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns})"
                
            elif table_name in ('pages',):
                sql = """CREATE TABLE IF NOT EXISTS pages 
                    (id TEXT PRIMARY KEY, parent_id TEXT, title TEXT DEFAULT 'Untitled', icon_data TEXT, cover_image_url TEXT, properties JSONB DEFAULT '{}', created_by TEXT REFERENCES users(id), is_favorite BOOLEAN DEFAULT 0, archived BOOLEAN DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
                
            elif table_name in ('blocks',):
                sql = """CREATE TABLE IF NOT EXISTS blocks 
                    (id TEXT PRIMARY KEY, page_id TEXT REFERENCES pages(id), type TEXT NOT NULL DEFAULT 'text', text_content TEXT, color TEXT DEFAULT 'default', is_checked BOOLEAN DEFAULT 0, children JSONB DEFAULT '[]')"""
                
            elif table_name == 'comments':
                sql = """CREATE TABLE IF NOT EXISTS comments 
                    (id TEXT PRIMARY KEY, page_id TEXT REFERENCES pages(id), user_id TEXT REFERENCES users(id), content TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
            
            cursor.execute(sql)
        
        # Insert default user if not exists
        try:
            cursor.execute('SELECT COUNT(*) FROM users')
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO users (id, name, email) VALUES ('default', 'Guest User', 'guest@notionspace.local')")
            
            conn.commit()
        except Exception as e:
            print(f"Error inserting default user: {e}")
        
    finally:
        try: get_connection().close() if hasattr(get_connection(), 'close') else None
        except: pass
    
    # Create default "Welcome" page after tables are created
    try:
        conn = get_connection()
        
        welcome_exists = bool(conn.execute("SELECT id FROM pages WHERE title='Welcome to NoteSpace!'").fetchone())
        
        if not welcome_exists:
            print('Creating default "Welcome" page...')
            
            cursor = conn.cursor()
            cursor.execute("INSERT INTO pages (id, title) VALUES (?, ?)", ('page_welcome_12345', 'Welcome to NoteSpace!'))
            
            # Add a heading block as first child
            cursor.execute('''INSERT INTO blocks (id, page_id, type, text_content) 
                         VALUES (?, ?, ?, ?)''', ('block_heading_1', 'page_welcome_12345', 'heading_1', '# Welcome to NoteSpace!'))
            
            conn.commit()
        
        print('Default "Welcome" page created successfully')
    except Exception as e:
        pass
    
    finally:
        try: get_connection().close() if hasattr(get_connection(), 'close') else None
        except: pass
    
    app.run(debug=False, host='0.0.0.0', port=5000)

