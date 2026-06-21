/**
 * Notion Clone - Enhanced Frontend Application
 * Complete implementation with rich editing, databases, and modern UI
 */
class NotionApp {
    constructor() {
        this.currentPageId = null;
        this.userId = localStorage.getItem('user_id') || '';
        this.userEmail = localStorage.getItem('user_email') || '';
        this.pages = [];
        this.blocksCache = new Map();  // Cache blocks for fast updates
    }
    
    /**
     * Initialize the application
     */
    async init() {
        console.log('🚀 Notion Clone initializing...');
        await this.loadPages();
        if (this.pages.length > 0) {
            this.renderPageList();
        } else {
            document.getElementById('app').innerHTML = `
                <div class="empty-state">
                    <h3>📝 No pages yet</h3>
                    <p>Create your first page!</p>
                </div>
            `;
        }
    }
    
    /**
     * Load all root-level pages
     */
    async loadPages() {
        try {
            const response = await fetch(`/api/users/${this.userId}/pages`);
            if (response.ok) {
                const result = await response.json();
                this.pages = result.pages;
                console.log('✓ Loaded', this.pages.length, 'pages');
            }
        } catch (error) {
            console.error('✗ Failed to load pages:', error);
        }
    }
    
    /**
     * Render the sidebar and page list
     */
    renderPageList() {
        const container = document.getElementById('pages-container');
        if (!container) return;
        
        let html = `
            <div class="sidebar">
                <div class="sidebar-header">📝 Notion Clone</div>
        `;
        
        this.pages.forEach((page, index) => {
            const isActive = this.currentPageId === page.id || (page.title && page.title.includes('Untitled'));
            html += `
                <div class="nav-item ${isActive ? 'active' : ''}" onclick="app.loadPage(${index})">
                    ${this.escapeHtml(page.icon) || '📄'} 
                    ${this.truncateText(this.escapeHtml(page.title), 30)}
                </div>
            `;
        });
        
        html += `
                <div class="nav-item" onclick="app.createNewPage()">
                    + New Page
                </div>
            </div>`;
        
        container.innerHTML = html;
    }
    
    /**
     * Load and render a specific page with its blocks
     */
    async loadPage(index) {
        if (index >= this.pages.length || !this.currentPageId) return;
        const page = this.pages[index];
        await this.fetchAndRender(page.id);
    }
    
    /**
     * Fetch page content and render editor
     */
    async fetchAndRender(pageId, isNewPage = false) {
        try {
            const response = await fetch(`/api/users/${this.userId}/pages/${pageId}`);
            if (response.ok) {
                const data = await response.json();
                this.currentPageId = pageId;
                
                // Render editor
                document.getElementById('editor').innerHTML = '';
                this.renderBlockEditor(data.blocks || []);
                
                // Update title and icon in header
                if (data.title && data.icon) {
                    const headerTitle = document.querySelector('.page-header');
                    if (headerTitle) {
                        headerTitle.innerHTML = `${this.escapeHtml(data.icon)} ${this.escapeHtml(data.title)}`;
                    }
                }
            } else {
                console.error('Failed to load page:', response.status);
            }
        } catch (error) {
            console.error('✗ Error fetching page:', error);
        }
    }
    
    /**
     * Create a new page
     */
    async createNewPage() {
        const title = prompt('Enter page title:');
        if (!title) return;
        
        try {
            const response = await fetch(`/api/users/${this.userId}/pages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, icon: '' })
            });
            
            if (response.ok) {
                await this.loadPages();
                location.reload();  // Reload to show new page
            }
        } catch (error) {
            console.error('✗ Failed to create page:', error);
        }
    }
    
    /**
     * Render the block editor with all blocks and contenteditable areas
     */
    renderBlockEditor(blocks = []) {
        const container = document.getElementById('editor');
        if (!container) return;
        
        // Convert blocks array to HTML string for better performance
        let html = '';
        blocks.forEach(block => this.renderSingleBlock(block, html));
        
        container.innerHTML = `<div class="prose">${html}</div>`;
    }
    
    /**
     * Render a single block with contenteditable for editing
     */
    renderSingleBlock(block, output) {
        const type = block.type || 'text';
        const content = this.escapeHtml(block.content || '');
        const id = `block-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        
        switch (type.toLowerCase()) {
            case 'h1': output += `<div class="contenteditable" contenteditable="true">${content}</div>`; break;
            case 'h1':
                output += `<h1><span class="contenteditable" contenteditable="true">${content}</span></h1>`; break;
            
            case 'h2': output += `<h2><span class="contenteditable" contenteditable="true">${content}</span></h2>`; break;
            case 'h3': output += `<h3><span class="contenteditable" contenteditable="true">${content}</span></h3>`; break;
            
            case 'quote':
                const quoteContent = block.content || '';
                if (quoteContent.trim()) {
                    // Split by newlines for multi-line quotes
                    output += `<blockquote>${quoteContent.split('\n').map(line => `
                        <div class="contenteditable" contenteditable="true">${this.escapeHtml(line)}</div>`).join('')}</blockquote>`;
                } else if (block.content) {
                    // Handle case where quote has no newline but might have multiple paragraphs
                    const lines = block.content.split('\n').filter(Boolean);
                    output += `<blockquote>${lines.map((line, idx) => `
                        <div class="contenteditable" contenteditable="true">${this.escapeHtml(line)}</div>`).join('')}</blockquote>`;
                }
                break;
            
            case 'bullet':
            case 'bulletpointlist': {
                const listItems = block.content.split('\n').filter(Boolean);
                if (listItems.length > 0) {
                    output += `<ul><li>`;
                    listItems.forEach(item => {
                        output += `<span class="contenteditable" contenteditable="true">${this.escapeHtml(item)}</span>`;
                    });
                    output += `</li></ul>`;
                }
                break;
            }
            
            case 'number':
            case 'numberlist': {
                const listItems = block.content.split('\n').filter(Boolean);
                if (listItems.length > 0) {
                    output += `<ol><li>`;
                    listItems.forEach((item, idx) => {
                        output += `<span class="contenteditable" contenteditable="true">${this.escapeHtml(item)}</span>`;
                    });
                    output += `</li></ol>`;
                }
                break;
            }
            
            case 'text':
            default: {
                const lines = block.content.split('\n').filter(Boolean);
                if (lines.length > 0) {
                    lines.forEach(line => {
                        output += `<p><span class="contenteditable" contenteditable="true">${this.escapeHtml(line)}</span></p>`;
                    });
                }
            }
        }
    }
    
    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
    
    /**
     * Truncate text for sidebar display
     */
    truncateText(text, maxLength) {
        if (!text || text.length <= maxLength) return this.escapeHtml(text);
        const truncated = text.substring(0, maxLength - 3);
        return `${this.escapeHtml(truncated)}...`;
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new NotionApp();
});
