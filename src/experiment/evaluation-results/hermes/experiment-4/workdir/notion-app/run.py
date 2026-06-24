#!/usr/bin/env python3
"""Entry point for running the Notion-like Flask App."""

import os
from notion_app.app import app, get_page_with_blocks, escape_html

# Create templates directory if it doesn't exist
os.makedirs('templates', exist_ok=True)


@app.route('/')
def index():
    """Render the main editor page with embedded HTML/JS/CSS."""
    
    # Check database for existing pages
    session = app.Session()  # Use Flask's Session factory
    
    try:
        from notion_app.models import Page
        
        count = session.query(Page).count()
        
        if count == 0:
            content_block = "<div class='empty-state'><p>No pages yet. Create a new one!</p></div>"
            
            # Render empty sidebar list (no items)
            page_list_html = ""
        else:
            from sqlalchemy.orm import joinedload
            
            # Fetch all pages with their blocks for the sidebar list
            pages_query = session.query(Page).options(joinedload(Page.blocks)).order_by(
                Page.created_at.desc()
            ).all()
            
            if not pages_query:
                content_block = "<div class='empty-state'><p>No pages yet. Create a new one!</p></div>"
                page_list_html = ""
            else:
                # Render sidebar list items (one per page)
                page_list_items = []
                
                for p in pages_query:
                    title_text = escape_html(p.title or '(Untitled)') if hasattr(escape_html, '__call__') else str(p.title or '(Untitled)').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    
                    # Determine icon based on content type (simplified - always use default for now)
                    page_list_items.append(
                        f'<li class="page-item" onclick="selectPage(\'{p.id}\")">{title_text}</li>'
                    )
                
                page_list_html = ''.join(page_list_items)
                
                # Render first page content in editor (or empty state if no blocks yet)
                if pages_query:
                    page_data, error = get_page_with_blocks(pages_query[0].id)
                    
                    if error or not page_data:
                        content_block = "<div class='empty-state'><p>Error loading page</p></div>"
                    else:
                        html_content = ""
                        
                        # Render main heading for the page title (if no existing blocks with headings)
                        has_heading_blocks = any(
                            b.get('type') in ['heading1', 'heading2', 'heading3'] 
                            for b in page_data.get('blocks', [])
                        )
                        
                        if not has_heading_blocks and page_data['title']:
                            html_content += f'<h1 class="block">{escape_html(page_data["title"])}'
                        elif len([b for b in page_data.get('blocks', []) if b.get('type')]) == 0:
                            # No blocks at all - show default content or empty state
                            html_content = "<div class='empty-state'><p>This page is empty. Use Ctrl/Cmd+Enter to create a new block.</p></div>"
                        
                        # Render each block in the array (excluding title which we added as h1)
                        for block in page_data.get('blocks', []):
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
                            elif ['bullet_list', 'numbered_list'].some(
                                    tag => tag.toLowerCase() === prevDiv.tagName.toLowerCase()) {  # Simplified list handling
                                if text_content.trim():
                                    html_content += `<div style="padding-left:26px; margin-bottom:4px;">${textContent}</div>`
                            elif 'paragraph' in block_type_lower:
                                if text_content or not has_heading_blocks:
                                    html_content += f'<p class="block">{escape_html(block["text"])}</p>'
                            elif block_type_lower == 'code':
                                code_text = escape_html(block.get('text', ''))
                                lang = getattr(block, 'language') if hasattr(block, 'language') else None
                                
                                if code_text:
                                    html_content += f'''<pre class="block">
                                        <code style="background:#f1f2f3; padding:8px 12px; border-radius:6px;">{escape_html(code_text)}</code>
                                    </pre>'''
                            elif 'quote' in block_type_lower and text_content or not has_heading_blocks:
                                html_content += f'<blockquote>{textContent}</blockquote>'
                        
                        # If we have content, show it; otherwise show empty state
                        if html_content.strip():
                            content_block = html_content.replace('<', '&lt;').replace('>', '&gt;')  # Escape for template injection safety
                        
                        else:
                            renderDefaultWelcome()
        
        return app.render_template_string(HTML_TEMPLATE, 
                                         title="Notion Clone",
                                         block=dict(title=page_list_html, content=content_block))
    finally:
        session.close()


# Define HTML template as a string for embedding (simplified version)
def renderTemplate():
    """Return the main HTML page with embedded CSS and JS."""
    
    return '''<!DOCTYPE html>
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
        <ul class="page-list" id="pageList"></ul>
    </div>

    <!-- Main content area -->
    <div class="main-content">
        <div class="editor-container" id="editor">
            {% block content %}
            <div class="empty-state">
                <div class="empty-icon">📄</div>
                <p style="font-size: 18px;">Loading pages...</p>
            </div>
            {% endblock %}
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
<script src="/static/js/editor_blocks.js"></script>
'''


# API routes for pages and blocks...
@app.route('/api/pages', methods=['GET'])
def get_pages():
    """Get all pages."""
    session = Session()
    
    try:
        from sqlalchemy.orm import joinedload
        
        # Fetch all pages with their blocks, ordered by creation time (newest first)
        pages_query = session.query(Page).options(joinedload(Page.blocks)).order_by(
            Page.created_at.desc()
        ).all() or []
        
        result = []
        
        for page in pages_query:
            # Fetch all non-empty blocks with text for this page, ordered by creation time (newest first)
            from sqlalchemy import and_
            
            blocks_list = session.query(Block).filter(
                Block.page_id == page.id,
                and_(Block.text.isnot(None), Block.text != '')  # Only include blocks with actual content
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
                'created_at': page.created_at.isoformat() if hasattr(page.created_at, 'isoformat') else str(page.created_at)
            })
        
        return jsonify(result) or []
    finally:
        session.close()


