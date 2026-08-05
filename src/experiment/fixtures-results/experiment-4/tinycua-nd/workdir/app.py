from flask import Flask, jsonify, request, send_from_directory
import sqlite3
import os

app = Flask(__name__, static_folder='frontend/static', static_url_path='')

DATABASE_PATH = os.path.join('.database', 'app.db')

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/', methods=['GET'])
def index():
    return send_from_directory('frontend/templates', 'index.html')

# Pages API endpoints
@app.route('/api/pages', methods=['GET'])
def get_pages():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM pages ORDER BY created_at')
    rows = cursor.fetchall()
    pages = [{'id': row['id'], 'name': row['name']} for row in rows]
    conn.close()
    return jsonify(pages)

@app.route('/api/pages', methods=['POST'])
def create_page():
    name = request.json.get('name', '')
    conn = get_db()
    cursor = conn.cursor()
    page_id = f'page_{len(cursor.execute("SELECT id FROM pages").fetchall()) + 1}'
    # Generate unique ID
    import uuid
    page_id = str(uuid.uuid4())
    cursor.execute('INSERT INTO pages (id, name) VALUES (?, ?)', (page_id, name))
    conn.commit()
    page = {'id': page_id, 'name': name}
    conn.close()
    return jsonify(page), 201

@app.route('/api/pages/<page_id>', methods=['DELETE'])
def delete_page(page_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM pages WHERE id = ?', (page_id,))
    conn.commit()
    # Also delete all blocks in this page
    cursor.execute('DELETE FROM blocks WHERE page_id = ?', (page_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'deleted'})

# Blocks API endpoints
@app.route('/api/blocks', methods=['GET'])
def get_blocks():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, content, position, page_id, block_type FROM blocks ORDER BY position')
    rows = cursor.fetchall()
    blocks = [{'id': row['id'], 'content': row['content'], 'position': row['position'], 
                 'page_id': row['page_id'], 'block_type': row['block_type']} for row in rows]
    conn.close()
    return jsonify(blocks)

@app.route('/api/blocks', methods=['POST'])
def create_block():
    content = request.json.get('content', '')
    block_type = request.json.get('block_type', 'paragraph')
    page_id = request.json.get('page_id', None)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as count FROM blocks ORDER BY position DESC LIMIT 1')
    result = cursor.fetchone()
    current_position = result['count'] + 1 if result else 0
    block_id = f'block_{current_position}'
    cursor.execute('INSERT INTO blocks (id, content, position, page_id, block_type) VALUES (?, ?, ?, ?, ?)', 
                   (block_id, content, current_position, page_id, block_type))
    conn.commit()
    block = {'id': block_id, 'content': content, 'position': current_position, 
              'page_id': page_id, 'block_type': block_type}
    conn.close()
    return jsonify(block), 201

@app.route('/api/blocks/<block_id>', methods=['GET'])
def get_block(block_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, content, position, page_id, block_type FROM blocks WHERE id = ?', (block_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Block not found'}), 404
    return jsonify({'id': row['id'], 'content': row['content'], 'position': row['position'], 
                     'page_id': row['page_id'], 'block_type': row['block_type']})

@app.route('/api/blocks/<block_id>', methods=['PUT'])
def update_block(block_id):
    content = request.json.get('content', '')
    block_type = request.json.get('block_type', None)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE blocks SET content = ? WHERE id = ?', (content, block_id))
    conn.commit()
    if block_type:
        cursor.execute('UPDATE blocks SET block_type = ? WHERE id = ?', (block_type, block_id))
        conn.commit()
    conn.close()
    return jsonify({'id': block_id, 'content': content})

@app.route('/api/blocks/<block_id>', methods=['DELETE'])
def delete_block(block_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM blocks WHERE id = ?', (block_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'deleted'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8765))
    app.run(host='0.0.0.0', port=port, debug=False)
