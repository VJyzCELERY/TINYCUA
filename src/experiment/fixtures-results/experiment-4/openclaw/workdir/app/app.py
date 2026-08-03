from flask import Flask, request, jsonify, render_template
import sqlite3
import os
from database import get_connection, init_db, get_page_or_404, get_blocks_for_page

app = Flask(__name__, static_folder='static', template_folder='templates')
init_db()

@app.route('/')
def index():
    return render_template('index.html')

# Pages API
@app.route('/api/pages', methods=['GET'])
def list_pages():
    conn = get_connection()
    cursor = conn.execute('SELECT * FROM pages ORDER BY updated_at DESC')
    pages = cursor.fetchall()
    conn.close()
    
    return jsonify([{
        'id': row['id'],
        'title': row['title'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at']
    } for row in pages])

@app.route('/api/pages/<int:page_id>', methods=['GET'])
def get_page(page_id):
    page = get_page_or_404(page_id)
    if not page:
        return jsonify({'error': 'Page not found'}), 404
    
    blocks = get_blocks_for_page(page_id)
    
    # Reorder blocks by their current order_idx
    ordered_blocks = sorted(blocks, key=lambda b: b['order_idx'])
    
    return jsonify({
        'id': page['id'],
        'title': page['title'],
        'blocks': [{'content': row['content']} for row in ordered_blocks]
    })

@app.route('/api/pages', methods=['POST'])
def create_page():
    data = request.get_json()
    title = data.get('title', 'Untitled') if data else 'Untitled'
    
    conn = get_connection()
    cursor = conn.execute(
        'INSERT INTO pages (title) VALUES (?)',
        (title,)
    )
    page_id = cursor.lastrowid
    conn.commit()  # Commit the insert
    conn.close()
    
    return jsonify({
        'id': page_id,
        'title': title
    }), 201

@app.route('/api/pages/<int:page_id>', methods=['PUT'])
def update_page(page_id):
    data = request.get_json() if request else {}
    new_title = data.get('title', '') if data else ''
    
    conn = get_connection()
    cursor = conn.execute(
        'UPDATE pages SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
        (new_title, page_id)
    )
    
    if not cursor.rowcount:
        conn.close()
        return jsonify({'error': 'Page not found'}), 404
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'id': page_id,
        'title': new_title
    })

@app.route('/api/pages/<int:page_id>', methods=['DELETE'])
def delete_page(page_id):
    conn = get_connection()
    
    cursor = conn.execute('SELECT title FROM pages WHERE id = ?', (page_id,))
    page = cursor.fetchone()
    
    if not page:
        conn.close()
        return jsonify({'error': 'Page not found'}), 404
    
    cursor = conn.execute('DELETE FROM blocks WHERE page_id = ?', (page_id,))
    cursor = conn.execute('DELETE FROM pages WHERE id = ?', (page_id,))
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Page not found'}), 404
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'id': page_id,
        'title': page['title'],
        'deleted': True
    })

# Blocks API
@app.route('/api/pages/<int:page_id>/blocks', methods=['GET'])
def get_blocks(page_id):
    blocks = get_blocks_for_page(page_id)
    
    # Reorder blocks by their current order_idx
    ordered_blocks = sorted(blocks, key=lambda b: b['order_idx'])
    
    return jsonify([{'content': row['content']} for row in ordered_blocks])

@app.route('/api/pages/<int:page_id>/blocks', methods=['POST'])
def create_block(page_id):
    data = request.get_json() if request else {}
    content = data.get('content', '') if data else ''
    
    conn = get_connection()
    
    # Get current max order_idx + 1
    cursor = conn.execute(
        'SELECT COALESCE(MAX(order_idx), -1) as max_idx FROM blocks WHERE page_id = ?',
        (page_id,)
    )
    row = cursor.fetchone()
    new_order = row['max_idx'] + 1
    
    cursor = conn.execute(
        'INSERT INTO blocks (page_id, content, order_idx) VALUES (?, ?, ?)',
        (page_id, content, new_order)
    )
    
    block_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({
        'id': block_id,
        'content': content
    }), 201

@app.route('/api/pages/<int:page_id>/blocks/<int:block_id>', methods=['PUT'])
def update_block(page_id, block_id):
    data = request.get_json() if request else {}
    new_content = data.get('content', '') if data else ''
    
    conn = get_connection()
    cursor = conn.execute(
        'SELECT content FROM blocks WHERE id = ? AND page_id = ?',
        (block_id, page_id)
    )
    
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Block not found'}), 404
    
    cursor = conn.execute(
        'UPDATE blocks SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND page_id = ?',
        (new_content, block_id, page_id)
    )
    
    if not cursor.rowcount:
        conn.close()
        return jsonify({'error': 'Block not found'}), 404
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'id': block_id,
        'content': new_content
    })

@app.route('/api/pages/<int:page_id>/blocks/<int:block_id>', methods=['DELETE'])
def delete_block(page_id, block_id):
    conn = get_connection()
    
    cursor = conn.execute(
        'SELECT content FROM blocks WHERE id = ? AND page_id = ?',
        (block_id, page_id)
    )
    
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Block not found'}), 404
    
    cursor = conn.execute(
        'DELETE FROM blocks WHERE id = ? AND page_id = ?',
        (block_id, page_id)
    )
    
    if not cursor.rowcount:
        conn.close()
        return jsonify({'error': 'Block not found'}), 404
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'id': block_id,
        'deleted': True
    })

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8765))
    app.run(host='0.0.0.0', port=port)
