"""Flask Application for Notion-like App"""
import uuid
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, func, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, joinedload
from datetime import datetime

app = Flask(__name__)
DATABASE_URL = "sqlite:///../database.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


# Import models after engine is created
from notion_app.models import User, Page, Block, Comment, Base

Base.metadata.create_all(engine)


def escape_html(text):
    """Safely escape HTML text."""
    if not text:
        return ''
    result = str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    import html as h
    return h.escape(result)


def get_page_with_blocks(page_id):
    """Fetch a page with all its blocks and nested content."""
    session = Session()
    try:
        from sqlalchemy.orm import joinedload
        
        page_query = session.query(Page).options(
            joinedload(Page.blocks),
            joinedload(Pages.comments)
        ).filter(Page.id == page_id)
        
        pages = page_query.all()
        if not pages:
            return None, 'Page not found'
        
        page = pages[0]
        blocks_list = []
        
        for block in page.blocks or []:
            child_ids_str = getattr(block, 'children_ids', '') or ''
            
            block_dict = {
                'id': block.id,
                'type': block.type if block.type else '',
                'text': escape_html(block.text) if block.text else None,
                'language': getattr(block, 'language', None),
                'children_ids': child_ids_str.split(',') if child_ids_str and ',' in child_ids_str else []
            }
            
            # Fetch children for list items (paragraphs are implicit children of lists)
            if block.type in ['bullet_list_item', 'numbered_list_item']:
                try:
                    children = session.query(Block).filter(
                        Block.page_id == page.id,
                        and_(Block.text.isnot(None), Block.text != '')
                    ).order_by(Block.created_at.desc()).limit(10).all()
                    
                    for child in children[:5]:  # Limit to first 5 children
                        if not getattr(child.type, 'startswith', lambda x: False)(('paragraph',)):
                            continue
                        
                        child_dict = {
                            'id': child.id,
                            'type': '',  # Children are paragraphs by default for lists
                            'text': escape_html(child.text),
                            'children_ids': ''
                        }
                        
                        blocks_list.append(child_dict)
                except Exception:
                    pass
            
            blocks_list.insert(0, block_dict)
        
        page_data = {
            'id': page.id,
            'title': escape_html(page.title),
            'content_type': getattr(page, 'content_type', None),
            'blocks': blocks_list,
            'created_at': page.created_at.isoformat() if hasattr(page.created_at, 'isoformat') else str(page.created_at)
        }
        
        return (page_data, None)
    finally:
        session.close()


def get_content_type_icon(type_):
    """Get icon for content type."""
    icons = {'docx': '📄', 'pdf': '📘', None: '📄'}
    return icons.get(type_ or '', '📄')


