"""
Flask application factory for Notion-like text blocks API.
Implements RESTful endpoints: GET /blocks, POST /blocks, PUT /blocks/<id>, DELETE /blocks/<id>
"""

import os
from flask import Flask, request, jsonify
from database.database import (
    init_db, get_all_blocks, create_block, update_block, delete_block
)


def create_app():
    """Flask application factory."""
    app = Flask(__name__)
    app.config['JSON_SORT_KEYS'] = False
    
    # Initialize database on startup
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'blocks.db')
    init_db()
    
    @app.route('/blocks', methods=['GET'])
    def list_blocks():
        """List all blocks."""
        try:
            conn = app.app_context().push()
            blocks = get_all_blocks()
            return jsonify({
                'success': True,
                'count': len(blocks),
                'blocks': blocks
            }), 200
        finally:
            app.app_context().pop()
    
    @app.route('/blocks', methods=['POST'])
    def create_block_endpoint():
        """Create a new block."""
        try:
            data = request.get_json()
            if not data or 'content' not in data:
                return jsonify({'success': False, 'error': 'Missing required field: content'}), 400
            
            content = data['content']
            
            block_id = create_block(content)
            
            if block_id is None:
                return jsonify({
                    'success': True,
                    'message': 'Block with this content already exists',
                    'id': None,
                    'content': content
                }), 201
            
            conn = app.app_context().push()
            blocks = get_all_blocks()
            block_data = [b for b in blocks if b['id'] == block_id][0]
            return jsonify({
                'success': True,
                'id': block_id,
                'content': block_data['content'],
                'created_at': block_data['created_at'],
                'updated_at': block_data['updated_at']
            }), 201
        finally:
            app.app_context().pop()
    
    @app.route('/blocks/<int:block_id>', methods=['PUT'])
    def update_block(block_id):
        """Edit a selected block."""
        try:
            data = request.get_json()
            if not data or 'content' not in data:
                return jsonify({'success': False, 'error': 'Missing required field: content'}), 400
            
            new_content = data['content']
            
            success = update_block(block_id, new_content)
            
            if not success:
                return jsonify({
                    'success': False,
                    'error': f'Block with id {block_id} not found'
                }), 404
            
            conn = app.app_context().push()
            blocks = get_all_blocks()
            block_data = [b for b in blocks if b['id'] == block_id][0]
            return jsonify({
                'success': True,
                'id': block_id,
                'content': block_data['content'],
                'updated_at': block_data['updated_at']
            }), 200
        finally:
            app.app_context().pop()
    
    @app.route('/blocks/<int:block_id>', methods=['DELETE'])
    def delete_block_endpoint(block_id):
        """Delete selected block."""
        try:
            success = delete_block(block_id)
            
            if not success:
                return jsonify({
                    'success': False,
                    'error': f'Block with id {block_id} not found'
                }), 404
            
            conn = app.app_context().push()
            blocks = get_all_blocks()
            return jsonify({
                'success': True,
                'message': f'Block with id {block_id} deleted successfully',
                'blocks_remaining': len(blocks)
            }), 200
        finally:
            app.app_context().pop()
    
    # Health check endpoint
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint."""
        return jsonify({'status': 'ok'}), 200
    
    return app


# Create application instance
app = create_app()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8765))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
