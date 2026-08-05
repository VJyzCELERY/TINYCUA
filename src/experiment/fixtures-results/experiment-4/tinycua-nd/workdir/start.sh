#!/bin/sh

# Notion-like Application Entrypoint
# Installs dependencies, initializes database, starts Flask backend with frontend

set -e

# Default port if not set
PORT="${PORT:-8765}"

# Install Python dependencies via uv (preferred) or pip fallback
if command -v uv >/dev/null 2>&1; then
    uv pip install --system flask
else
    pip install flask
fi

# Create database directory
mkdir -p .database

# Initialize SQLite database with schema
python3 << 'EOF'
import sqlite3
import os

db_path = os.path.join('.database', 'app.db')

# Remove existing database if it exists (reinitialize)
if os.path.exists(db_path):
    os.remove(db_path)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create pages table for document pages
cursor.execute('''
CREATE TABLE pages (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Create blocks table with Notion-like block types
cursor.execute('''
CREATE TABLE blocks (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    position INTEGER NOT NULL,
    page_id TEXT,
    block_type TEXT NOT NULL DEFAULT 'paragraph',
    FOREIGN KEY (page_id) REFERENCES pages(id)
)
''')

# Create index for efficient block ordering
cursor.execute('CREATE INDEX idx_blocks_position ON blocks(position)')

conn.commit()
conn.close()
print("Database initialized successfully with pages and blocks tables")
EOF

# Create frontend static files directory
mkdir -p frontend/static
mkdir -p frontend/templates

# Create enhanced HTML frontend with intuitive text block editor
cat > frontend/templates/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Notion-like App</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; background: #fafafa; color: #37352f; }
        .container { max-width: 900px; margin: 0 auto; background: white; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.12); padding: 24px; }
        h1 { color: #37352f; margin-bottom: 24px; font-size: 32px; font-weight: 600; }
        .block-list { list-style: none; display: flex; flex-direction: column; gap: 8px; }
        .block-item { padding: 12px 16px; border: 1px solid #e3e3e3; border-radius: 4px; cursor: pointer; transition: all 0.15s ease; background: white; font-size: 15px; line-height: 1.5; position: relative; outline: none; }
        .block-item:hover { background: #f7f7f7; border-color: #dcdcdc; }
        .block-item.selected { border-color: #2eaadc; border-width: 2px; box-shadow: 0 0 0 1px rgba(46,170,220,0.2); z-index: 1; }
        .block-item.deleting { opacity: 0.5; background: #ffebee; }
        .add-block-btn { width: 100%; padding: 12px; background: #2eaadc; color: white; border: none; border-radius: 4px; margin-top: 16px; cursor: pointer; font-size: 15px; font-weight: 500; transition: background 0.15s; }
        .add-block-btn:hover { background: #2697c1; }
        .delete-btn { background: #fa5e5e; color: white; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 13px; margin-left: 8px; display: none; transition: background 0.15s; }
        .delete-btn:hover { background: #e05252; }
        .block-item.selected .delete-btn { display: inline-flex; align-items: center; gap: 4px; }
        .empty-state { text-align: center; color: #6b6b6b; padding: 48px; font-size: 16px; }
        .editor-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: none; justify-content: center; align-items: center; z-index: 100; }
        .editor-overlay.active { display: flex; }
        .editor-container { background: white; border-radius: 8px; padding: 24px; min-width: 500px; max-width: 90%; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
        .editor-container h2 { margin-bottom: 16px; font-size: 18px; color: #37352f; }
        .editor-textarea { width: 100%; min-height: 120px; padding: 12px; border: 1px solid #e3e3e3; border-radius: 4px; font-family: inherit; font-size: 15px; line-height: 1.5; resize: vertical; outline: none; transition: border-color 0.15s; }
        .editor-textarea:focus { border-color: #2eaadc; }
        .editor-buttons { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
        .save-btn { background: #2eaadc; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: 500; }
        .save-btn:hover { background: #2697c1; }
        .cancel-btn { background: #e3e3e3; color: #37352f; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 14px; }
        .cancel-btn:hover { background: #d0d0d0; }
        .keyboard-hint { font-size: 12px; color: #888; margin-top: 4px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Notion-like Text Blocks</h1>
        <ul class="block-list" id="blockList"></ul>
        <button class="add-block-btn" onclick="addBlock()" tabindex="0" role="button" aria-label="Add new block">+ Add New Block</button>
    </div>

    <!-- Editor overlay for editing selected block -->
    <div class="editor-overlay" id="editorOverlay" role="dialog" aria-modal="true" aria-labelledby="editorTitle">
        <div class="editor-container">
            <h2 id="editorTitle">Edit Block</h2>
            <textarea class="editor-textarea" id="editorTextarea" placeholder="Type here to edit this block..." aria-label="Block content editor"></textarea>
            <div class="keyboard-hint">Press Enter to confirm, Esc to cancel</div>
            <div class="editor-buttons">
                <button class="cancel-btn" onclick="cancelEdit()" tabindex="0">Cancel</button>
                <button class="save-btn" onclick="saveEdit()" tabindex="0">Save</button>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = '/api';
        let selectedBlockId = null;
        let currentBlockData = null;

        // Load blocks from database
        async function loadBlocks() {
            try {
                const response = await fetch(`${API_BASE}/blocks`);
                if (!response.ok) throw new Error('Failed to load blocks');
                const blocks = await response.json();
                renderBlocks(blocks);
            } catch (err) {
                console.error(err);
                document.getElementById('blockList').innerHTML = '<li class="empty-state">No blocks yet. Click "+ Add New Block" to create your first block.</li>';
            }
        }

        function renderBlocks(blocks) {
            const list = document.getElementById('blockList');
            list.innerHTML = '';
            
            if (blocks.length === 0) {
                list.innerHTML = '<li class="empty-state">No blocks yet. Click "+ Add New Block" to create your first block.</li>';
                return;
            }

            blocks.forEach(block => {
                const li = document.createElement('li');
                li.className = 'block-item';
                li.dataset.id = block.id;
                li.textContent = block.content || '(empty)';
                
                // Click handler for selection
                li.onclick = (e) => selectBlock(e, block.id);
                
                // Keyboard accessibility - Enter to confirm edit when focused
                li.onkeydown = (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        editBlock(block.id);
                    }
                };
                li.innerHTML += `<button class="delete-btn" onclick="deleteBlock('${block.id}')" aria-label="Delete block" tabindex="-1">Delete</button>`;
                list.appendChild(li);
            });
        }

        function selectBlock(event, id) {
            // Remove selected class from all items
            document.querySelectorAll('.block-item').forEach(el => el.classList.remove('selected'));
            
            // Add selected class to clicked item
            const selectedItem = event.target.closest('.block-item');
            if (selectedItem) {
                selectedItem.classList.add('selected');
                selectedBlockId = id;
                
                // Focus the delete button for keyboard accessibility
                const deleteBtn = selectedItem.querySelector('.delete-btn');
                if (deleteBtn) {
                    deleteBtn.focus();
                }
            }
        }

        async function addBlock() {
            try {
                const response = await fetch(`${API_BASE}/blocks`, { 
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: '', block_type: 'paragraph', page_id: null })
                });
                if (!response.ok) throw new Error('Failed to create block');
                const block = await response.json();
                loadBlocks();
            } catch (err) {
                console.error(err);
                alert('Error creating block');
            }
        }

        async function editBlock(id) {
            try {
                // Get current block data
                const response = await fetch(`${API_BASE}/blocks/${id}`);
                if (!response.ok) throw new Error('Failed to get block');
                currentBlockData = await response.json();
                
                // Store selected ID on overlay
                document.getElementById('editorOverlay').dataset.selectedId = currentBlockData.id;
                
                // Set textarea value
                const textarea = document.getElementById('editorTextarea');
                textarea.value = currentBlockData.content || '';
                textarea.focus();
                
                // Show editor overlay
                const overlay = document.getElementById('editorOverlay');
                overlay.classList.add('active');
                overlay.setAttribute('aria-hidden', 'false');
                
                // Focus textarea for keyboard accessibility
                setTimeout(() => textarea.focus(), 50);
                
            } catch (err) {
                console.error(err);
                alert('Error opening editor');
            }
        }

        function cancelEdit() {
            const overlay = document.getElementById('editorOverlay');
            overlay.classList.remove('active');
            overlay.setAttribute('aria-hidden', 'true');
            selectedBlockId = null;
        }

        async function saveEdit() {
            try {
                const textarea = document.getElementById('editorTextarea');
                const newContent = textarea.value.trim();
                
                const response = await fetch(`${API_BASE}/blocks/${selectedBlockId}`, { 
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: newContent })
                });
                
                if (!response.ok) throw new Error('Failed to save block');
                const updated = await response.json();
                
                // Close editor and reload blocks
                cancelEdit();
                loadBlocks();
            } catch (err) {
                console.error(err);
                alert('Error saving block');
            }
        }

        async function deleteBlock(id) {
            if (!confirm('Delete this block? This action cannot be undone.')) return;
            try {
                await fetch(`${API_BASE}/blocks/${id}`, { method: 'DELETE' });
                loadBlocks();
            } catch (err) {
                console.error(err);
                alert('Error deleting block');
            }
        }

        // Close editor overlay when clicking outside
        document.getElementById('editorOverlay').addEventListener('click', (e) => {
            if (e.target.id === 'editorOverlay') {
                cancelEdit();
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && document.getElementById('editorOverlay').classList.contains('active')) {
                cancelEdit();
            }
        });

        // Load blocks on page load
        loadBlocks();
    </script>
</body>
</html>
HTMLEOF

# Create Flask backend application
cat > app.py << 'PYEOF'
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
PYEOF

# Start Flask backend serving static files and API endpoints
cd "$(dirname "$0")"
exec python3 -W ignore::DeprecationWarning app.py
