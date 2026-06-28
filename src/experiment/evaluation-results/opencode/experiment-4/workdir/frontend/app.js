// API Configuration
const API_BASE = '/api';

let currentPageId = null;
let currentToken = localStorage.getItem('auth_token') || '';

// Initialize app on DOM load
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
});

function checkAuth() {
    if (currentToken) {
        showToast('Logged in successfully');
    } else {
        // Auto-login for local development
        login().then(() => {});
    }
}

// --- Authentication Functions ---

async function login() {
    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: 'demo_user', remember_me: true })
        });

        if (!response.ok) throw new Error('Login failed');

        const data = await response.json();
        currentToken = data.token;
        
        // Store token with expiry timestamp
        localStorage.setItem('auth_token', currentToken);
        localStorage.setItem('token_expiry', Date.now() + (data.expires_in * 1000));

        return { success: true, user_id: data.user_id };
    } catch (error) {
        console.error('Login error:', error);
        showToast(error.message || 'Failed to login');
        return null;
    }
}

async function logout() {
    currentToken = '';
    localStorage.removeItem('auth_token');
    localStorage.removeItem('token_expiry');
    
    // Clear page state
    currentPageId = null;
    
    // Show welcome screen
    document.getElementById('pageHeader').style.display = 'none';
    document.getElementById('emptyState').style.display = 'block';
    document.getElementById('welcomeScreen').style.display = 'flex';
    
    showToast('Logged out successfully');
}

// Add auth header to requests if needed
async function fetchWithAuth(url, options = {}) {
    const headers = new Headers(options.headers);
    
    // Check token expiry and refresh if needed
    const expiryStr = localStorage.getItem('token_expiry');
    const now = Date.now();
    
    if (expiryStr && parseInt(expiryStr) < now + 30000) { // Refresh before expiry
        await login();
    }

    headers.set('Authorization', `Bearer ${currentToken}`);
    headers.set('Accept', 'application/json');

    const response = await fetch(url, options);
    
    if (!response.ok && response.status !== 401) {
        const errorText = await response.text();
        throw new Error(errorText || httpStatusText(response.status));
    }

    return response;
}

function httpStatusText(statusCode) {
    const messages = {
        '200': 'OK',
        '401': 'Unauthorized',
        '403': 'Forbidden',
        '404': 'Not Found',
        '500': 'Internal Server Error'
    };
    return messages[statusCode] || '';
}

// --- Page Functions ---

async function loadPages() {
    try {
        const response = await fetchWithAuth(`${API_BASE}/pages?per_page=10`);
        const data = await response.json();
        
        renderPageList(data.pages);
    } catch (error) {
        console.error('Failed to load pages:', error);
        showToast(error.message || 'Error loading pages');
    }
}

function renderPageList(pages) {
    const pageList = document.getElementById('pageList');
    
    if (!pages || pages.length === 0) {
        pageList.innerHTML = `
            <div class="page-item" style="text-align: center; color: #787775;">
                No pages yet. Create your first one!
            </div>
        `;
        return;
    }

    const html = pages.map(page => `
        <div 
            class="page-item ${currentPageId === page.id ? 'active' : ''}" 
            onclick="selectPage(${page.id})"
            data-id="${page.id}">
            ${escapeHtml(page.title)}${page.parent_page_id !== null ? ' ▼' : ''}
        </div>
    `).join('');

    pageList.innerHTML = html;
}

async function selectPage(id) {
    try {
        currentPageId = id;
        
        // Update UI to show page header, hide welcome screen and empty state
        document.getElementById('pageHeader').style.display = 'block';
        document.getElementById('welcomeScreen').style.display = 'none';
        document.getElementById('emptyState').style.display = 'none';

        const response = await fetchWithAuth(`${API_BASE}/pages/${id}`);
        const pageData = await response.json();

        // Update title input
        setTimeout(() => {
            if (pageData.title) {
                const titleInput = document.getElementById('pageTitleInput');
                titleInput.value = pageData.title;
                titleInput.focus();
                
                // Select all text for easy editing
                selectAllText(titleInput);
            } else {
                document.getElementById('pageTitleInput').value = '';
            }
        }, 100);

        renderBlocks(pageData.blocks || []);
    } catch (error) {
        console.error(`Failed to load page ${id}:`, error);
        
        // If we can't load a specific page, try loading all pages and selecting the first one
        if (currentPageId === id) {
            await loadPages();
            
            const items = document.querySelectorAll('.page-item');
            if (items.length > 0) {
                selectPage(items[0].dataset.id);
            } else {
                showToast('No pages available. Create one first!');
            }
        }
    }
}