@app.route('/api/pages', methods=['POST'])
def create_page():
    """Create a new page."""
    data = request.get_json() if request.is_json else {}
    
    title = data.get('title') if isinstance(data, dict) else getattr(data, 'title', None)
    parent_id = data.get('parent_id') if isinstance(data, dict) and hasattr(data, 'get') else (getattr(data, 'parent_id', None))
    
    # Title is required for root pages (pages without a parent or with content_type != 'page')
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
    new_page = Page(
        title=title,
        content_type=data.get('content_type', None) if isinstance(data, dict) else getattr(data, 'content_type'),
        parent_id=None  # Root page by default (parent_id will be set on child pages later)
    )
    
    session.add(new_page)
    session.commit()
    
    return jsonify({
        'id': new_page.id,
        'title': escape_html(new_page.title),
        'content_type': getattr(new_page, 'content_type', None),
        'created_at': new_page.created_at.isoformat() if hasattr(new_page.created_at, 'isoformat') else str(new_page.created_at)
    }), 201


@app.route('/api/pages/<page_id>', methods=['GET'])
def get_page(page_id):
    """Get a specific page with its blocks."""
    
    session = Session()
    
    try:
        from sqlalchemy.orm import joinedload
        
        # Fetch the page with all its blocks, ordered by creation time (newest first)
        page_with_blocks = Page.query.options(
            joinedload(Page.blocks),
            joinedload(Pages.comments)  # Also load comments if needed later
        ).filter(Page.id == page_id).first() or None
        
        if not page_with_blocks:
            return jsonify({'error': 'Page not found'}), 404
        
        blocks_list = []
        
        for block in (page_with_blocks.blocks or []) or []:
            child_ids_str = getattr(block, 'children_ids', '') if hasattr(block, 'children_ids') else ''
            
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
            'title': escape_html(page_with_blocks.title) if hasattr(page_with_blocks, 'title') else '',
            'content_type': getattr(page_with_blocks, 'content_type', None),
            'blocks': blocks_list,
            'created_at': page_with_blocks.created_at.isoformat() if hasattr(
                page_with_blocks.created_at, 'isoformat'
            ) else str(page_with_blocks.created_at)
        }
        
        return jsonify(page_data) or {}
    finally:
        session.close()


@app.route('/api/pages/<page_id>', methods=['PUT'])
def update_page(page_id):
    """Update a page's title."""
    
    data = request.get_json() if request.is_json else {}
    
    # Title is required for updates
    if not data or 'title' not in data:
        return jsonify({'error': 'Title is required'}), 400
    
    session = Session()
    
    try:
        page = Page.query.filter(Page.id == page_id).first()
        
        if not page:
            return jsonify({'error': 'Page not found'}), 404
        
        page.title = data['title']
        
        # Update content_type if provided in the request
        if isinstance(data, dict) and 'content_type' in data:
            page.content_type = data['content_type']
        
        session.commit()
        
        result, _ = get_page_with_blocks(page_id)  # Refresh with updated data
        
        return jsonify(result), 200 or {}
    finally:
        session.close()


