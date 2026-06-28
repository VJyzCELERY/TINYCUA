// Notion-like App JavaScript Client
(function() {
    const API_BASE = '/api';
    
    let currentPageId = null;
    let selectedBlockId = null;
    
    // Icon mappings for content types
    const CONTENT_TYPE_ICONS = {
        'docx': '📄',
        'pdf': '📘'
    };
    
    document.addEventListener('DOMContentLoaded', async () => {
        await loadPages();
        
        // Add Enter key handler for creating new blocks/pages
        const editor = document.getElementById('editor');
        if (editor) {
            editor.addEventListener('keydown', handleKeydown);
            
            // Double click on paragraph-like blocks to add comment
            editor.addEventListener('dblclick', async (e) => {
                await tryAddComment(e.clientX - 260 + window.scrollX, e.clientY - 40 + window.scrollY);
            });
        }
    });
    
    // Handle keyboard events in the editor
    function handleKeydown(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            createNewPage();
        } else if (e.key === 'Enter' && !e.shiftKey) {
            tryHandleBlockEnter(e);
        } else if (e.key === 'Backspace' && e.target.textContent.trim() === '') {
            deleteSelectedBlock();
        }
    }
    
    // Try to handle block creation on Enter key
    async function tryHandleBlockEnter(e) {
        const editor = document.getElementById('editor');
        if (!editor || !currentPageId) return;
        
        let newType, newText;
        const currentText = e.target.textContent.trim();
        
        // Check what type of block we're in based on parent structure or previous context
        const prevBlock = getPreviousSibling(e.target);
        if (prevBlock && ['h1', 'h2', 'h3'].includes(prevBlock.tagName.toLowerCase())) {
            newType = 'heading' + ((parseInt(prevBlock.style.fontSize) / 10).toFixed(0)).replace('.', '');
        } else {
            // Default to heading2 for new blocks
            newType = 'heading2';
        }
        
        if (newType === 'heading3') {
            newType = 'heading2_1';
        }
        
        const nextBlockId = await insertNewBlock(e.target, newType);
        selectNextBlock();
    }
    
    // Get previous sibling element that's a block container
    function getPreviousSibling(element) {
        let parent = element.parentElement;
        while (parent && parent.classList.contains('editor-container')) {
            const prev = parent.previousElementSibling || null;
            if (prev && prev.tagName.toLowerCase() === 'div' && prev.querySelector('.block')) {
                return prev.querySelector('.block');
            }
            break;
        }
        return null;
    }
    
    // Load all pages from the API and render them in sidebar
    async function loadPages() {
        try {
            const res = await fetch(`${API_BASE}/pages`);
            if (!res.ok) throw new Error('Failed to load pages');
            
            const pages = await res.json();
            renderPageList(pages);
            
            // Select first page or create empty state
            if (pages.length > 0) {
                currentPageId = pages[0].id;
                selectPage(currentPageId);
            } else {
                showEmptyState('No pages yet. Use Ctrl/Cmd+Enter to create a new page.');
            }
        } catch (err) {
            console.error('Error loading pages:', err);
            // Try to load default welcome content
            const editor = document.getElementById('editor');
            if (editor) {
                showEmptyState('Welcome! Use Ctrl/Cmd+Enter to create a new page.');
            }
        }
    }
    
    // Render the sidebar list of pages
    function renderPageList(pages) {
        const pageList = document.getElementById('pageList');
        if (!pageList) return;
        
        pageList.innerHTML = '';
        
        pages.forEach(page => {
            const li = document.createElement('li');
            li.className = `page-item ${currentPageId === page.id ? 'active' : ''}`;
            
            // Add icon for content type
            let iconSpanHtml = '';
            if (page.content_type) {
                const icon = CONTENT_TYPE_ICONS[page.content_type] || '📄';
                iconSpanHtml = `<span class="page-icon">${icon}</span>`;
            } else {
                iconSpanHtml = '<span class="page-icon">📄</span>';
            }
            
            const titleText = escapeHtml(page.title) || '(Untitled)';
            li.innerHTML = `${iconSpanHtml}<span>${titleText}</span>`;
            li.onclick = () => selectPage(page.id);
            
            pageList.appendChild(li);
        });
    }
    
    // Select a specific page and render its content
    async function selectPage(id) {
        currentPageId = id;
        
        const pageData = await fetchPageById(id);
        if (pageData && !pageData.error) {
            showEditor(pageData);
        } else if (!pageData) {
            // Create new empty page with default content
            const editor = document.getElementById('editor');
            if (editor) {
                editor.innerHTML = '';
                renderDefaultWelcome();
            }
        } else {
            console.error('Error loading page:', pageData);
        }
    }
    
    // Show the welcome/empty state for new pages
    function showEmptyState(message) {
        const editor = document.getElementById('editor');
        if (!editor) return;
        
        let html = '<div class="empty-state">';
        html += `<div class="empty-icon">📄</div>`;
        html += `<p style="font-size: 18px;">${escapeHtml(message)}</p>`;
        html += '</div>';
        
        editor.innerHTML = html;
    }
    
    // Render default welcome content for new pages
    function renderDefaultWelcome() {
        const editor = document.getElementById('editor');
        if (!editor) return;
        
        let html = '<h1 class="block">New Page</h1>';
        html += '<p class="block"><strong>Welcome to your Notion-like workspace!</strong></p>';
        html += '<ul><li>Use <kbd>Ctrl/Cmd + Enter</kbd> to create a new page</li>';
        html += '</ul>';
        
        editor.innerHTML = html;
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
    
    // Show the editor content for a loaded page
    function showEditor(pageData) {
        const editor = document.getElementById('editor');
        if (!editor || !pageData.blocks || pageData.blocks.length === 0) {
            renderDefaultWelcome();
            return;
        }
        
        let html = '';
        
        // Main title block (if provided in data or create default)
        const hasTitleBlock = pageData.blocks.some(b => b.type && ['heading1', 'heading2', 'heading3'].includes(b.type));
        if (!hasTitleBlock) {
            html += `<h1 class="block">${escapeHtml(pageData.title || '')}</h1>`;
        }
        
        // Render all blocks
        for (const block of pageData.blocks) {
            const textContent = escapeHtml(block.text || '');
            
            if (!block.type) continue;
            
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
                    // For lists, we'll render the main item text only for simplicity
                    // Children (paragraphs) would be fetched separately in a full implementation
                    html += `<div style="padding-left: 26px; margin-bottom: 4px;">${textContent}</div>`;
                    break;
                }
                    
                case 'paragraph':
                    html += `<p class="block">${textContent || '&nbsp;'}</p>`;
                    break;
                    
                case 'code': {
                    const codeText = escapeHtml(block.text || '');
                    if (block.language) {
                        html += `
                            <pre class="block">
                                <code style="background:#f1f2f3; padding:8px; border-radius:4px;">${escapeCode(codeText)}</code>
                            </pre>`;
                    } else {
                        html += `<p class="block">${textContent}</p>`;
                    }
                    break;
                }
                    
                case 'quote':
                    html += `<blockquote>${textContent || '&nbsp;'}</blockquote>`;
                    break;
            }
        }
        
        // If no blocks rendered, show empty state
        if (!html.trim()) {
            renderDefaultWelcome();
        } else {
            editor.innerHTML = html;
        }
    }
    
    // Escape HTML text safely (excluding markdown in code)
    function escapeHtml(text) {
        if (!text || typeof text !== 'string') return '';
        
        const div = document.createElement('div');
        div.textContent = text.replace(/<[^>]*>|&/g, '');  // Remove any existing HTML and & chars first
        return div.innerHTML;
    }
    
    // Escape code content (keep markdown)
    function escapeCode(code) {
        if (!code || typeof code !== 'string') return '';
        
        let escaped = code.replace(/&/g, '&amp;');  // First: & becomes &amp;
        escaped = escaped.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        
        // Don't escape markdown-like content for now - keep it readable
        return escaped;
    }
    
    // Escape HTML text safely (excluding markdown in code)
    function escapeHtml(text) {
        if (!text || typeof text !== 'string') return '';
        
        const div = document.createElement('div');
        div.textContent = text.replace(/<[^>]*>|&/g, '');  // Remove any existing HTML and & chars first
        return div.innerHTML;
    }
