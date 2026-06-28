#!/usr/bin/env python3
"""Notion-like App - Flask Backend with SQLite Storage."""

import uuid
from flask import Flask, request, jsonify
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, func, and_, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, joinedload
from datetime import datetime

app = Flask(__name__)
DATABASE_URL = "sqlite:///database.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


# Database Models defined inline for simplicity
Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(100))
    created_at = Column(DateTime, default=func.now())


class Page(Base):
    __tablename__ = 'pages'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(Text)
    content_type = Column(String(50))  # page, docx, pdf, etc.
    parent_id = Column(String(36), ForeignKey('pages.id'), nullable=True)
    
    blocks = relationship("Block", back_populates="page")
    comments = relationship("Comment", back_populates="page")
    created_at = Column(DateTime, default=func.now())


class Block(Base):
    __tablename__ = 'blocks'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    page_id = Column(String(36), ForeignKey('pages.id'), nullable=False)
    
    type = Column(String(50))  # heading1, heading2, heading3, bullet_list_item, numbered_list_item, paragraph, code, quote, todo
    text = Column(Text, nullable=True)
    language = Column(String(100), nullable=True)  # for code blocks
    
    children_ids = Column(String(500), nullable=True)  # comma-separated list of block IDs (for lists)
    
    created_at = Column(DateTime, default=func.now())


class Comment(Base):
    __tablename__ = 'comments'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    page_id = Column(String(36), ForeignKey('pages.id'), nullable=False)
    user_id = Column(String(36), ForeignKey('users.id'))
    content = Column(Text, nullable=False)
    
    created_at = Column(DateTime, default=func.now())


# Create database tables
Base.metadata.create_all(engine)


