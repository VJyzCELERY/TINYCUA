#!/usr/bin/env python3
"""Notion-like web app with Python backend and SQLite storage."""

import os
import sqlite3
from flask import Flask, render_template, request, jsonify, url_for

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-key'

# Database path - use relative path to preserve data across invocations
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'notion.db')

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database schema with migration-ready blocks table."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Drop existing blocks table to apply new migration-ready schema
    cursor.execute('DROP TABLE IF EXISTS blocks')
    
    # Blocks table - stores text blocks with content and order
    # Schema supports text blocks with keyboard-accessible editing
    cursor.execute('''
        CREATE TABLE blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id TEXT NOT NULL DEFAULT 'default',
            type TEXT NOT NULL DEFAULT 'text',
            content TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create index for efficient position-based queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_blocks_position ON blocks(position)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_blocks_page_id ON blocks(page_id)')
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """Main page rendering text blocks."""
    return render_template('index.html')

@app.route('/api/blocks', methods=['GET'])
@app.route('/api/blocks', methods=['GET'])
def get_blocks():
    """Get all blocks ordered by position."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, content, position FROM blocks ORDER BY position, id')
    rows = cursor.fetchall()
    blocks = [{'id': row['id'], 'content': row['content'], 'position': row['position']} for row in rows]
    conn.close()
    return jsonify(blocks)

@app.route('/api/block/<int:block_id>', methods=['GET'])
def get_block(block_id):
    """Get a single block by ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, content, position FROM blocks WHERE id = ?', (block_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return jsonify({'id': row['id'], 'content': row['content'], 'position': row['position']})
    return jsonify({'error': 'Block not found'}), 404

@app.route('/api/blocks', methods=['POST'])
def add_block():
    """Add a new block."""
    data = request.get_json()
    content = data.get('content', '')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COALESCE(MAX(position), -1) + 1 FROM blocks')
    position = cursor.fetchone()[0]
    cursor.execute('INSERT INTO blocks (content, position) VALUES (?, ?)', (content, position))
    conn.commit()
    block_id = cursor.lastrowid
    conn.close()
    return jsonify({'id': block_id, 'content': content, 'position': position}), 201

@app.route('/api/block/<int:block_id>', methods=['PUT'])
def update_block(block_id):
    """Update block content."""
    data = request.get_json()
    content = data.get('content', '')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE blocks SET content = ? WHERE id = ?', (content, block_id))
    conn.commit()
    conn.close()
    return jsonify({'id': block_id, 'content': content})

@app.route('/api/block/<int:block_id>', methods=['DELETE'])
def delete_block(block_id):
    """Delete a block."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM blocks WHERE id = ?', (block_id,))
    conn.commit()
    rows_deleted = cursor.rowcount
    conn.close()
    return jsonify({'deleted': rows_deleted > 0})

@app.route('/api/selected', methods=['GET'])
def get_selected():
    """Get current selected block ID from cookie."""
    selected_id = request.cookies.get('selected_block_id')
    return jsonify({'selected_block_id': selected_id}), 200

@app.route('/api/selected', methods=['POST'])\ndef set_selected():
    """Set selected block ID via cookie."""
    data = request.get_json()
    selected_id = data.get('id')
    response = jsonify({'selected_block_id': selected_id})
    response.set_cookie('selected_block_id', str(selected_id), httponly=True, secure=False, samesite='Lax')
    return response, 200

@app.route('/api/blocks/clear', methods=['POST'])\ndef clear_blocks():
    """Delete all blocks."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM blocks')
    conn.commit()
    conn.close()
    return jsonify({'cleared': True})

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8765))
    app.run(host='127.0.0.1', port=port, debug=False)
