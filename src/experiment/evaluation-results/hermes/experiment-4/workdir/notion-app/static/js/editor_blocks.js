// Block insertion and deletion logic for Notion-like app

const API_BASE = '/api';

let currentPageId = null;
let selectedBlockId = null;

document.addEventListener('DOMContentLoaded', async () => {
    await loadPages();
    
    const editor = document.getElementById('editor');
    if (editor) {
        // Add keyboard event listeners to the editable content area
        editor.addEventListener('keydown', handleKeydown);
        
        // Double-click handler for adding comments (on paragraph-like blocks only)
        editor.addEventListener('dblclick', async (e) => {
            await tryAddComment(e.clientX - 260 + window.scrollX, e.clientY - 40 + window.scrollY);
        });
    }
});

// Handle keyboard events in the editor
function handleKeydown(e) {
    // Ctrl/Cmd+Enter creates new page
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        createNewPage();
    } 
    // Enter key inserts a new block after current one
    else if (e.key === 'Enter' && !e.shiftKey) {
        tryHandleBlockEnter(e);
    } 
    // Backspace on empty paragraph deletes it
    else if (e.key === 'Backspace' && e.target.textContent.trim() === '') {
        deleteSelectedBlock();
    }
}

// Try to handle Enter key by inserting a new block after current one
async function tryHandleBlockEnter(e) {
    const editor = document.getElementById('editor');
    
    // Find the parent container of this element
    let container = e.target;
    while (container && !container.classList.contains('block')) {
        if (container.tagName === 'H1' || 
            container.tagName === 'H2' || 
            container.tagName === 'H3') {
            
            // For heading blocks, insert a new block of the next level or same type
            const currentLevel = parseInt(container.tagName.replace('H', ''));
            let nextType;
            
            if (currentLevel < 3) {
                nextType = `heading${currentLevel + 1}`;
            } else {
                // Headings become paragraphs, then we might turn paragraph into heading2_1
                const prevSibling = getPreviousBlock(e.target);
                
                if (!prevSibling || !['h1', 'h2'].includes(prevSibling.tagName.toLowerCase())) {
                    nextType = 'heading2';  // Default to h2 for new blocks
                } else {
                    nextType = 'paragraph';
                }
            }
            
            const blockId = await insertNewBlock(e.target, nextType);
            selectNextBlock();
        }
        
        container = container.parentElement;
    }
}

// Get the previous sibling that's a heading or paragraph element
function getPreviousBlock(element) {
    let parent = element.parentElement;
    
    // Go up to editor-container and look for previous div with block content
    while (parent && !parent.classList.contains('editor-container')) {
        const prevDiv = parent.previousElementSibling || null;
        
        if (prevDiv && prevDiv.tagName.toLowerCase() === 'div' && 
            prevDiv.querySelector('.block')) {
            
            // Return the heading/paragraph inside that div
            return prevDiv.querySelector('[class*="block"]:not(pre):not(blockquote)');
        }
        
        parent = parent.parentElement;
    }
    
    return null;
}

// Load all pages from API and render them in sidebar
async function loadPages() {
    try {
        const res = await fetch(`${API_BASE}/pages`);
        if (!res.ok) throw new Error('Failed to load pages');
        
        const pages = await res.json();
        renderPageList(pages);
        
        // Select first page or show empty state
        if (pages.length > 0) {
            currentPageId = pages[0].id;
            selectPage(currentPageId);
        } else {
            showEmptyState('No pages yet. Use Ctrl/Cmd+Enter to create a new page.');
        }
    } catch (err) {
        console.error('Error loading pages:', err);
        
        // Show default welcome content if API fails but we're in editor mode
        const editor = document.getElementById('editor');
        if (editor && currentPageId) {
            renderDefaultWelcome();
        } else {
            showEmptyState('Loading... Please refresh the page.');
        }
    }
}

