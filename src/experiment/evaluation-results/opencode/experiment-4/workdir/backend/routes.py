from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
import json

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/api/pages', methods=['POST'])
def create_page():
    """Create a new page"""
    data = request.json
    
    if not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400

    session = Session()
    
    try:
        parent_id = data.get('parent_page_id')
        
        # Check for duplicate title at same level (simple duplicate check)
        if not parent_id or parent_id == -1:
            existing_count = session.query(Page).filter_by(title=data['title']).count()
            if existing_count > 0:
                return jsonify({'error': 'Page with this title already exists'}), 409

        page = Page(
            title=data['title'],
            content=data.get('content', ''),
            parent_page_id=parent_id or None,
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
        
        session.add(page)
        session.commit()
        
        return jsonify({
            'id': page.id,
            'title': page.title,
            'content': page.content,
            'parent_page_id': parent_id or None,
            'created_at': page.created_at.isoformat(),
            'updated_at': page.updated_at.isoformat() if page.updated_at else None
        }), 201
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    
    finally:
        session.close()


@pages_bp.route('/api/pages/<int:page_id>', methods=['GET'])
def get_page(page_id):
    """Get a page by ID"""
    session = Session()
    
    try:
        page = session.query(Page).filter_by(id=page_id).first_or_404()
        
        return jsonify({
            'id': page.id,
            'title': page.title,
            'content': page.content,
            'parent_page_id': page.parent_page_id,
            'created_at': page.created_at.isoformat(),
            'updated_at': page.updated_at.isoformat() if page.updated_at else None,
            'blocks': [
                {
                    'id': block.id,
                    'type': block.type,
                    'data': block.data,
                    'created_at': block.created_at.isoformat() if block.created_at else None
                }
                for block in page.blocks
            ]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    finally:
        session.close()


@pages_bp.route('/api/pages', methods=['GET'])
def get_pages():
    """Get all pages (optionally paginated)"""
    page = request.args.get('page', '1')
    per_page = request.args.get('per_page', 20, type=int)
    
    session = Session()
    
    try:
        offset = int(page) - 1
        
        total = session.query(Page).count()
        pages = session.query(Page).offset(offset).limit(per_page).all()
        
        return jsonify({
            'pages': [
                {
                    'id': p.id,
                    'title': p.title,
                    'content': p.content[:50] + '...' if len(p.content) > 50 else p.content,
                    'parent_page_id': p.parent_page_id or None,
                    'created_at': p.created_at.isoformat() if p.created_at else None,
                    'updated_at': p.updated_at.isoformat() if p.updated_at and hasattr(p.updated_at, 'isoformat') else str(p.updated_at)
                }
                for p in pages
            ],
            'total': total,
            'page': int(page),
            'per_page': per_page
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    finally:
        session.close()


@pages_bp.route('/api/pages/<int:page_id>', methods=['PUT'])
def update_page(page_id):
    """Update a page"""
    data = request.json

    if not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400
    
    session = Session()
    
    try:
        page = session.query(Page).filter_by(id=page_id).first_or_404()
        
        page.title = data['title']
        if 'content' in data:
            page.content = data['content']
            
        page.updated_at = datetime.utcnow()
        
        session.commit()
        
        return jsonify({
            'id': page.id,
            'title': page.title,
            'content': page.content,
            'parent_page_id': page.parent_page_id,
            'updated_at': page.updated_at.isoformat() if page.updated_at else None
        }), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    
    finally:
        session.close()


@pages_bp.route('/api/pages/<int:page_id>', methods=['DELETE'])
def delete_page(page_id):
    """Delete a page"""
    session = Session()
    
    try:
        page = session.query(Page).filter_by(id=page_id).first_or_404()
        
        # Delete associated blocks first (cascade)
        for block in page.blocks:
            session.delete(block)
        
        session.delete(page)
        session.commit()
        
        return jsonify({'message': 'Page deleted successfully'}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    
    finally:
        session.close()


@pages_bp.route('/api/pages/<int:page_id>/blocks', methods=['POST'])
def create_block(page_id):
    """Create a new block for a page"""
    data = request.json
    
    if not page_id or not isinstance(page_id, int):
        return jsonify({'error': 'Invalid page ID'}), 400

    session = Session()
    
    try:
        # Verify page exists
        page = session.query(Page).filter_by(id=page_id).first_or_404()
        
        block_type = data.get('type', 'paragraph')
        block_data = json.dumps(data.get('data', {})) if isinstance(data.get('data'), dict) else str(data.get('data', ''))

        block = Block(
            page_id=page_id,
            type=block_type,
            data=block_data or '',
            created_at=data.get('created_at')
        )
        
        session.add(block)
        session.commit()
        
        return jsonify({
            'id': block.id,
            'type': block.type,
            'data': block.data if isinstance(block.data, str) else json.loads(block.data),
            'page_id': page_id,
            'created_at': block.created_at.isoformat() if block.created_at else None
        }), 201
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    
    finally:
        session.close()


@pages_bp.route('/api/pages/<int:page_id>/blocks', methods=['GET'])
def get_blocks(page_id):
    """Get all blocks for a page"""
    session = Session()
    
    try:
        # Verify page exists first
        page = session.query(Page).filter_by(id=page_id).first_or_404()
        
        blocks = session.query(Block).filter_by(page_id=page_id).order_by(Block.id.desc()).all()
        
        return jsonify({
            'blocks': [
                {
                    'id': b.id,
                    'type': b.type,
                    'data': json.loads(b.data) if isinstance(b.data, str) and len(b.data) > 0 else {},
                    'created_at': b.created_at.isoformat() if b.created_at else None
                }
                for b in blocks
            ],
            'page_id': page_id
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    finally:
        session.close()


@pages_bp.route('/api/pages/<int:page_id>/blocks/<int:block_id>', methods=['PUT'])
def update_block(page_id, block_id):
    """Update a block"""
    data = request.json

    if not page_id or not isinstance(page_id, int):
        return jsonify({'error': 'Invalid page ID'}), 400
    
    session = Session()
    
    try:
        # Verify both exist and belong to same page
        block = session.query(Block).filter_by(id=block_id, page_id=page_id).first_or_404()
        
        if 'type' in data:
            block.type = data['type']
            
        if 'data' in data:
            new_data = json.dumps(data['data']) if isinstance(data.get('data'), dict) else str(data['data'])
            block.data = new_data
        
        session.commit()
        
        return jsonify({
            'id': block.id,
            'type': block.type,
            'data': block.data if isinstance(block.data, str) and len(block.data) > 0 else json.loads(block.data),
            'page_id': page_id,
            'created_at': block.created_at.isoformat() if block.created_at else None
        }), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    
    finally:
        session.close()


@pages_bp.route('/api/pages/<int:page_id>/blocks/<int:block_id>', methods=['DELETE'])
def delete_block(page_id, block_id):
    """Delete a block"""
    if not page_id or not isinstance(page_id, int):
        return jsonify({'error': 'Invalid page ID'}), 400
    
    session = Session()
    
    try:
        # Verify both exist and belong to same page
        block = session.query(Block).filter_by(id=block_id, page_id=page_id).first_or_404()
        
        session.delete(block)
        session.commit()
        
        return jsonify({'message': 'Block deleted successfully'}), 200
        
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    
    finally:
        session.close()