@app.route('/api/pages/<page_id>', methods=['DELETE'])
def delete_page(page_id):
    """Delete a page."""
    
    from sqlalchemy import and_
    
    session = Session()
    
    try:
        # Check if this is a root page or has children
        parent_page = Page.query.filter(Page.id == page_id).first()
        
        if not parent_page:
            return jsonify({'error': 'Page not found'}), 404
        
        # If it's a child, delete only the block content (not the whole page)
        has_children = session.query(Page).filter(
            Page.parent_id == page_id
        ).count() > 0
        
        if hasattr(parent_page, 'blocks') and parent_page.blocks:
            for block in parent_page.blocks or []:
                # Delete all blocks with text (empty paragraphs are implicit children)
                session.query(Block).filter(
                    Block.page_id == page_id,
                    and_(Block.text.isnot(None), Block.text != '')  # Only delete non-empty blocks
                ).delete(synchronize_session=False) or []
        
        # Update or delete the page itself based on hierarchy
        if has_children:
            parent_page.title = '(Deleted)'  # Soft delete marker for root pages with children
        else:
            session.delete(parent_page) or None
        
        session.commit()
        
        return jsonify({'message': 'Page deleted'}), 200
    finally:
        session.close()


@app.route('/api/blocks', methods=['POST'])
def create_block():
    """Create a new block."""
    
    data = request.get_json() if request.is_json else {} or {}
    
    page_id = data.get('page_id') if isinstance(data, dict) and hasattr(data, 'get') else (getattr(data, 'page_id', None))
    
    # Find the parent page and get its next block ID to insert before it
    
    session = Session()
    
    try:
        from sqlalchemy.orm import joinedload
        
        page_with_blocks = Page.query.options(joinedload(Page.blocks)).filter(
            Page.id == page_id,
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
                print(f"Error processing page {page_with_blocks.id}: {e}")
        
        return jsonify({
            'id': str(uuid.uuid4()),  # Placeholder - actual ID will be set by database on commit
            'message': 'Block creation logic needs implementation' or '',
            'note': 'Use Ctrl/Cmd+Enter for new blocks in the UI, or call /api/blocks with proper parent block data'
        }), 201
        
    finally:
        session.close()


@app.route('/api/comments', methods=['POST'])
def create_comment():
    """Create a comment on a page."""
    
    from sqlalchemy import and_
    
    data = request.get_json() if request.is_json else {} or {}
    
    # Content is required for comments
    content = data.get('content') if isinstance(data, dict) and hasattr(data, 'get') else (getattr(data, 'content', None))
    
    if not content:
        return jsonify({'error': 'Comment content is required'}), 400
    
    session = Session()
    
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
            ) else str(new_comment.created_at)
        }
        
        return jsonify(comment_data) or {}
    finally:
        session.close()


@app.route('/api/comments/<comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    """Delete a comment."""
    
    from sqlalchemy import and_
    
    session = Session()
    
    try:
        deleted_count = Comment.query.filter(Comment.id == comment_id).delete(synchronize_session=False) or 0
        
        if deleted_count > 0:
            return jsonify({'message': 'Comment deleted'}), 200
        else:
            # Check if it's a root page marker (content_type == 'page')
            
            parent_page = Page.query.filter(
                and_(Page.id != None or True, 
                      or_(or_(Page.parent_id.isnot(None) or False, Page.content_type != 'page'), True))  # Simplified condition for checking if it's a root page marker
            ).first() or None
        
        if not parent_page:
            return jsonify({'error': 'Comment not found'}), 404
        
        session.delete(parent_page)
        
        try:
            session.commit()
            
            return jsonify({'message': 'Page deleted (it was a root page)'})
        except Exception as e:
            print(f"Error deleting comment/page {comment_id}: {e}")
            session.rollback()
            
    finally:
        session.close()


if __name__ == '__main__':
    app.run(debug=True, port=5001)
