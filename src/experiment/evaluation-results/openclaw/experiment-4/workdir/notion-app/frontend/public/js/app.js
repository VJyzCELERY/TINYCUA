/**
 * Notion Clone - Frontend Application
 */

class NotionApp {
    constructor() {
        this.currentPageId = null;
        this.currentUserEmail = localStorage.getItem('user_email') || '';
        this.userPages = [];
        
        this.init();
    }
    
    async init() {
        // Check if user is logged in
        const isLoggedIn = !!this.currentUserEmail && !localStorage.getItem('show_auth');
        
        if (isLoggedIn) {
            await this.loadPages();
            this.renderPageList();
        } else {
            this.showAuthScreen();
        }
    }
    
    // ============== Authentication ==============
    showAuthScreen() {
        document.body.innerHTML = `
            <div class="auth-screen">
                <div class="auth-box">
                    <h2>Welcome to Notion Clone</h2>
                    <form id="login-form" class="auth-form">
                        <input type="email" placeholder="Email address" 
                               name="email" required value="${this.currentUserEmail}" autofocus>
                        <button type="submit" class="btn-primary">Sign In</button>
                    </form>
                </div>
            </div>
        `;
        
        document.getElementById('login-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData.entries());
            
            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                if (response.ok) {
                    const result = await response.json();
                    this.currentUserEmail = data.email;
                    localStorage.setItem('user_email', data.email);
                    
                    // Hide auth screen and load pages
                    document.body.innerHTML = `"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Notion Clone</title>
    <link rel="stylesheet" href="/css/style.css">
</head>
<body>
    <div id="app"></div>
    <script src="/js/app.js"><\/script>
</body>
</html>"""
                    `;
                    await this.loadPages();
                } else {
                    alert('Login failed');
                }
            } catch (error) {
                console.error(error);
            }
        });
    }
    
    // ============== Page Management ==============
    async loadPages() {
        try {
            const response = await fetch(`/api/users/${this.currentUserEmail.split('@')[0]}/pages`); 
            if (response.ok) {
                const result = await response.json();
                this.userPages = result.pages;
                console.log('Loaded pages:', this.userPages);
            }
        } catch (error) {
            console.error('Failed to load pages:', error);
        }
    }
    
    renderPageList() {
        const container = document.getElementById('app');
        if (!container) return;
        
        let html = `
            <div class="sidebar">
                <div class="sidebar-header">📄 Notion Clone</div>
                `;
        
        this.userPages.forEach((page, index) => {
            const isActive = this.currentPageId === page.id;
            html += `
                <div class="nav-item ${isActive ? 'active' : ''}" onclick="app.loadPage(${index})">
                    📄 ${this.escapeHtml(page.title)}
                </div>
            `;
        });
        
        // Add new page button
        html += `
                <div class="nav-item" onclick="app.createNewPage()">
                    + New Page
                </div>
            </div>
        `;
        
        if (this.userPages.length === 0) {
            html += `
                <div class="main-content">
                    <div class="empty-state">
                        <h3>No pages yet</h3>
                        <p>Click "New Page" to create your first page!</p>
                    </div>
                </div>
            `;
        } else {
            html += `
                <div id="pages-container" class="main-content"></div>
            `;
        }
        
        container.innerHTML = html;
    }
    
    // ============== Page Editor ==============
    loadPage(index) {
        const page = this.userPages[index];
        if (!page || !page.title) return;
        
        this.currentPageId = page.id;
        console.log('Loading page:', page);
        
        // Fetch current content
        this.fetchPageContent(page.id).then(content => {
            this.renderEditor(container, content.page, content.blocks);
        });
    }
    
    fetchPageContent(pageId) {
        return fetch(`/api/users/${this.currentUserEmail.split('@')[0]}/pages/${pageId}`)
            .then(res => res.json());
    }
    
    async createNewPage() {
        const title = prompt('Enter page title:');
        if (!title) return;
        
        try {
            const response = await fetch(`/api/users/${this.currentUserEmail.split('@')[0]}/pages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, icon: '', coverImage: null })
            });
            
            if (response.ok) {
                await this.loadPages();
                // Reload to show new page
                location.reload();
            }
        } catch (error) {
            console.error('Failed to create page:', error);
        }
    }
    
    renderEditor(container, page, blocks = []) {
        const html = `
            <div class="page-header">
                ${this.escapeHtml(page.title)}
            </div>
            <div id="editor" class="editor-container block-editor prose">
                `;
        
        // Render initial content
        blocks.forEach(block => {
            const type = block.type || 'text';
            if (type === 'h1') html += `<h1>${this.escapeHtml(block.content)}</h1>`;
            else if (type === 'h2') html += `<h2>${this.escapeHtml(block.content)}</h2>`;
            else if (type === 'h3') html += `<h3>${this.escapeHtml(block.content)}</h3>`;
            else if (type.startsWith('bullet')) {
                const listItems = block.content.split('\n').filter(Boolean);
                listItems.forEach(item => {
                    html += `<li><span contenteditable="true">${this.escapeHtml(item)}<\/span></li>`;
                });
                html += '</ul>';
            } else if (type.startsWith('number')) {
                const listItems = block.content.split('\n').filter(Boolean);
                listItems.forEach((item, idx) => {
                    html += `<li><span contenteditable="true">${idx + 1}. ${this.escapeHtml(item)}<\/span></li>`;
                });
                html += '</ol>';
            } else if (type === 'quote') {
                html += `<blockquote>\"${this.escapeHtml(block.content)}\"</blockquote>`;
            }
        });
        
        container.innerHTML = html;
    }
    
    // Escape HTML to prevent XSS
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new NotionApp();
});
