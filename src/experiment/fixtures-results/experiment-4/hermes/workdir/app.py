#!/usr/bin/env python3
"""Notion-like workspace backend with Flask and SQLite."""

import os
import sqlite3
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DATABASE = '/workspace/data.db'


def get_db():
    """Get database connection with row factory."""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    """Initialize the database schema."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db.commit()
    db.close()


@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/api/blocks', methods=['GET'])
def get_blocks():
    """Get all blocks with their positions."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id, content, position FROM blocks ORDER BY position ASC')
    rows = cursor.fetchall()
    db.close()
    
    blocks = []
    for row in rows:
        blocks.append({
            'id': row['id'],
            'content': row['content'],
            'position': row['position']
        })
    
    return jsonify(blocks)


@app.route('/api/blocks', methods=['POST'])
def create_block():
    """Create a new block."""
    data = request.json
    content = data.get('content', '')
    position = data.get('position')
    
    db = get_db()
    cursor = db.cursor()
    
    # Insert the new block
    cursor.execute(
        'INSERT INTO blocks (content, position) VALUES (?, ?)',
        (content, position)
    )
    block_id = cursor.lastrowid
    
    # Update created_at and updated_at timestamps
    cursor.execute('UPDATE blocks SET content=?, position=? WHERE id=?',
                   (content, position, block_id))
    
    db.commit()
    db.close()
    
    return jsonify({
        'id': block_id,
        'content': content,
        'position': position
    }), 201


@app.route('/api/blocks/<int:block_id>', methods=['PUT'])
def update_block(block_id):
    """Update an existing block."""
    data = request.json
    content = data.get('content', '')
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute(
        'UPDATE blocks SET content=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
        (content, block_id)
    )
    
    if cursor.rowcount == 0:
        return jsonify({'error': 'Block not found'}), 404
    
    db.commit()
    db.close()
    
    # Get the updated block
    cursor.execute('SELECT id, content, position FROM blocks WHERE id=?', (block_id,))
    row = cursor.fetchone()
    
    return jsonify({
        'id': row['id'],
        'content': row['content'],
        'position': row['position']
    })


@app.route('/api/blocks/<int:block_id>', methods=['DELETE'])
def delete_block(block_id):
    """Delete a block."""
    db = get_db()
    
    cursor = db.cursor()
    cursor.execute('SELECT position FROM blocks WHERE id=?', (block_id,))
    row = cursor.fetchone()
    
    if not row:
        return jsonify({'error': 'Block not found'}), 404
    
    cursor.execute('DELETE FROM blocks WHERE id=?', (block_id,))
    db.commit()
    db.close()
    
    return jsonify({'success': True})


@app.route('/api/blocks/reorder', methods=['POST'])
def reorder_blocks():
    """Reorder multiple blocks."""
    data = request.json
    positions = data.get('positions', [])
    
    if not positions:
        return jsonify({'error': 'No positions provided'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Update all blocks with new positions
    for item in positions:
        block_id = item['id']
        position = item['position']
        cursor.execute(
            'UPDATE blocks SET position=? WHERE id=?',
            (position, block_id)
        )
    
    db.commit()
    db.close()
    
    return jsonify({'success': True})


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8765)), debug=True)