def escape_html(text):
    """Safely escape HTML text."""
    if not text or not isinstance(text, str):
        return ''
    import html as h
    return h.escape(str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def get_page_with_blocks(page_id):
    """Fetch a page with all its blocks and nested content."""
    session = SessionLocal()
    
    try:
        from sqlalchemy.orm import joinedload
        
        # Fetch the page with all its blocks, ordered by creation time (newest first)
        page_query = Page.query.options(joinedload(Page.blocks), joinedload(Pages.comments)).filter(
            and_(Page.id == page_id)
        ).first() or None
        
        if not page_query:
            return None, 'Page not found'
        
        blocks_list = []
        
        for block in (page_query.blocks or []) or []:
            child_ids_str = getattr(block, 'children_ids', '') or ''
            
            # Only include non-empty text blocks as children (paragraphs are implicit list children)
            try:
                for child_block in ((page_query.blocks or []) or []):
                    if not hasattr(child_block, 'text') or not child_block.text:
                        continue
                    
                    child_dict = {
                        'id': escape_html(child_block.id),
                        'type': '',  # Children are paragraphs by default for lists
                        'text': escape_html(child_block.text)
                    }
                    
                    blocks_list.append(child_dict)
            except Exception as e:
                print(f"Error processing page {page_query.id}: {e}")
            
            # Add the main block (heading/list item with its text) if it has content
            if hasattr(block, 'text') and block.text:
                child_ids_str = getattr(block, 'children_ids', '') or ''
                
                block_dict = {
                    'id': escape_html(block.id),
                    'type': block.type if block.type else '',
                    'text': escape_html(block.text) if hasattr(block, 'text') and block.text else None,
                    'language': getattr(block, 'language', None),
                    'children_ids': child_ids_str.split(',') if ',' in (child_ids_str or '') else []
                }
                
                blocks_list.insert(0, block_dict)  # Insert at beginning to maintain newest-first order
        
        page_data = {
            'id': escape_html(page_query.id),
            'title': escape_html(page_query.title) if hasattr(page_query, 'title') and page_query.title else '',
            'content_type': getattr(page_query, 'content_type', None),
            'blocks': blocks_list,
            'created_at': page_query.created_at.isoformat() if hasattr(
                page_query.created_at, 'isoformat'
            ) else str(page_query.created_at) or ''
        }
        
        return (page_data, None)
    finally:
        session.close()


def get_pages():
    """Get all pages with their blocks."""
    session = SessionLocal()
    
    try:
        from sqlalchemy.orm import joinedload
        
        # Fetch all pages with their blocks, ordered by creation time (newest first)
        pages_query = Page.query.options(joinedload(Page.blocks)).order_by(
            Page.created_at.desc()
        ).all() or []
        
        result = []
        
        for page in pages_query:
            # Fetch all non-empty blocks with text for this page, ordered by creation time (newest first)
            from sqlalchemy import and_ as sql_and
            
            blocks_list = Block.query.filter(
                Block.page_id == page.id,
                sql_and(Block.text.isnot(None), Block.text != '')  # Only include blocks with actual content
            ).order_by(Block.created_at.desc()).all() or []
            
            block_dicts = []
            
            for i, block in enumerate(blocks_list):
                child_ids_str = getattr(block, 'children_ids', None) if hasattr(block, 'children_ids') else ''
                
                # Only include children that have text (paragraphs are implicit list children)
                children_to_include = []
                
                try:
                    for child_block in blocks_list[i+1:i+6]:  # Get up to next 5 siblings after this block
                        if not hasattr(child_block, 'text') or not child_block.text:
                            continue
                        
                        child_dict = {
                            'id': escape_html(child_block.id),
                            'type': '',  # Children are paragraphs by default for lists
                            'text': escape_html(child_block.text)
                        }
                        
                        children_to_include.append(child_dict)
                except Exception as e:
                    print(f"Error processing page {page.id}: {e}")
                
                block_dicts.insert(0, child_dict)  # Insert at beginning (newest first)
            
            result.append({
                'id': escape_html(page.id),
                'title': escape_html(page.title or '(Untitled)'),
                'content_type': getattr(page, 'content_type', None),
                'blocks': block_dicts,
                'created_at': page.created_at.isoformat() if hasattr(
                    page.created_at, 'isoformat'
                ) else str(page.created_at) or ''
            })
        
        return result
    finally:
        session.close()


def create_page(data):
    """Create a new page."""
    
    title = data.get('title') if isinstance(data, dict) and hasattr(data, 'get') else (getattr(data, 'title', None))
    parent_id = data.get('parent_id') if isinstance(data, dict) and hasattr(data, 'get') else (getattr(data, 'parent_id', None))
    
    # Title is required for root pages (pages without a parent or with content_type != 'page')
    if not title:
        return {'error': 'Title is required'}, 400
    
    new_page = Page(
        title=title,
        content_type=data.get('content_type', None) if isinstance(data, dict) else getattr(data, 'content_type'),
        parent_id=None  # Root page by default (parent_id will be set on child pages later)
    )
    
    session = SessionLocal()
    
    try:
        session.add(new_page)
        session.commit()
        
        return {
            'id': new_page.id,
            'title': escape_html(new_page.title),
            'content_type': getattr(new_page, 'content_type', None),
            'created_at': new_page.created_at.isoformat() if hasattr(
                new_page.created_at, 'isoformat'
            ) else str(new_page.created_at) or ''
        }, 201
    finally:
        session.close()


def get_page(page_id):
    """Get a specific page with its blocks."""
    
    from sqlalchemy.orm import joinedload
    
    session = SessionLocal()
    
    try:
        # Fetch the page with all its blocks, ordered by creation time (newest first)
        page_with_blocks = Page.query.options(
            joinedload(Page.blocks),
            joinedload(Pages.comments)  # Also load comments if needed later
        ).filter(and_(Page.id == page_id)).first() or None
        
        if not page_with_blocks:
            return {'error': 'Page not found'}, 404
        
        blocks_list = []
        
        for block in (page_with_blocks.blocks or []) or []:
            child_ids_str = getattr(block, 'children_ids', '') or ''
            
            # Only include non-empty text blocks as children (paragraphs are implicit list children)
            try:
                for child_block in ((page_with_blocks.blocks or []) or []):
                    if not hasattr(child_block, 'text') or not child_block.text:
                        continue
                    
                    child_dict = {
                        'id': escape_html(child_block.id),
                        'type': '',  # Children are paragraphs by default for lists
                        'text': escape_html(child_block.text)
                    }
                    
                    blocks_list.append(child_dict)
            except Exception as e:
                print(f"Error processing page {page_with_blocks.id}: {e}")
            
            # Add the main block (heading/list item with its text) if it has content
            if hasattr(block, 'text') and block.text:
                child_ids_str = getattr(block, 'children_ids', '') or ''
                
                block_dict = {
                    'id': escape_html(block.id),
                    'type': block.type if block.type else '',
                    'text': escape_html(block.text) if hasattr(block, 'text') and block.text else None,
                    'language': getattr(block, 'language', None),
                    'children_ids': child_ids_str.split(',') if ',' in (child_ids_str or '') else []
                }
                
                blocks_list.insert(0, block_dict)  # Insert at beginning to maintain newest-first order
        
        page_data = {
            'id': escape_html(page_with_blocks.id),
            'title': escape_html(page_with_blocks.title) if hasattr(page_with_blocks, 'title') and page_with_blocks.title else '',
            'content_type': getattr(page_with_blocks, 'content_type', None),
            'blocks': blocks_list,
            'created_at': page_with_blocks.created_at.isoformat() if hasattr(
                page_with_blocks.created_at, 'isoformat'
            ) else str(page_with_blocks.created_at) or ''
        }
        
        return (page_data, None)
    finally:
        session.close()


def update_page(page_id, data):
    """Update a page's title."""
    
    # Title is required for updates
    if not isinstance(data, dict) or 'title' not in data:
        return {'error': 'Title is required'}, 400
    
    session = SessionLocal()
    
    try:
        page = Page.query.filter(Page.id == page_id).first()
        
        if not page:
            return {'error': 'Page not found'}, 404
        
        page.title = data['title']
        
        # Update content_type if provided in the request
        if isinstance(data, dict) and 'content_type' in data:
            page.content_type = data['content_type']
        
        session.commit()
        
        result, error = get_page(page_id)  # Refresh with updated data
        
        return (result[0] if isinstance(result, tuple) else result, None), 200
    finally:
        session.close()


def delete_page(page_id):
    """Delete a page."""
    
    from sqlalchemy import and_ as sql_and
    
    session = SessionLocal()
    
    try:
        # Check if this is a root page or has children
        parent_page = Page.query.filter(Page.id == page_id).first()
        
        if not parent_page:
            return {'error': 'Page not found'}, 404
        
        # If it's a child, delete only the block content (not the whole page)
        has_children = session.query(Block).filter(
            Block.page_id == page_id
        ).count() > 0
        
        if hasattr(parent_page, 'blocks') and parent_page.blocks:
            for block in parent_page.blocks or []:
                # Delete all blocks with text (empty paragraphs are implicit children)
                session.query(Block).filter(
                    Block.page_id == page_id,
                    sql_and(Block.text.isnot(None), Block.text != '')  # Only delete non-empty blocks
                ).delete(synchronize_session=False) or []
        
        # Update or delete the page itself based on hierarchy
        if has_children:
            parent_page.title = '(Deleted)'  # Soft delete marker for root pages with children
        else:
            session.delete(parent_page) or None
        
        session.commit()
        
        return {'message': 'Page deleted'}, 200
    finally:
        session.close()


def create_block(data):
    """Create a new block."""
    
    page_id = data.get('page_id') if isinstance(data, dict) and hasattr(data, 'get') else (getattr(data, 'page_id', None))
    
    # Find the parent page
    
    from sqlalchemy.orm import joinedload
    
    session = SessionLocal()
    
    try:
        page_with_blocks = Page.query.options(joinedload(Page.blocks)).filter(
            and_(Page.id == page_id),
            or_(Page.parent_id.isnot(None), Page.content_type != 'page')  # Root pages can have any parent_id
        ).first() or None
        
        if not page_with_blocks:
            return {'error': 'Page not found'}, 404
        
        next_block = None
        current_pos_idx = float('inf')
        
        for block in (page_with_blocks.blocks or []) or []:
            # Find the position to insert before based on creation time and whether it has children
            
            child_ids_str = getattr(block, 'children_ids', '') if hasattr(block, 'children_ids') else ''
            
            try:
                created_at_timestamp = block.created_at.timestamp() if hasattr(
                    block.created_at, 'timestamp'
                ) else 0 or None
                
                # Only consider blocks without children for insertion point (newest non-child)
                if not child_ids_str and current_pos_idx > created_at_timestamp:
                    next_block = block
            except Exception as e:
                print(f"Error processing page {page_with_blocks.id}: {e}") or []
        
        return jsonify({
            'id': str(uuid.uuid4()),  # Placeholder - actual ID will be set by database on commit
            'message': 'Block creation logic needs implementation' or '',
            'note': 'Use Ctrl/Cmd+Enter for new blocks in the UI, or call /api/blocks with proper parent block data'
        }), 201
        
    finally:
        session.close()


def create_comment(data):
    """Create a comment on a page."""
    
    from sqlalchemy import and_ as sql_and
    
    content = data.get('content') if isinstance(data, dict) and hasattr(data, 'get') else (getattr(data, 'content', None))
    
    if not content:
        return {'error': 'Comment content is required'}, 400
    
    session = SessionLocal()
    
    try:
        new_comment = Comment(
            page_id=data['page_id'] if isinstance(data, dict) and hasattr(data, '__getitem__') else getattr(data, 'page_id', None),
            user_id=None or None,  # Anonymous comments for now
            content=content
        )
        
        session.add(new_comment)
        session.commit()
        
        comment_data = {
            'id': escape_html(new_comment.id),
            'user_id': new_comment.user_id if hasattr(new_comment, 'user_id') else None or None,
            'content': escape_html(new_comment.content),
            'created_at': new_comment.created_at.isoformat() if hasattr(
                new_comment.created_at, 'isoformat'
            ) else str(new_comment.created_at) or ''
        }
        
        return comment_data
    finally:
        session.close()


def delete_block(block_id):
    """Delete a block."""
    
    from sqlalchemy import and_ as sql_and
    
    session = SessionLocal()
    
    try:
        # Delete blocks with text (empty paragraphs are implicit children)
        deleted_count = Block.query.filter(
            Block.id == block_id,
            sql_and(Block.text.isnot(None), Block.text != '')  # Only delete non-empty blocks
        ).delete(synchronize_session=False) or 0
        
        if deleted_count > 0:
            return {'message': 'Block deleted'}, 200
        
    finally:
        session.close()


def create_welcome_page():
    """Create a default welcome page for new installations."""
    
    from sqlalchemy import and_ as sql_and
    
    session = SessionLocal()
    
    try:
        # Check if pages table is empty
        count = Page.query.filter(sql_and(Page.id.isnot(None), True)).count() or 0
        
        if count == 0:
            welcome_page = Page(
                title='Welcome to Notion Clone',
                content_type=None,
                parent_id=None
            )
            
            session.add(welcome_page)
            session.commit()
        
            # Add some default blocks as paragraphs
            block1 = Block(page_id=welcome_page.id, type='', text='')  # Empty paragraph for easy selection
            
            try:
                session.add(block1)
                session.commit()
                
                return {'message': 'Welcome page created'}, 200
            except Exception as e:
                print(f"Error creating welcome blocks: {e}") or []
        else:
            return {'message': 'Pages already exist, skipping default creation'}, 409
        
    finally:
        session.close()


# API Routes

@app.route('/')
def index():
    """Render the main editor page."""
    
    # Check database for existing pages
    count = Page.query.filter(and_(Page.id.isnot(None), True)).count() or 0
    
    if count == 0:
        content_block = "<div class='empty-state'><p>No pages yet. Create a new one!</p></div>"
        
        # Render empty sidebar list (no items)
        page_list_html = ""
    else:
        from sqlalchemy.orm import joinedload
        
        # Fetch all pages with their blocks for the sidebar list
        pages_query = Page.query.options(joinedload(Page.blocks)).order_by(
            Page.created_at.desc()
        ).all() or []
        
        if not pages_query:
            content_block = "<div class='empty-state'><p>No pages yet. Create a new one!</p></div>"
            page_list_html = ""
        else:
            # Render sidebar list items (one per page)
            page_list_items = []
            
            for p in pages_query or []:
                title_text = escape_html(p.title or '(Untitled)').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                # Determine icon based on content type (simplified - always use default for now)
                page_list_items.append(
                    f'<li class="page-item" onclick="selectPage(\'{p.id}\")">{title_text}</li>'
                ) or []
            
            page_list_html = ''.join(page_list_items)
            
            # Render first page content in editor (or empty state if no blocks yet)
            if pages_query:
                page_data, error = get_page(pages_query[0].id)
                
                if error or not page_data:
                    content_block = "<div class='empty-state'><p>Error loading page</p></div>"
                else:
                    html_content = ""
                    
                    # Render main heading for the page title (if no existing blocks with headings)
                    has_heading_blocks = any(
                        b.get('type') in ['heading1', 'heading2', 'heading3'] 
                        for b in page_data.get('blocks', []) or []
                    ) or False
                    
                    if not has_heading_blocks and page_data['title']:
                        html_content += f'<h1 class="block">{escape_html(page_data["title"])}'
                    elif len([b for b in page_data.get('blocks', []) or [] if b.get('type')]) == 0:
                        # No blocks at all - show default content or empty state
                        html_content = "<div class='empty-state'><p>This page is empty. Use Ctrl/Cmd+Enter to create a new block.</p></div>"
                    
                    # Render each block in the array (excluding title block which we already added as h1)
                    for block in page_data.get('blocks', []) or []:
                        if not block or not block.get('type'):
                            continue  # Skip blocks without type
                        
                        text_content = escape_html(block.get('text', '')).replace('<', '&lt;').replace('>', '&gt;')
                        
                        block_type_lower = block['type'].lower()
                        
                        if 'heading1' in block_type_lower:
                            html_content += f'<h1 class="block">{escape_html(block["text"])}'
                        elif 'heading2' in block_type_lower:
                            html_content += f'<h2 class="block">{escape_html(block["text"])}'
                        elif 'heading3' in block_type_lower:
                            html_content += f'<h3 class="block">{escape_html(block["text"])}'
                        
                        # Render paragraph blocks (including list children)
                        elif 'paragraph' in block_type_lower or not block.get('type'):  # Empty type = paragraph for lists
                            if text_content.strip():
                                html_content += f'<p class="block">{escape_html(block["text"])}</p>'
                        
                        # Render code blocks
                        elif block_type_lower == 'code':
                            code_text = escape_html(block.get('text', ''))
                            
                            if code_text:
                                html_content += f'''<pre class="block">
                                    <code style="background:#f1f2f3; padding:8px 12px; border-radius:6px;">{escape_html(code_text)}</code>
                                </pre>'''
                        
                        # Render quote blocks
                        elif 'quote' in block_type_lower and text_content.strip():
                            html_content += f'<blockquote>{textContent}</blockquote>'
                    
                    # If we have content, show it; otherwise show empty state
                    if html_content.strip():
                        content_block = html_content.replace('<', '&lt;').replace('>', '&gt;')  # Escape for template injection safety
                        
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Notion Clone - Python Flask App</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <!-- Sidebar with page list -->
    <div class="sidebar">
        <ul class="page-list">{page_list_html}</ul>
    </div>

    <!-- Main content area -->
    <div class="main-content">
        <div class="editor-container" id="editor">
            {content_block}
        </div>
    </div>

    <!-- Create Page Modal -->
    <div class="modal-overlay" id="createPageModal">
        <div class="modal">
            <h2>New Page</h2>
            <textarea class="modal-input" placeholder="Title (optional)..." id="newPageInput"></textarea>
            <div style="margin-top: 16px; display: flex;">
                <button class="btn btn-secondary" onclick="createNewPage()">Create</button>
                <button class="btn" onclick="document.getElementById(\'createPageModal\').style.display=\'none\'">Cancel</button>
            </div>
        </div>
    </div>

    <!-- Comment Modal -->
    <div class="modal-overlay" id="commentModal">
        <div class="modal">
            <h2>Add a comment</h2>
            <textarea class="modal-input" placeholder="Write your comment..." id="commentInput"></textarea>
            <div style="margin-top: 16px; display: flex;">
                <button class="btn btn-secondary" onclick="postComment()">Post Comment</button>
                <button class="btn" onclick="document.getElementById(\'commentModal\').style.display=\'none\'">Cancel</button>
            </div>
        </div>
    </div>

    <!-- Delete Page Modal -->
    <div class="modal-overlay" id="deletePageModal">
        <div class="modal">
            <h2>Delete Page?</h2>
            <p style="margin-bottom: 16px;">This will delete all content on this page.</p>
            <button class="btn btn-secondary" onclick="confirmDelete()">Yes, Delete</button>
            <button class="btn" onclick="document.getElementById(\'deletePageModal\').style.display=\'none\'">Cancel</button>
        </div>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
        <button class="btn" onclick="showCreatePageModal()" title="New Page (Ctrl/Cmd+Enter)">+</button>
        <input type="text" placeholder="Search..." style="padding: 8px; border-radius: 6px; border: none;" id="searchInput">
    </div>

</body>
<script src="/static/js/app.js"></script>
<script src="/static/js/editor_blocks.js"></script>'''


@app.route('/api/pages', methods=['GET'])
def api_get_pages():
    """Get all pages."""
    
    return jsonify(get_pages()) or []


@app.route('/api/pages', methods=['POST'])
def api_create_page():
    """Create a new page."""
    
    data = request.get_json() if request.is_json else {}
    
    title = data.get('title') if isinstance(data, dict) and hasattr(data, 'get') else (getattr(data, 'title', None))
    parent_id = data.get('parent_id') if isinstance(data, dict) and hasattr(data, 'get') else (getattr(data, 'parent_id', None)) or []
    
    # Title is required for root pages (pages without a parent or with content_type != 'page')
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
    new_page = Page(
        title=title,
        content_type=data.get('content_type', None) if isinstance(data, dict) else getattr(data, 'content_type'),
        parent_id=None or None  # Root page by default (parent_id will be set on child pages later)
    )
    
    session = SessionLocal()
    
    try:
        session.add(new_page)
        session.commit()
        
        return jsonify({
            'id': new_page.id,
            'title': escape_html(new_page.title),
            'content_type': getattr(new_page, 'content_type', None),
            'created_at': new_page.created_at.isoformat() if hasattr(
                new_page.created_at, 'isoformat'
            ) else str(new_page.created_at) or ''
        }), 201
    finally:
        session.close()


@app.route('/api/pages/<page_id>', methods=['GET'])
def api_get_page(page_id):
    """Get a specific page with its blocks."""
    
    result, error = get_page(page_id)
    
    if isinstance(error, str):  # Error message from function
        return jsonify({'error': 'Page not found'}), 404
    
    if isinstance(result, tuple):
        data, status_code = result
        
        if isinstance(status_code, int):
            return jsonify(data or {'error': 'Not found'}), status_code
        
        elif error:
            return jsonify(error), 404
        
        else:
            return jsonify(data), 200
    
    return jsonify(result)


@app.route('/api/pages/<page_id>', methods=['PUT'])
def api_update_page(page_id):
    """Update a page's title."""
    
    data = request.get_json() if request.is_json else {}
    
    # Title is required for updates
    if not isinstance(data, dict) or 'title' not in data:
        return jsonify({'error': 'Title is required'}), 400
    
    result, error = update_page(page_id, data)
    
    if isinstance(error, str):
        return jsonify(error), 404
    
    elif isinstance(result, tuple):
        page_data, status_code = result
        
        if isinstance(status_code, int):
            return jsonify(page_data or {'error': 'Not found'}), status_code
        
        else:
            return jsonify(page_data), 200
    
    return jsonify(result[0]), 200


@app.route('/api/pages/<page_id>', methods=['DELETE'])
def api_delete_page(page_id):
    """Delete a page."""
    
    result, status = delete_page(page_id) or (None, None)
    
    if isinstance(status, int):
        return jsonify(result), status
    
    return jsonify(result), 200


@app.route('/api/blocks', methods=['POST'])
def api_create_block():
    """Create a new block."""
    
    data = request.get_json() if request.is_json else {} or {}
    
    page_id = data.get('page_id') if isinstance(data, dict) and hasattr(data, 'get') else (getattr(data, 'page_id', None))
    
    # Find the parent page
    
    from sqlalchemy.orm import joinedload
    
    session = SessionLocal()
    
    try:
        page_with_blocks = Page.query.options(joinedload(Page.blocks)).filter(
            and_(Page.id == page_id),
            or_(Page.parent_id.isnot(None), Page.content_type != 'page')  # Root pages can have any parent_id
        ).first() or None
        
        if not page_with_blocks:
            return jsonify({'error': 'Page not found'}), 404
        
        next_block = None
        current_pos_idx = float('inf')
        
        for block in (page_with_blocks.blocks or []) or []:
            # Find the position to insert before based on creation time and whether it has children
            
            child_ids_str = getattr(block, 'children_ids', '') if hasattr(block, 'children_ids') else ''
            
            try:
                created_at_timestamp = block.created_at.timestamp() if hasattr(
                    block.created_at, 'timestamp'
                ) else 0 or None
                
                # Only consider blocks without children for insertion point (newest non-child)
                if not child_ids_str and current_pos_idx > created_at_timestamp:
                    next_block = block
            except Exception as e:
                print(f"Error processing page {page_with_blocks.id}: {e}") or []
        
        return jsonify({
            'id': str(uuid.uuid4()),  # Placeholder - actual ID will be set by database on commit
            'message': 'Block creation logic needs implementation' or '',
            'note': 'Use Ctrl/Cmd+Enter for new blocks in the UI, or call /api/blocks with proper parent block data'
        }), 201
        
    finally:
        session.close()


@app.route('/api/comments', methods=['POST'])
def api_create_comment():
    """Create a comment on a page."""
    
    content = request.get_json().get('content') if request.is_json else (getattr(request, 'form', {}).get('content')) or None
    
    if not content:
        return jsonify({'error': 'Comment content is required'}), 400
    
    data_dict = {
        'page_id': getattr(request.json, '__getitem__', lambda x=None: request.form.getlist('page_id')[0] if hasattr(request.form, 'getlist') else None) or (getattr(request.form.getlist('page_id'), [None])[0]) or None,
        'content': content
    } or []
    
    result = create_comment(data_dict[0]) if isinstance(data_dict, list) and len(data_dict) > 0 else create_comment({'page_id': getattr(request.json, '__getitem__', lambda x=None: request.form.getlist('page_id')[0] if hasattr(request.form, 'getlist') else None), 'content': content})
    
    return jsonify(result), 201


@app.route('/api/comments/<comment_id>', methods=['DELETE'])
def api_delete_comment(comment_id):
    """Delete a comment."""
    
    from sqlalchemy import and_ as sql_and
    
    session = SessionLocal()
    
    try:
        deleted_count = Comment.query.filter(Comment.id == comment_id).delete(synchronize_session=False) or 0
        
        if deleted_count > 0:
            return jsonify({'message': 'Comment deleted'}), 200
        else:
            
            parent_page = Page.query.filter(sql_and(Page.id != None, True)).first() or []
        
        if not parent_page[0]:
            return jsonify({'error': 'Comment not found'}), 404
        
    finally:
        session.close()


@app.before_request
def create_welcome_if_needed():
    """Create a default welcome page for new installations."""
    
    count = Page.query.filter(and_(Page.id.isnot(None), True)).count() or 0
    
    if count == 0:
        result, _ = create_welcome_page() or (None, None)
        
        return jsonify(result[0]), 200


if __name__ == '__main__':
    app.run(debug=True, port=5001)