// Render the sidebar list of pages
function renderPageList(pages) {
    const pageList = document.getElementById('pageList');
    if (!pageList) return;
    
    pageList.innerHTML = '';
    
    // Create a map for quick lookup by ID
    const idToPageMap = {};
    
    pages.forEach(page => {
        let iconSpanHtml = '<span class="page-icon">📄</span>';
        
        if (page.content_type) {
            iconSpanHtml = `<span class="page-icon">${CONTENT_TYPE_ICONS[page.content_type] || '📄'}</span>`;
        } else if (idToPageMap[page.id]) {
            // Already rendered a page with this ID, use default icon
            iconSpanHtml = '<span class="page-icon">📄</span>';
        }
        
        const titleText = escapeHtml(page.title) || '(Untitled)';
        
        const li = document.createElement('li');
        li.className = `page-item ${currentPageId === page.id ? 'active' : ''}`;
        li.innerHTML = `${iconSpanHtml}<span>${titleText}</span>`;
        
        // Store for later lookup by ID text extraction (simplified approach)
        idToPageMap[page.title] = { ...page, title: escapeHtml(page.title), icon: CONTENT_TYPE_ICONS[page.content_type] || '📄' };
        
        li.onclick = () => selectPage(page.id);
        
        pageList.appendChild(li);
    });
}

// Content type icons for sidebar display
const CONTENT_TYPE_ICONS = {
    'docx': '📄',
    'pdf': '📘'
};

// Select a specific page and render its content
async function selectPage(id) {
    currentPageId = id;
    
    const pageData = await fetchPageById(id);
    
    if (pageData && !pageData.error) {
        showEditor(pageData);
    } else if (!pageData || pageData.id !== id) {
        // Page not found or error - create new empty page
        renderDefaultWelcome();
        
        // Create the first block as a heading2 with default text
        const editor = document.getElementById('editor');
        if (editor && currentPageId) {
            await insertNewBlock(null, 'heading2', 'Start writing...');
            
            // Also create an empty paragraph below it for easier editing
            setTimeout(async () => {
                try {
                    await fetch(`${API_BASE}/blocks`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({page_id: currentPageId, type: '', text: ''})
                    });
                    
                    // Re-fetch page to get the new block
                    const refreshedPage = await fetchPageById(currentPageId);
                    if (refreshedPage && !refreshedPage.error) {
                        showEditor(refreshedPage);
                        
                        // Select and focus on second block (the paragraph we just added)
                        selectNextBlock();
                    }
                } catch (err) {
                    console.log('Failed to add default block:', err);
                }
            }, 100);
        }
    } else if (pageData.error) {
        // Some error occurred while fetching - show empty state with message
        const editor = document.getElementById('editor');
        if (editor) {
            renderDefaultWelcome();
        }
    } else {
        console.error('Error loading page:', pageData);
    }
}

// Show the welcome/empty state for new pages or when no blocks exist yet
function showEmptyState(message) {
    const editor = document.getElementById('editor');
    if (!editor || !currentPageId) return;
    
    let html = '<div class="empty-state">';
    html += `<div class="empty-icon">📄</div>`;
    html += `<p style="font-size: 18px;">${escapeHtml(message)}</p>`;
    html += '</div>';
    
    editor.innerHTML = html;
}

// Render default welcome content for new pages (with one block)
function renderDefaultWelcome() {
    const editor = document.getElementById('editor');
    if (!editor || !currentPageId) return null;
    
    let html = '<h1 class="block">New Page</h1>';
    html += '<p class="block"><strong>Welcome to your Notion-like workspace!</strong></p>';
    html += '<ul><li>Use <kbd>Ctrl/Cmd + Enter</kbd> to create a new page</li>' ;
    
    // Also add an empty paragraph that can be easily selected and edited
    const paraId = 'default-para-' + Date.now();
    html += `<p class="block" id="${paraId}">&nbsp;</p>`;
    
    return html;
}

// Fetch and return page data from API
async function fetchPageById(id) {
    try {
        const res = await fetch(`${API_BASE}/pages/${id}`);
        
        if (!res.ok) throw new Error('Failed to load page');
        
        return await res.json();
    } catch (err) {
        console.error(`Error fetching page ${id}:`, err);
        return null;
    }
}

