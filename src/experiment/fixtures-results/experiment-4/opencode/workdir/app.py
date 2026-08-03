"""Notion-like workspace application with Python backend and SQLite storage."""
import uuid
from flask import Flask, jsonify, request, render_template_string
import sqlite3
import os

app = Flask(__name__)
DATABASE = '/workspace/workspace.db'

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with schema."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocks (
            id TEXT PRIMARY KEY,
            content TEXT DEFAULT '',
            page_id TEXT
        )
    ''')
    
    # Initialize with a default block if empty
    cursor.execute('SELECT COUNT(*) FROM blocks')
    count = cursor.fetchone()[0]
    if count == 0:
        cursor.execute(
            'INSERT INTO blocks (id, content) VALUES (?, ?)',
            (f'block_{uuid.uuid4().hex[:8]}', '')
        )
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """Render the main page."""
    return render_template_string(TEMPLATE_HTML)

TEMPLATE_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Workspace</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #fff;
            color: #37352f;
            line-height: 1.6;
            padding: 20px;
        }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { font-size: 2em; border-bottom: 1px solid #e1e1e1; padding-bottom: 10px; }
        
        .block {
            position: relative;
            min-height: 24px;
            margin-bottom: 8px;
            padding: 4px 6px;
            border-radius: 3px;
            cursor: pointer;
            transition: background-color 0.15s;
        }
        .block:hover { background-color: #f2f2f2; }
        .block.selected { outline: 2px solid #007bff; outline-offset: -2px; }
        
        .block-content { display: inline-block; min-width: 100%; word-break: break-word; }
        .block-content:focus { outline: none; }
        .block-content::placeholder { color: #9aa0aa; }
        
        .toolbar {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            padding: 8px 16px;
            display: flex;
            gap: 12px;
            align-items: center;
            z-index: 100;
        }
        .toolbar button {
            background: #f2f2f2;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: background-color 0.15s;
        }
        .toolbar button:hover { background: #e8e8e8; }
        .toolbar button.primary { background: #007bff; color: white; }
        .toolbar button.primary:hover { background: #0069d9; }
        
        .empty-state { text-align: center; padding: 60px 20px; color: #8c8c8c; }
    </style>
</head>
<body>
    <div class="container">
        <h1 id="page-title">Untitled</h1>
        <div id="blocks-container"></div>
        <div id="empty-state" class="empty-state" style="display: none;">
            <p>Select a block to edit or click "New Block" to add one</p>
        </div>
    </div>
    
    <div class="toolbar">
        <button onclick="addBlock()">+ New Block</button>
        <button class="primary" onclick="deleteSelected()">Delete Selected</button>
    </div>

    <script>
        let selectedBlock = null;
        
        async function loadBlocks() {
            try {
                const response = await fetch('/api/blocks');
                if (!response.ok) throw new Error('Failed to load blocks');
                const blocks = await response.json();
                
                const container = document.getElementById('blocks-container');
                const emptyState = document.getElementById('empty-state');
                
                if (blocks.length === 0) {
                    container.innerHTML = '';
                    emptyState.style.display = 'block';
                } else {
                    emptyState.style.display = 'none';
                    container.innerHTML = blocks.map(block => createBlockElement(block)).join('');
                }
            } catch (error) {
                console.error('Error loading blocks:', error);
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function createBlockElement(block) {
            const isSelected = block.id === selectedBlock ? 'selected' : '';
            const blockIdEscaped = escapeHtml(block.id);
            const content = escapeHtml(block.content);
            
            return '<div class="block ' + isSelected + '" data-id="' + blockIdEscaped + '" tabindex="0" onkeydown="handleBlockKeydown(event, \'' + blockIdEscaped + '\')">';
        }
        
        function createBlockElementWithContent(block) {
            const content = escapeHtml(block.content);
            return '</span><span class="block-content">' + content + '</span></div>';
        }
        
        async function handleBlockKeydown(event, blockId) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                selectedBlock = blockId;
                updateSelectedBlock(blockId);
            } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'delete') {
                await deleteSelected();
            }
        }
        
        async function addBlock() {
            try {
                const response = await fetch('/api/blocks', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: '' })
                });
                if (!response.ok) throw new Error('Failed to create block');
                const block = await response.json();
                
                document.getElementById('empty-state').style.display = 'none';
                
                selectedBlock = block.id;
                updateSelectedBlock(block.id);
            } catch (error) {
                console.error('Error adding block:', error);
            }
        }
        
        async function deleteSelected() {
            if (!selectedBlock) return;
            
            try {
                const response = await fetch('/api/blocks/' + selectedBlock, { method: 'DELETE' });
                if (response.ok || response.status === 204) {
                    const blocksDiv = document.getElementById('blocks-container');
                    blocksDiv.innerHTML = '';
                    
                    selectedBlock = null;
                    document.getElementById('empty-state').style.display = 'block';
                } else {
                    console.error('Failed to delete block:', response.status);
                }
            } catch (error) {
                console.error('Error deleting block:', error);
            }
        }
        
        async function updateSelectedBlock(blockId) {
            const content = document.querySelector('.block[data-id="' + blockId + '"] .block-content').innerText;
            
            try {
                await fetch('/api/blocks/' + blockId, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content })
                });
            } catch (error) {
                console.error('Error updating block:', error);
            }
        }
        
        loadBlocks();
    </script>
</body>
</html>
'''

@app.route('/api/blocks', methods=['GET'])
def get_blocks():
    """Get all blocks."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, content FROM blocks ORDER BY RANDOM()')
    rows = cursor.fetchall()
    conn.close()
    return jsonify([{'id': row['id'], 'content': row['content']} for row in rows])

@app.route('/api/blocks', methods=['POST'])
def create_block():
    """Create a new block."""
    data = request.get_json() or {}
    content = data.get('content', '') if isinstance(data, dict) else ''
    
    conn = get_db()
    cursor = conn.cursor()
    new_id = f'block_{uuid.uuid4().hex[:8]}'
    
    cursor.execute(
        'INSERT INTO blocks (id, content) VALUES (?, ?)',
        (new_id, content)
    )
    conn.commit()
    conn.close()
    
    return jsonify({'id': new_id, 'content': content}), 201

@app.route('/api/blocks/<block_id>', methods=['PUT'])
def update_block(block_id):
    """Update a block."""
    data = request.get_json() or {}
    content = data.get('content', '') if isinstance(data, dict) else ''
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE blocks SET content = ? WHERE id = ?',
        (content, block_id)
    )
    conn.commit()
    
    cursor.execute('SELECT id, content FROM blocks WHERE id = ?', (block_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'error': 'Block not found'}), 404
    
    return jsonify({'id': row['id'], 'content': row['content']})

@app.route('/api/blocks/<block_id>', methods=['DELETE'])
def delete_block(block_id):
    """Delete a block."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM blocks WHERE id = ?', (block_id,))
    conn.commit()
    
    if cursor.rowcount == 0:
        return jsonify({'error': 'Block not found'}), 404
    
    conn.close()
    return '', 204

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8765))
    app.run(host='127.0.0.1', port=port, debug=False)