async function createNewPage() {
    try {
        const response = await fetchWithAuth(`${API_BASE}/pages`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: `Untitled Page ${new Date().toLocaleTimeString()}`,
                content: ''
            })
        });

        const pageData = await response.json();

        // Update sidebar and select the new page
        loadPages();
        
        setTimeout(() => {
            if (pageData.id) {
                currentPageId = pageData.id;
                
                document.getElementById('pageTitleInput').value = '';
                renderBlocks([]);
            }
        }, 100);

    } catch (error) {
        console.error('Failed to create new page:', error);
        showToast(error.message || 'Error creating page');
    }
}

async function updatePageTitle() {
    if (!currentPageId) return;

    const titleInput = document.getElementById('pageTitleInput');
    
    // Only save after typing a bit (debounce-like behavior)
    clearTimeout(window.titleSaveTimer);
    window.titleSaveTimer = setTimeout(async () => {
        const newTitle = titleInput.value.trim();
        
        if (!newTitle && !titleInput.placeholder.includes('Untitled')) return;

        try {
            await fetchWithAuth(`${API_BASE}/pages/${currentPageId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: newTitle || 'Untitled Page' })
            });
            
            // Update sidebar display
            renderPageList([]); // Will reload and update
            
        } catch (error) {
            console.error('Failed to update page title:', error);
        }
    }, 500);
}

// --- Block Functions ---

async function loadBlocksForCurrentPage() {
    if (!currentPageId) return;

    try {
        const response = await fetchWithAuth(`${API_BASE}/pages/${currentPageId}/blocks`);
        const data = await response.json();
        
        renderBlocks(data.blocks || []);
    } catch (error) {
        console.error('Failed to load blocks:', error);
        showToast(error.message || 'Error loading blocks');
    }
}

async function createBlock(type, parentBlockId = null) {
    if (!currentPageId) return;

    try {
        const response = await fetchWithAuth(`${API_BASE}/pages/${currentPageId}/blocks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type, data: {} })
        });

        return await response.json();
    } catch (error) {
        console.error('Failed to create block:', error);
        showToast(error.message || 'Error creating block');
        return null;
    }
}

async function updateBlock(blockId, updates) {
    if (!currentPageId) return;

    try {
        const response = await fetchWithAuth(`${API_BASE}/pages/${currentPageId}/blocks/${blockId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });

        return await response.json();
    } catch (error) {
        console.error('Failed to update block:', error);
        showToast(error.message || 'Error updating block');
        return null;
    }
}

async function deleteBlock(blockId) {
    if (!currentPageId) return false;

    try {
        const response = await fetchWithAuth(`${API_BASE}/pages/${currentPageId}/blocks/${blockId}`, {
            method: 'DELETE'
        });

        return response.ok;
    } catch (error) {
        console.error('Failed to delete block:', error);
        showToast(error.message || 'Error deleting block');
        return false;
    }
}

function renderBlocks(blocks) {
    const container = document.getElementById('blockList');
    
    if (!blocks || blocks.length === 0) {
        // Add default paragraph for empty pages
        addDefaultParagraph();
        return;
    }

    const html = blocks.map(block => `
        <div class="block-container" data-block-id="${block.id}">
            ${getBlockHTML(block)}
            
            <div class="block-actions">
                <button 
                    class="btn-block-action" 
                    onclick="addBlockAfter(${block.id}, 'paragraph', event)">+ Add</button>
                
                <select onchange="updateBlockType(${block.id}, this.value)" style="font-size: 0.8rem; padding: 2px;">
                    ${getBlockTypesOptions(block.type)}
                </select>
            </div>
        </div>
    `).join('');

    container.innerHTML = html;
}

function getBlockHTML(block) {
    const type = block.type || 'paragraph';
    
    // Parse data if it's a JSON string
    let data = {};
    try {
        if (typeof block.data === 'string') {
            data = JSON.parse(block.data);
        } else {
            data = block.data;
        }
    } catch (e) {
        // ignore parse errors, use empty object
    }

    const contentClass = type === 'paragraph' ? 'block-paragraph' : `block-${type}`;
    
    return `<div class="${contentClass}" oninput="updateBlockContent(${block.id}, this.value)">${escapeHtml(block.data)}</div>`;
}

function getBlockTypesOptions(currentType) {
    const options = [
        ['paragraph', 'Paragraph'],
        ['heading_1', 'Heading 1'],
        ['heading_2', 'Heading 2'],
        ['bulleted_list_item', 'Bullet List']
    ];

    return options.map(([value, label]) => 
        `<option value="${value}" ${currentType === value ? 'selected' : ''}>${label}</option>`
    ).join('');
}

function addDefaultParagraph() {
    const container = document.getElementById('blockList');
    
    const block = createBlock('paragraph').then(block => {
        if (block) renderBlocks([block]);
    });
}

// --- Event Handlers ---

async function handleCreatePage(event) {
    event.preventDefault();
    
    const form = event.target;
    await fetchWithAuth(`${API_BASE}/pages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: form.title.value,
            type: form.type.value || 'paragraph'
        })
    });

    showToast('Page created!');
}