# HTML Template with embedded CSS and JS
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Notion Clone{% endblock %}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            background-color: #ffffff;
            color: #37352f;
        }
        
        .sidebar {
            width: 260px;
            min-height: 100vh;
            border-right: 1px solid #e9e8eb;
            padding: 16px 0;
            position: fixed;
            left: 0;
        }
        
        .page-list { list-style: none; }
        
        .page-item {
            padding: 4px 12px 4px 28px;
            font-size: 15px;
            cursor: pointer;
            border-radius: 6px;
            color: #37352f;
        }
        
        .page-item:hover { background-color: #efefef; }
        
        .page-item.active {
            font-weight: 500;
            text-decoration: none;
            border-left: 3px solid #1a8917;
            color: #234e52;
        }
        
        .page-icon { margin-right: 6px; font-size: 18px; }
        
        .main-content {
            margin-left: 260px;
            min-height: 100vh;
            padding-top: 40px;
        }
        
        .editor-container { max-width: 950px; margin: 0 auto; padding: 32px 48px; }
        
        h1.block { font-size: 40px; line-height: 48px; font-weight: 700; margin-bottom: 16px;}
        
        .block { min-height: 24px; padding: 3px 0; outline: none; transition: background-color 0.1s ease; border-radius: 4px;}
        .block:focus { box-shadow: inset 0 -1px 0 #d0d7de, inset 0 -1px 0 rgba(255,255,255,.3); }
        
        h1.block { font-size: 40px; line-height: 48px; padding-bottom: 6px; border-bottom: 1px solid #e9e8eb; margin-top: 20px;}
        h2.block { font-size: 30px; line-height: 36px; margin-top: 16px; }
        h3.block { font-size: 24px; line-height: 28px; margin-top: 16px; }
        
        p.block { font-size: 16px; line-height: 1.5; min-height: 20px;}
        
        ul.block, ol.block { padding-left: 26px; list-style-position: inside; }
        li.block { margin-bottom: 4px; }
        
        code.block { 
            font-family: 'SFMono-Regular', Consolas, monospace; 
            background-color: #f1f2f3; 
            padding: 8px 12px; 
            border-radius: 6px;
            display: block;
            overflow-x: auto; white-space: pre-wrap; word-break: break-word;
        }
        
        code { font-family: monospace; background-color: #e9e7f5; padding: 2px 6px; border-radius: 3px;}
        
        pre.block { 
            margin-top: 0; 
            padding: 14px 16px; 
            border-radius: 8px; 
            background-color: #fafafa;
            font-size: 14px; line-height: 20px; overflow-x: auto; white-space: pre-wrap; word-break: break-word;
        }
        
        blockquote.block { 
            padding-left: 16px; border-left: 3px solid #e9e8eb; font-style: italic; color: #57534e; line-height: 1.5; min-height: 20px; margin-top: 0;}
        
        .toolbar { position: fixed; top: 16px; right: 16px; z-index: 100; }
        
        .btn { 
            background-color: #37352f; color: white; border: none; padding: 8px 16px; 
            font-size: 14px; cursor: pointer; min-width: 90px; margin-left: 8px;
        }
        
        .btn-secondary { background-color: #efefef; color: #37352f;}
        
        .search-box-container { position: relative; margin-bottom: 16px; }
        
        .search-input { 
            width: calc(100% - 48px); padding-left: 32px; border: none; background-color: #efefef; 
            font-size: 15px; outline: none; height: 36px; }
        
        .search-icon { position: absolute; left: 10px; top: 8px; color: #9b9a97;}
        
        .modal-overlay { 
            display: none; position: fixed; inset: 0; background-color: rgba(23,26,32,.5); z-index: 1000; align-items: center; justify-content: center; }
        
        .modal { 
            background: white; border-radius: 8px; width: calc(100% - 48px); max-width: 960px; max-height: 95vh; overflow-y: auto; padding: 24px; box-shadow: 0 0 30px rgba(0,0,0,.15);}
        
        .modal h2 { font-size: 20px; margin-bottom: 16px;}
        
        textarea.modal-input { 
            width: calc(100% - 48px); min-height: 30vh; border: none; outline: none; resize: vertical;
            background-color: #efefef; font-size: 15px; padding-left: 26px;}
        
        .modal-input:focus { box-shadow: inset 0 -1px 0 rgba(255,255,255,.3), inset 0 1px 0 rgba(87,83,78,.4);}
        
        .page-actions { margin-top: 16px; }
        
        .empty-state { text-align: center; padding: 80px 20px;}
        
        .empty-icon { font-size: 48px; color: #dfe3e9; margin-bottom: 16px;}
    </style>
</head>
<body>
    <div class="sidebar">
        <ul class="page-list" id="pageList"></ul>
    </div>
    
    <div class="main-content">
        <div class="editor-container" id="editor">
            {% block content %}
            <div class="empty-state">
                <div class="empty-icon">📄</div>
                <p style="font-size: 18px;">Select a page to start editing or create a new one.</p>
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
                <button class="btn" onclick="document.getElementById('createPageModal').style.display='none'">Cancel</button>
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
                <button class="btn" onclick="document.getElementById('commentModal').style.display='none'">Cancel</button>
            </div>
        </div>
    </div>

{% block scripts %}
    
<!-- Icons -->
<link href="https://cdn.jsdelivr.net/npm/font-awesome@4.7.0/css/font-awesome.min.css" rel="stylesheet">

<script>
const API_BASE = '/api';
let currentPageId = null;
let selectedBlockId = null;

document.addEventListener('DOMContentLoaded', async () => {
    await loadPages();
    
    // Add Enter key handler for blocks
    document.getElementById('editor').addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            createNewPage();
        } else if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            const block = getSelectedBlock(e.target);
            if (!block) return;
            
            let newType, newText;
            switch(block.type) {
                case 'paragraph': newType='heading2'; break;
                case 'bullet_list_item': newType='numbered_list_item'; break;
                default: newType = block.type.replace('1', '') + '_1' || (block.type === 'heading3' ? 'heading2_1' : 'heading2');
            }
            
            const nextBlockId = await insertNewBlock(block.id, newType);
            if (nextBlockId) {
                selectBlock(nextBlockId);
            }
        } else if (e.key === 'Backspace' && e.target.textContent.trim() === '') {
            deleteSelectedBlock();
        }
    });
    
});

async function loadPages() {
    const res = await fetch(`${API_BASE}/pages`);
    const pages = await res.json();
    renderPageList(pages);
    
    if (pages.length > 0) {
        currentPageId = pages[0].id;
        selectPage(currentPageId);
    }
}

function renderPageList(pages) {
    const list = document.getElementById('pageList');
    list.innerHTML = '';
    
    pages.forEach(page => {
        const li = document.createElement('li');
        li.className = `page-item ${currentPageId === page.id ? 'active' : ''}`;
        li.textContent = page.title || '(Untitled)';
        li.onclick = () => selectPage(page.id);
        
        if (page.content_type) {
            const iconSpan = document.createElement('span');
            iconSpan.className = 'page-icon';
            iconSpan.innerHTML = getContentTypeIcon(page.content_type);
            li.prepend(iconSpan);
        }
        
        list.appendChild(li);
    });
}

function selectPage(id) {
    currentPageId = id;
    renderPageList(document.querySelectorAll('.pages').map(p => p.id)); 
    
    const pageData = fetchPageById(id);
    if (pageData && !pageData.error) {
        document.getElementById('editor').innerHTML = '';
        
        let html = `<h1 class="block">${escapeHtml(pageData.title || '')}</h1>`;
        
        if (Array.isArray(pageData.blocks)) {
            pageData.blocks.forEach(block => {
                html += renderBlock(block);
            });
        }
        
        document.getElementById('editor').innerHTML = html;
    } else if (!pageData) {
        const welcome = `Welcome to your new page! <br><br>` + 
                       `<p>Try these shortcuts:</p>` +
                       `<ul><li><strong>Ctrl/Cmd + Enter</strong>: Create a new page</li></ul>`;
        document.getElementById('editor').innerHTML = escapeHtml(welcome);
    } else {
        const errorDiv = document.createElement('div');
        errorDiv.style.color = 'red';
        errorDiv.textContent = pageData.error || 'Error loading page';
        document.getElementById('editor').appendChild(errorDiv);
    }
}

async function fetchPageById(id) {
    try {
        const res = await fetch(`${API_BASE}/pages/${id}`);
        return await res.json();
    } catch (err) { console.error(err); return null; }
}

function renderBlock(block) {
    if (!block || !block.type) return '';
    
    let html = `<div class="block" data-id="${encodeURIComponent(JSON.stringify(block))}"`;
    
    const textContent = block.text ? escapeHtml(block.text).replace(/<[^>]+>/g, '') : '';
    
    if (block.type === 'heading1') {
        html += ` style="font-size: 40px; line-height: 48px;">${textContent}</div>`;
    } else if (block.type === 'heading2') {
        html += ` style="font-size: 30px; line-height: 36px; margin-top: 16px;">${textContent}</div>`;
    } else if (block.type === 'heading3') {
        html += ` style="font-size: 24px; line-height: 28px; margin-top: 16px;">${textContent}</div>`;
    } else if (['bullet_list_item', 'numbered_list_item'].includes(block.type) && block.children_ids.length > 0) {
        // Render list with children
        const ulTag = block.type === 'bullet_list_item' ? '<ul>' : '<ol>';
        html += ` style="padding-left:26px;">${textContent}</div>`;
        
        for (const childId of block.children_ids.slice(0, 5)) {
            // Children are rendered as paragraphs by default - simplified
        }
    } else if (block.type === 'paragraph') {
        html += `<p>${textContent}</p></div>`;
    } else if (block.type === 'code' && block.language) {
        html += `</div><pre class="block"><code style="background:#f1f2f3; padding:8px; border-radius:4px;">${escapeHtml(block.text || '')}</code></pre></div>`;
    } else if (['quote'].includes(block.type)) {
        html += `<blockquote>${textContent}</blockquote></div>`;
    } else {
        // Default to paragraph for unknown types with text
        if (textContent) {
            html = `<div class="block"><p>${textContent}</p></div>`;
        }
    }
    
    return html.replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function getSelectedBlock(element) {
    const blockDiv = element.closest('.block');
    if (blockDiv && blockDiv.dataset.id) {
        try {
            return JSON.parse(decodeURIComponent(blockDiv.dataset.id));
        } catch(e) {}
    }
    return null;
}

async function insertNewBlock(beforeId, type, text='') {
    try {
        const res = await fetch(`${API_BASE}/blocks`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({page_id: currentPageId, before_block_id: beforeId, type, text})
        });
        
        const data = await res.json();
        
        // Re-fetch and re-render page
        const pageData = fetchPageById(currentPageId);
        if (pageData && !pageData.error && Array.isArray(pageData.blocks)) {
            document.getElementById('editor').innerHTML = '';
            
            let html = `<h1 class="block">${escapeHtml(pageData.title || '')}</h1>`;
            pageData.blocks.forEach(block => {
                html += renderBlock(block);
            });
            
            document.getElementById('editor').innerHTML = html;
        }
        
        selectBlock(data.id);
        return data.id;
    } catch (err) { console.error(err); return null;}
}

function deleteSelectedBlock() {
    if (!selectedBlockId) return;
    
    fetch(`${API_BASE}/blocks/${selectedBlockId}`, {method: 'DELETE'}).then(() => {
        const pageData = fetchPageById(currentPageId);
        if (pageData && !pageData.error && Array.isArray(pageData.blocks)) {
            document.getElementById('editor').innerHTML = '';
            
            let html = `<h1 class="block">${escapeHtml(pageData.title || '')}</h1>`;
            pageData.blocks.forEach(block => {
                html += renderBlock(block);
            });
            
            document.getElementById('editor').innerHTML = html;
        }
    });
}

function selectBlock(id) {
    selectedBlockId = id;
    
    const blocks = document.querySelectorAll('.block');
    blocks.forEach(b => b.classList.remove('selected'));
    
    if (id) {
        // Highlight logic simplified for now
    }
}

async function createNewPage() {
    const titleInput = document.getElementById('newPageInput');
    const title = titleInput.value.trim();
    
    if (!title && !currentPageId) return;
    
    try {
        let res;
        if (currentPageId) {
            res = await fetch(`${API_BASE}/pages`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({parent_id: currentPageId, title})
            });
        } else {
            // Create root page with just a title if provided
            res = await fetch(`${API_BASE}/pages`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title})
            });
        }
        
        const pageData = await res.json();
        document.getElementById('newPageInput').value = '';
        loadPages();
    } catch (err) { console.error(err); alert('Error creating page');}
}

function getContentTypeIcon(type) {
    const icons = {'docx': '📄', 'pdf': '📘', None: '📄'};
    return icons[type] || '📄';
}

async function postComment() {
    const commentText = document.getElementById('commentInput').value.trim();
    if (!commentText) return;
    
    try {
        await fetch(`${API_BASE}/comments`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({page_id: currentPageId, content: commentText})
        });
        
        document.getElementById('commentInput').value = '';
    } catch (err) { console.error(err); alert('Error posting comment');}
    
    // Re-fetch page to show new comments if needed
    const pageData = fetchPageById(currentPageId);
    if (pageData && !pageData.error) {
        selectPage(currentPageId);
    }
}

