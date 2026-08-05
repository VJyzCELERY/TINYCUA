// Notion-like Workspace - Frontend Application

class NotionApp {
    constructor() {
        this.currentPageId = null;
        this.currentPageTitle = '';
        
        // DOM Elements
        this.pageList = document.getElementById('page-list');
        this.editor = document.getElementById('editor');
        this.backBtn = document.getElementById('back-btn');
        this.pageTitleInput = document.getElementById('page-title-input');
        this.blocksContainer = document.getElementById('blocks-container');
        this.addBlockBtn = document.getElementById('add-block-btn');
        
        // Bind events
        this.init();
    }
    
    init() {
        this.backBtn.addEventListener('click', () => this.showPageList());
        this.pageTitleInput.addEventListener('input', (e) => this.updatePageTitle(e.target.value));
        this.addBlockBtn.addEventListener('click', () => this.addBlock());
        
        // Load initial state
        this.loadPages();
    }
    
    showPageList() {
        this.editor.classList.add('hidden');
        this.pageList.classList.remove('hidden');
        this.currentPageId = null;
        this.loadPages();
    }
    
    async loadPages() {
        try {
            const response = await fetch('/api/pages');
            const pages = await response.json();
            
            if (pages.length === 0) {
                this.pageList.innerHTML = `
                    <div class="empty-state">
                        <h3>No pages yet</h3>
                        <p>Create a new page to get started</p>
                    </div>`;
                return;
            }
            
            // Create page items
            this.pageList.innerHTML = '';
            pages.forEach((page, index) => {
                const item = document.createElement('div');
                item.className = 'page-item';
                if (this.currentPageId === page.id) {
                    item.classList.add('active');
                }
                
                item.dataset.pageId = page.id;
                item.innerHTML = `
                    <span class="page-title">${escapeHtml(page.title)}</span>
                    <button class="delete-page-btn" title="Delete page">×</button>
                `;
                
                // Click to open
                const deleteBtn = item.querySelector('.delete-page-btn');
                if (deleteBtn) {
                    deleteBtn.addEventListener('click', () => this.deletePage(page.id));
                }
                
                item.addEventListener('click', (e) => {
                    if (!deleteBtn || !deleteBtn.contains(e.target)) {
                        e.stopPropagation();
                        this.openPage(page.id);
                    }
                });
                
                this.pageList.appendChild(item);
            });
            
        } catch (error) {
            console.error('Failed to load pages:', error);
        }
    }
    
    async openPage(pageId) {
        try {
            const response = await fetch(`/api/pages/${pageId}`);
            const page = await response.json();
            
            if (page.error) {
                alert('Page not found');
                return;
            }
            
            this.currentPageId = page.id;
            this.currentPageTitle = page.title || 'Untitled';
            
            // Update UI
            document.querySelectorAll('.page-item').forEach(item => item.classList.remove('active'));
            const activeItem = document.querySelector(`[data-page-id="${page.id}"]`);
            if (activeItem) {
                activeItem.classList.add('active');
            }
            
            this.pageTitleInput.value = page.title || '';
            this.blocksContainer.innerHTML = '';
            
            // Render blocks
            page.blocks.forEach((block, index) => {
                this.renderBlock(block.content, index);
            });
            
        } catch (error) {
            console.error('Failed to open page:', error);
        }
    }
    
    renderBlock(content, index) {
        const block = document.createElement('div');
        block.className = 'block-item';
        block.dataset.index = index;
        
        block.innerHTML = `
            <textarea 
                class="block-content" 
                placeholder="Type here..." 
                aria-label="Content block ${index + 1}"
                spellcheck="false"
            >${escapeHtml(this.escapeNewlines(content))}</textarea>
            <button class="delete-block-btn" title="Delete block">×</button>
        `;
        
        const textarea = block.querySelector('textarea');
        const deleteBtn = block.querySelector('.delete-block-btn');
        
        // Delete button click
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => this.deleteBlock(block.dataset.index));
        }
        
        // Auto-resize textarea
        textarea.addEventListener('input', () => {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
        });
        
        this.blocksContainer.appendChild(block);
    }
    
    async addBlock() {
        try {
            const response = await fetch(`/api/pages/${this.currentPageId}/blocks`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: '' })
            });
            
            if (!response.ok) return;
            
            const newBlock = await response.json();
            this.renderBlock(newBlock.content);
        } catch (error) {
            console.error('Failed to add block:', error);
        }
    }
    
    async deleteBlock(index) {
        try {
            const response = await fetch(`/api/pages/${this.currentPageId}/blocks/${index}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) return;
            
            // Remove the block from DOM
            const blocks = this.blocksContainer.querySelectorAll('.block-item');
            if (blocks[index]) {
                blocks[index].remove();
            }
        } catch (error) {
            console.error('Failed to delete block:', error);
        }
    }
    
    async updatePageTitle(title) {
        try {
            await fetch(`/api/pages/${this.currentPageId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: this.pageTitleInput.value || 'Untitled' })
            });
            
            // Update the active page item's display
            const activeItem = document.querySelector(`[data-page-id="${this.currentPageId}"]`);
            if (activeItem) {
                activeItem.querySelector('.page-title').textContent = 
                    escapeHtml(this.pageTitleInput.value || 'Untitled');
            }
        } catch (error) {
            console.error('Failed to update page title:', error);
        }
    }
    
    async deletePage(pageId) {
        if (!confirm('Are you sure you want to delete this page?')) return;
        
        try {
            const response = await fetch(`/api/pages/${pageId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                // Reload pages list
                this.loadPages();
            } else {
                alert('Failed to delete page');
            }
        } catch (error) {
            console.error('Failed to delete page:', error);
        }
    }
}

// Utility function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Escape newlines as <br> for textarea display
function escapeNewlines(text) {
    if (!text) return '';
    return text.replace(/\n/g, '<br>');
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.notionApp = new NotionApp();
});