async function handleKeydown(event) {
    // Handle Enter key to create new block when focused on title (if page exists)
    if (event.key === 'Enter') {
        event.preventDefault();
        
        const container = document.getElementById('blockList');
        
        // Check if there's a last element we can append after
        if (container.lastElementChild && !container.lastElementChild.classList.contains('loading-spinner')) {
            await createBlock('paragraph', parseInt(container.lastElementChild.dataset.blockId || 0));
        } else {
            addDefaultParagraph();
        }
    }

    // Handle Escape to clear title input when focused on it (if page exists)
    if (event.key === 'Escape') {
        event.preventDefault();
        
        const container = document.getElementById('blockList');
        if (container.lastElementChild && !container.lastElementChild.classList.contains('loading-spinner')) {
            await createBlock('paragraph', parseInt(container.lastElementChild.dataset.blockId || 0));
        } else {
            addDefaultParagraph();
        }
    }

    // Handle backspace to delete last block when focused on title (if page exists)
    if (event.key === 'Backspace' && !document.getElementById('pageTitleInput').value) {
        event.preventDefault();
        
        const container = document.getElementById('blockList');
        if (container.lastElementChild && !container.lastElementChild.classList.contains('loading-spinner')) {
            await deleteBlock(parseInt(container.lastElementChild.dataset.blockId));
        } else {
            addDefaultParagraph();
        }
    }
}

async function updatePageTitle() {
    const titleInput = document.getElementById('pageTitleInput');
    
    if (!currentPageId) return;

    // Only save after typing something (debounce-like behavior)
    clearTimeout(window.titleSaveTimer);
    window.titleSaveTimer = setTimeout(async () => {
        const newTitle = titleInput.value.trim();
        
        try {
            await fetchWithAuth(`${API_BASE}/pages/${currentPageId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    title: newTitle || 'Untitled Page',
                    content: document.getElementById('blockList').innerHTML.replace(/<div[^>]*class="[^"]*block-paragraph"[^>]*>(.*?)<\/div>/gs, '$1') // Extract first paragraph as content
                })
            });

        } catch (error) {
            console.error('Failed to update page:', error);
        }
    }, 500);
}

async function addBlockAfter(blockId, type, event) {
    if (!currentPageId) return;

    // Prevent form submission when clicking action buttons
    if (event && event.target.tagName === 'FORM') {
        event.preventDefault();
    }

    const block = await createBlock(type);
    
    if (block) {
        loadBlocksForCurrentPage().catch(console.error);
        
        showToast('Added new block');
    }
}

async function updateBlockType(blockId, type) {
    if (!currentPageId || !type) return;

    try {
        const container = document.querySelector(`[data-block-id="${blockId}"]`);
        let currentData = '';
        
        // Get current content before updating type
        if (container && typeof container.innerHTML === 'string') {
            const blockDiv = container.firstElementChild;
            currentData = blockDiv.innerText || '';
        }

        await updateBlock(blockId, { type });
        
        showToast('Block type updated');
    } catch (error) {
        console.error('Failed to update block type:', error);
    }
}

function selectAllText(element) {
    const range = document.createRange();
    const selection = window.getSelection();
    
    if (!element.value || element.placeholder.includes('Untitled')) return;
    
    // Select all text in the input except placeholder part
    let value = element.value.replace(escapeHtml(element.placeholder), '');
    
    try {
        range.selectNodeContents(element);
        range.collapse(false);
        
        const selectedRange = window.getSelection();
        if (selectedRange) {
            selectedRange.removeAllRanges();
            selectedRange.addRange(range);
            
            // Scroll to bottom of selection
            element.scrollTop = element.scrollHeight;
        }
    } catch (e) {
        console.error('Failed to select text:', e);
    }
}

// --- Utility Functions ---

function showToast(message, duration = 3000) {
    const toast = document.getElementById('toast');
    
    if (!toast) return;

    toast.textContent = message;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, duration);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

// --- API Test Section (for demonstration) ---

async function handleCreatePage(event) {
    event.preventDefault();
    
    if (!currentPageId && !confirm('This will create a new page. Continue?')) {
        return;
    }

    const form = event.target;
    
    try {
        await fetchWithAuth(`${API_BASE}/pages`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: form.title.value,
                parent_page_id: currentPageId || -1, // null for root level
                type: form.type.value || 'paragraph'
            })
        });

        showToast('Page created successfully!');
        
        if (currentPageId) {
            loadBlocksForCurrentPage();
        } else {
            loadPages().catch(console.error);
        }
    } catch (error) {
        console.error('Failed to create page:', error);
        showToast(error.message || 'Error creating page');
    }

    // Reset form
    form.title.value = '';
}

// --- Initialize on DOMContentLoaded ---

loadPages().catch(console.error);