// Show the editor content for a loaded page with blocks
function showEditor(pageData) {
    const editor = document.getElementById('editor');
    
    // Handle error response from API
    if (pageData.error) {
        console.error('Error loading page:', pageData);
        
        // Try to create new empty block on first load only, then fall back to welcome
        if (!currentPageId && !document.querySelector('.block')) {
            addDefaultBlocks();
        } else {
            renderDefaultWelcome();
        }
        
        return;
    }
    
    // Check if page has blocks or is empty (just title)
    const blocksArray = Array.isArray(pageData.blocks) ? pageData.blocks : [];
    
    if (!pageData.title && !blocksArray.length) {
        renderDefaultWelcome();
        return;
    }
    
    let html = '';
    
    // Main heading block for the page title (if not already a heading in blocks array)
    const hasHeadingBlock = blocksArray.some(b => b.type && ['heading1', 'heading2', 'heading3'].includes(b.type));
    if (!hasHeadingBlock && pageData.title) {
        html += `<h1 class="block">${escapeHtml(pageData.title)}</h1>`;
    }
    
    // Render all blocks in the array (excluding title block which we already added as h1)
    for (const block of blocksArray) {
        const textContent = escapeHtml(block.text || '');
        
        if (!block.type && !textContent.trim()) continue;  // Skip empty paragraphs
        
        switch (block.type.toLowerCase()) {
            case 'heading1':
                html += `<h1 class="block">${textContent}</h1>`;
                break;
                
            case 'heading2':
                html += `<h2 class="block">${textContent}</h2>`;
                break;
                
            case 'heading3':
                html += `<h3 class="block">${textContent}</h3>`;
                break;
                
            case 'bullet_list_item':
            case 'numbered_list_item': {
                // For lists, render the main item text only (children are implicit paragraphs)
                if (!textContent.trim()) continue;  // Skip empty list items
                
                html += `<div style="padding-left: 26px; margin-bottom: 4px;">${textContent}</div>`;
                
                // If there are child IDs, we'd fetch and render them here in a full implementation
                break;
            }
            
            case 'paragraph': {
                if (!textContent.trim()) continue;  // Skip empty paragraphs (they're list children)
                html += `<p class="block">${textContent || '&nbsp;'}</p>`;
                break;
            }
                
            case 'code': {
                const codeText = escapeHtml(block.text || '');
                if (block.language && textContent.trim()) {
                    // Render as code block with syntax highlighting styling
                    html += `
                        <pre class="block">
                            <code style="background:#f1f2f3; padding:8px 12px; border-radius:6px;">${escapeCode(codeText)}</code>
                        </pre>`;
                } else if (textContent.trim()) {
                    // Fallback to paragraph for code without language or empty text
                    html += `<p class="block">${textContent}</p>`;
                }
                
                break;
            }
            
            case 'quote':
                if (textContent.trim() || block.type === 'quote') {  // Always render quote blocks even empty
                    html += `<blockquote>${textContent || '&nbsp;'}</blockquote>`;
                } else {
                    continue;  // Skip other types of quotes
                }
                break;
        }
    }
    
    // If no valid content rendered, show default welcome or empty state
    if (!html.trim()) {
        renderDefaultWelcome();
    } else {
        editor.innerHTML = html;
    }
}

// Escape HTML text safely (removes any existing HTML tags and escapes special chars)
function escapeHtml(text) {
    if (!text || typeof text !== 'string') return '';
    
    // First remove any existing HTML-like content to prevent XSS, then escape remaining & < > 
    const cleaned = text.replace(/<[^>]*>|&/g, '');  // Remove tags and ampersands
    
    const div = document.createElement('div');
    div.textContent = cleaned;
    return div.innerHTML;
}

// Escape code content (keep markdown formatting)
function escapeCode(code) {
    if (!code || typeof code !== 'string') return '';
    
    // Only escape & first to prevent breaking entities, then < > so we don't break HTML tags
    let escaped = String(code).replace(/&/g, '&amp;');  
    escaped = escaped.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    
    return escaped;  // Keep markdown-like formatting readable
}

// Get previous block element (heading or paragraph) for context when inserting new blocks
function getPreviousBlock(element) {
    let container = element.parentElement;
    
    while (container && !container.classList.contains('block')) {
        if (['H1', 'H2', 'H3'].includes(container.tagName)) {
            return container;
        }
        
        const prevDiv = container.previousElementSibling || null;
        
        if (prevDiv && 
            ['pre', 'blockquote', 'ul', 'ol'].some(tag => tag.toLowerCase() === prevDiv.tagName.toLowerCase())) {
            
            // Return the heading/paragraph inside that div element
            return prevDiv.querySelector('[class*="block"]:not(pre):not(blockquote)') || null;
        }
        
        container = container.parentElement;
    }
    
    return null;
}