</script>
{% endblock %}
</body>
</html>"""


@app.route('/')
def index():
    """Render the main editor page."""
    session = Session()
    try:
        count = session.query(Page).count()
        
        if count == 0:
            content_block = "<div class='empty-state'><p>No pages yet. Create a new one!</p></div>"
            
            # Render empty sidebar list
            page_list_html = ""
        else:
            # Fetch all pages for sidebar and render first in editor
            from sqlalchemy.orm import joinedload
            
            pages_query = session.query(Page).options(joinedload(Page.blocks)).order_by(Page.created_at.desc()).all()
            
            if not pages_query:
                content_block = "<div class='empty-state'><p>No pages yet. Create a new one!</p></div>"
                page_list_html = ""
            else:
                # Render sidebar list items
                page_list_items = []
                for p in pages_query:
                    icon = get_content_type_icon(p.content_type) if hasattr(get_content_type_icon, '__call__') else ('📄' if not p.content_type else '📘' if p.content_type == 'pdf' else '📄')
                    title = escape_html(p.title or '(Untitled)')
                    active_class = 'active' if p.id == pages_query[0].id else ''
                    
                    page_list_items.append(f'<li class="page-item {active_class}" onclick="selectPage(\'{p.id}\")">{icon} {title}</li>')
                
                page_list_html = ''.join(page_list_items)
                
                # Render first page content in editor
                if pages_query:
                    page_data, error = get_page_with_blocks(pages_query[0].id)
                    
                    if error or not page_data:
                        content_block = "<div class='empty-state'><p>Error loading page</p></div>"
                    else:
                        html_content = f"<h1 class=\"block\">{escape_html(page_data.get('title', ''))}</h1>"
                        
                        for block in page_data.get('blocks', []):
                            if not block or not block.get('type'):
                                continue
                            
                            text_content = escape_html(block.get('text', '')).replace(/<[^>]+>/g, '').replace('&lt;/g, '<').replace('/&gt;', '>')
                            
                            if block['type'] == 'heading1':
                                html_content += f'<div class="block"><h1>{text_content}</h1></div>'
                            elif block['type'] == 'heading2':
                                html_content += f'<div class="block"><h2>{text_content}</h2></div>'
                            elif block['type'] == 'heading3':
                                html_content += f'<div class="block"><h3>{text_content}</h3></div>'
                            elif ['bullet_list_item', 'numbered_list_item'].includes(block['type']):
                                # Simplified: just render text for now
                                pass
                            elif block['type'] == 'paragraph':
                                html_content += f'<div class="block"><p>{text_content}</p></div>'
                            elif block['type'] == 'code' and block.get('language'):
                                code_text = escape_html(block.get('text', '')).replace(/<[^>]+>/g, '').replace('&lt;/g, '<').replace('/&gt;', '>')
                                html_content += f'''<div class="block">
                                    <pre><code style="background:#f1f2f3; padding:8px; border-radius:4px;">{code_text}</code></pre>
                                </div>'''
                            elif block['type'] and 'quote' in block['type']:
                                html_content += f'<blockquote>{text_content}</blockquote>'
                        
                        content_block = html_content if html_content else "<div class='empty-state'><p>This page is empty</p></div>"
        
        return render_template_string(HTML_TEMPLATE, 
                                     title="Notion Clone",
                                     block=dict(title=page_list_html, content=content_block))
    finally:
        session.close()


@app.route('/api/pages', methods=['GET'])
def get_pages():
    """Get all pages."""
    session = Session()
    try:
        from sqlalchemy.orm import joinedload
        
        pages_query = session.query(Page).options(joinedload(Page.blocks)).order_by(Page.created_at.desc()).all()
        
        result = []
        for page in pages_query or []:
            blocks_list = []
            
            # Fetch all blocks for this page with their children (paragraphs)
            if hasattr(page, 'blocks') and page.blocks:
                try:
                    for block in page.blocks:
                        child_ids_str = getattr(block, 'children_ids', '') or ''
                        
                        block_dict = {
                            'id': block.id,
                            'type': block.type if block.type else '',
                            'text': escape_html(block.text) if hasattr(block, 'text') and block.text else None,
                            'language': getattr(block, 'language', None),
                            'children_ids': child_ids_str.split(',') if ',' in (child_ids_str or '') else []
                        }
                        
                        blocks_list.insert(0, block_dict)
                except Exception as e:
                    print(f"Error processing page {page.id}: {e}")
            
            result.append({
                'id': escape_html(page.id),
                'title': escape_html(page.title),
                'content_type': getattr(page, 'content_type', None),
                'blocks': blocks_list,
                'created_at': page.created_at.isoformat() if hasattr(page.created_at, 'isoformat') else str(page.created_at)
            })
        
        return jsonify(result)
    finally:
        session.close()


@app.route('/api/pages', methods=['POST'])
def create_page():
    """Create a new page."""
    session = Session()
    try:
        data = request.get_json() or {}
        
        if not data.get('title') and (not hasattr(data, 'parent_id') or not getattr(data, 'parent_id', None)):
            return jsonify({'error': 'Title required for root pages'}), 400
        
        new_page = Page(
            title=data.get('title'),
            content_type=getattr(data, 'content_type', None) if hasattr(data, '__dict__') else data.get('content_type'),
            parent_id=None if not getattr(data, 'parent_id', True) else (getattr(data, 'parent_id') or data.get('parent_id'))
        )
        
        session.add(new_page)
        session.commit()
        
        page_data = {
            'id': new_page.id,
            'title': escape_html(new_page.title),
            'content_type': getattr(new_page, 'content_type', None),
            'created_at': new_page.created_at.isoformat() if hasattr(new_page.created_at, 'isoformat') else str(new_page.created_at)
        }
        
        return jsonify(page_data), 201
    finally:
        session.close()


@app.route('/api/pages/<page_id>', methods=['GET'])
def get_page(page_id):
    """Get a specific page with its blocks."""
    from sqlalchemy.orm import joinedload
    
    session = Session()
    try:
        from sqlalchemy import and_
        
        # Fetch the page with all its blocks, ordered by creation time (newest first)
        page_with_blocks = session.query(Page).options(
            joinedload(Page.blocks),
            joinedload(Pages.comments)
        ).filter(Page.id == page_id).first()
        
        if not page_with_blocks:
            return jsonify({'error': 'Page not found'}), 404
        
        blocks_list = []
        
        for block in (page_with_blocks.blocks or []):
            child_ids_str = getattr(block, 'children_ids', '') or ''
            
            # Only include non-empty text blocks as children
            if hasattr(block, 'text') and block.text:
                child_dict = {
                    'id': block.id,
                    'type': '',  # Children are paragraphs by default for lists
                    'text': escape_html(block.text),
                    'children_ids': ''
                }
                
                blocks_list.append(child_dict)
            
            # Add the main block (heading/list item with its text)
            if hasattr(block, 'text') and block.text:
                child_ids_str = getattr(block, 'children_ids', '') or ''
                
                block_dict = {
                    'id': block.id,
                    'type': block.type if block.type else '',
                    'text': escape_html(block.text),
                    'language': getattr(block, 'language', None),
                    'children_ids': child_ids_str.split(',') if ',' in (child_ids_str or '') else []
                }
                
                blocks_list.insert(0, block_dict)
        
        page_data = {
            'id': escape_html(page_with_blocks.id),
            'title': escape_html(page_with_blocks.title),
            'content_type': getattr(page_with_blocks, 'content_type', None),
            'blocks': blocks_list,
            'created_at': page_with_blocks.created_at.isoformat() if hasattr(page_with_blocks.created_at, 'isoformat') else str(page_with_blocks.created_at)
        }
        
        return jsonify(page_data)
    finally:
        session.close()


@app.route('/api/pages/<page_id>', methods=['PUT'])
def update_page(page_id):
    """Update a page's title."""
    session = Session()
    try:
        data = request.get_json() or {}
        
        if not data.get('title'):
            return jsonify({'error': 'Title is required'}), 400
        
        page = Page.query.filter(Page.id == page_id).first()
        if not page:
            return jsonify({'error': 'Page not found'}), 404
        
        page.title = data['title']
        
        session.commit()
        
        result, error = get_page_with_blocks(page_id)
        if error:
            return jsonify(error), 404
        
        # Update content_type if provided
        if 'content_type' in data and getattr(data, '__dict__', None):
            page.content_type = data['content_type']
        
        session.commit()
        
        result, _ = get_page_with_blocks(page_id)
        return jsonify(result), 200
        
    finally:
        session.close()


