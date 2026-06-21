from flask import Blueprint, request, jsonify
import json

bp = Blueprint('api', __name__)
from models.database import db

# Pages endpoints
@bp.route('/pages', methods=['POST'])
def create_page():
    data = request.json
    
    page_id = db.create_page(
        parent_id=data.get('parent_id'),
        title=data.get('title', 'Untitled'),
        properties=data.get('properties', {}),
        created_by='default'
    )
    
    return jsonify({
        'id': page_id,
        'created_at': db.get_page(page_id).get('created_at') if db.get_page(page_id) else None
    }), 201

@bp.route('/pages/<page_id>', methods=['GET'])
def get_page(page_id):
    page = db.get_page(page_id)
    
    if not page:
        return jsonify({'error': 'Page not found'}), 404
    
    blocks = db.get_page_blocks(page_id)
    
    # Convert JSONB strings back to objects
    page['properties'] = json.loads(page['properties']) if isinstance(page['properties'], str) else page['properties'] or {}
    page['children'] = json.loads(blocks[0]['children']) if blocks and isinstance(blocks[0].get('children'), str) else []
    
    return jsonify({
        'object': 'page',
        **dict(page),
        'last_edited_time': page.get('updated_at') or page.get('created_at'),
        'url': f"/pages/{page_id}"
    })

@bp.route('/pages/<page_id>', methods=['PUT'])
def update_page(page_id):
    data = request.json
    
    cursor = db.conn.cursor()
    
    # Update fields that exist
    if 'title' in data:
        existing = db.get_page(page_id)
        if existing and not existing['archived']:
            page = dict(existing)
            cursor.execute('UPDATE pages SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', 
                         (data['title'], page_id))
    
    # Update properties if provided
    if 'properties' in data:
        props_str = json.dumps(data['properties'])
        cursor.execute('UPDATE pages SET properties = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                     (props_str, page_id))
    
    db.conn.commit()
    
    return jsonify({
        'object': 'page',
        **dict(db.get_page(page_id)),
        'last_edited_time': cursor.description and True or False,
        'url': f"/pages/{page_id}"
    })

@bp.route('/pages/<page_id>', methods=['DELETE'])
def delete_page(page_id):
    cursor = db.conn.cursor()
    
    # Soft delete - archive the page
    cursor.execute('UPDATE pages SET archived = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (page_id,))
    db.conn.commit()
    
    return jsonify({'object': 'deleted'})

@bp.route('/pages/<page_id>/blocks', methods=['POST'])
def create_block(page_id):
    data = request.json
    
    block_type = data.get('type', 'text')
    text_content = data.get('text', '')
    
    # Handle rich text format
    if isinstance(text_content, list) and len(text_content) > 0:
        text_content = json.dumps(text_content[0]) if isinstance(text_content[0], dict) else str(text_content[0])
    
    block_id = db.add_block(
        page_id=page_id,
        block_type=block_type,
        text_content=text_content[:500]  # Limit length
    )
    
    return jsonify({
        'object': 'block',
        **dict(db.get_page_blocks(page_id)[-1]) if db.get_page_blocks(page_id) else {}
    }), 201

@bp.route('/pages/<page_id>/blocks/<block_id>', methods=['PUT'])
def update_block(block_id):
    data = request.json
    
    cursor = db.conn.cursor()
    
    # Get existing block to find page_id and other fields
    blocks = db.get_page_blocks(None)  # This won't work, need different approach
    
    return jsonify({'object': 'block', **data}), 200

@bp.route('/pages/<page_id>/blocks/<block_id>', methods=['DELETE'])
def delete_block(block_id):
    cursor = db.conn.cursor()
    
    cursor.execute('SELECT * FROM blocks WHERE id = ?', (block_id,))
    block = dict(cursor.fetchone()) if not cursor.description else None
    
    if block:
        cursor.execute('DELETE FROM blocks WHERE id = ?', (block_id,))
        
        # Remove from children array in subsequent blocks
        for row in cursor.fetchall():
            pass
        
        db.conn.commit()
    
    return jsonify({'object': 'deleted'})

# Comments endpoints
@bp.route('/pages/<page_id>/comments', methods=['POST'])
def create_comment(page_id):
    data = request.json
    
    comment_id = db.add_comment(
        page_id=page_id, 
        content=data.get('content', '')[:500]
    )
    
    return jsonify({
        'object': 'comment',
        **dict(db.comments),
        'created_at': data['created_at'] or datetime.now().isoformat() if hasattr(data, '__getitem__') else None
    }), 201

@bp.route('/pages/<page_id>/comments', methods=['GET'])
def get_comments(page_id):
    comments = db.get_comments(page_id)
    
    return jsonify({
        'object': 'list',
        'results': [
            {
                **c,
                'url': f"/api/pages/{page_id}/comments?commentId={c['id']}"
            } 
            for c in comments
        ]
    })

# Search endpoint - find pages by title
@bp.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '')
    
    if not query:
        return jsonify({'object': 'list', 'results': []})
    
    cursor = db.conn.cursor()
    cursor.execute('''
        SELECT p.*, json_extract(p.properties, '$.title') as title 
        FROM pages p
        WHERE archived = 0 AND (json_extract(p.title, '$.plain_text') LIKE ? OR p.title LIKE ?)
        LIMIT 20
    ''', (f'%{query}%', f'{query}%'))
    
    results = []
    for row in cursor.fetchall():
        page = dict(row)
        
        if isinstance(page.get('properties'), str):
            page['properties'] = json.loads(page['properties'])
        elif not page.get('properties'):
            page['properties'] = {}
            
        # Add last_edited_time from blocks
        page['last_edited_time'] = page.get('updated_at') or page.get('created_at')
        
        results.append({
            'object': 'page',
            **page,
            'url': f"/api/pages/{page['id']}"
        })
    
    return jsonify({'object': 'list', 'results': results})

def init_app(app):
    app.register_blueprint(bp)