@app.route('/api/pages/<page_id>', methods=['DELETE'])
def delete_page(page_id):
    """Delete a page."""
    session = Session()
    try:
        from sqlalchemy.orm import joinedload
        
        # Check if this is a root page or has children
        parent_page = Page.query.filter(Page.id == page_id).first()
        
        if not parent_page:
            return jsonify({'error': 'Page not found'}), 404
        
        # If it's a child, delete only the block content (not the whole page)
        has_children = session.query(Page).filter(Page.parent_id == page_id).count() > 0
        
        if hasattr(parent_page, 'blocks') and parent_page.blocks:
            for block in parent_page.blocks:
                # Delete all blocks with text
                session.query(Block).filter(
                    Block.page_id == page_id,
                    and_(Block.text.isnot(None), Block.text != '')
                ).delete(synchronize_session=False)
        
        # Update or delete the page itself based on hierarchy
        if has_children:
            parent_page.title = '(Deleted)'  # Soft delete marker for root pages
        else:
            session.delete(parent_page)
        
        session.commit()
        
        return jsonify({'message': 'Page deleted'}), 200
        
    finally:
        session.close()


@app.route('/api/blocks', methods=['POST'])
def create_block():
    """Create a new block."""
    session = Session()
    try:
        data = request.get_json() or {}
        
        page_id = getattr(data, 'page_id') if hasattr(data, '__dict__') else data.get('page_id')
        before_block_id = None
        
        # Find the parent page and get its next block ID (or create new)
        from sqlalchemy.orm import joinedload
        page_with_blocks = session.query(Page).options(joinedload(Page.blocks)).filter(
            Page.id == page_id,
            or_(Page.parent_id.isnot(None), Page.content_type != 'page')  # Root pages can have any parent_id
        ).first()
        
        if not page_with_blocks:
            return jsonify({'error': 'Page not found'}), 404
        
        next_block = None
        current_pos_idx = 999999
        
        for block in (page_with_blocks.blocks or []):
            # Find the position to insert before
            if getattr(block, 'children_ids', ''):
                continue
            
            try:
                created_at = block.created_at.timestamp() if hasattr(block.created_at, 'timestamp') else 0
            except:
                created_at = 0
            
            if not next_block or (created_at < current_pos_idx):
                # This is the right position to insert before
                pass
        
        return jsonify({'id': str(uuid.uuid4()), 'message': 'Block creation logic needs implementation'}), 201
        
    finally:
        session.close()


@app.route('/api/blocks/<block_id>', methods=['DELETE'])
def delete_block(block_id):
    """Delete a block."""
    from sqlalchemy import and_
    
    session = Session()
    try:
        # Delete blocks with text (empty paragraphs are implicit children)
        deleted_count = session.query(Block).filter(
            Block.id == block_id,
            and_(Block.text.isnot(None), Block.text != '')
        ).delete(synchronize_session=False)
        
        if deleted_count > 0:
            return jsonify({'message': 'Block deleted'}), 200
        
        # Check if it's a root page marker (content_type == 'page')
        from sqlalchemy import or_
        parent_page = Page.query.filter(
            and_(Page.id != None, 
                  or_(or_(Page.parent_id.isnot(None), Page.content_type != 'page'), True))
        ).first()
        
        if not parent_page:
            return jsonify({'error': 'Block not found'}), 404
        
        session.delete(parent_page)
        session.commit()
        
        return jsonify({'message': 'Page deleted (it was a root page)'})
    finally:
        session.close()


@app.route('/api/comments', methods=['POST'])
def create_comment():
    """Create a comment on a page."""
    session = Session()
    try:
        data = request.get_json() or {}
        
        if not data.get('content'):
            return jsonify({'error': 'Comment content is required'}), 400
        
        new_comment = Comment(
            page_id=data['page_id'],
            user_id=None,  # Anonymous comments for now
            content=data['content']
        )
        
        session.add(new_comment)
        session.commit()
        
        comment_data = {
            'id': escape_html(new_comment.id),
            'user_id': new_comment.user_id or None,
            'content': escape_html(new_comment.content),
            'created_at': new_comment.created_at.isoformat() if hasattr(new_comment.created_at, 'isoformat') else str(new_comment.created_at)
        }
        
        return jsonify(comment_data), 201
        
    finally:
        session.close()


if __name__ == '__main__':
    app.run(debug=True, port=5000)
