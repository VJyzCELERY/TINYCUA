/**
 * Notion-like Workspace Application
 * Handles CRUD operations for text blocks with SQLite backend
 */

class App {
    constructor() {
        this.blocksContainer = document.getElementById('blocks-container');
        this.addBlockBtn = document.getElementById('add-block-btn');
        this.previewBox = document.getElementById('block-preview');
        
        // State
        this.blocks = [];
        this.selectedBlockId = null;
        
        // Bind events
        this.addBlockBtn.addEventListener('click', () => this.addNewBlock());
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (this.selectedBlockId !== null) {
                const currentBlock = this.blocks.find(b => b.id === this.selectedBlockId);
                
                // Delete with Ctrl/Cmd + Backspace
                if ((e.ctrlKey || e.metaKey) && e.key === 'Backspace') {
                    e.preventDefault();
                    this.deleteSelectedBlock();
                    return;
                }
                
                // Move up/down with Tab (when not in an input)
                const isActiveElementInput = document.activeElement.tagName.toLowerCase() === 'textarea';
                if (!isActiveElementInput && e.key === 'Tab') {
                    e.preventDefault();
                    this.moveBlock('up');
                    return;
                }
            }
        });
        
        // Initialize
        this.loadBlocks();
    }
    
    async loadBlocks() {
        try {
            const response = await fetch('/api/blocks');
            if (!response.ok) throw new Error('Failed to load blocks');
            
            this.blocks = await response.json();
            this.selectedBlockId = null;
            this.renderBlocks();
        } catch (error) {
            console.error('Error loading blocks:', error);
            this.showPreview('Error loading blocks. Please refresh the page.');
        }
    }
    
    renderBlocks() {
        if (!this.blocks || !this.blocks.length) {
            this.blocksContainer.innerHTML = `
                <div class="empty-state">
                    <h3>No blocks yet</h3>
                    <p>Click "+ Add Block" to create your first block</p>
                </div>`;
            return;
        }
        
        const html = this.blocks.map(block => {
            const isSelected = this.selectedBlockId === block.id;
            
            return `
                <div class="block ${isSelected ? 'selected' : ''}" data-id="${block.id}">
                    <textarea 
                        class="block-content"
                        placeholder="Type your content here..."
                        rows="1"
                        oninput="this.style.height = ''; this.style.height = (this.scrollHeight - 24) + 'px'"
                        onchange="app.updateBlock(${JSON.stringify(block)}, event.target.value)"
                    >${escapeHtml(block.content)}</textarea>
                    
                    <div class="block-actions">
                        <button 
                            class="delete-btn" 
                            onclick="app.deleteBlock(${block.id})"
                            aria-label="Delete this block"
                        >&times;</div>`;
        }).join('');
        
        this.blocksContainer.innerHTML = html;
    }
    
    async updateBlock(block, content) {
        try {
            const response = await fetch('/api/blocks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: block.id, content, position: block.position })
            });
            
            if (!response.ok) throw new Error('Failed to update block');
        } catch (error) {
            console.error('Error updating block:', error);
        }
    }
    
    async deleteBlock(blockId) {
        try {
            const response = await fetch(`/api/blocks/${blockId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) throw new Error('Failed to delete block');
        } catch (error) {
            console.error('Error deleting block:', error);
        }
    }
    
    async moveBlock(direction) {
        const currentBlock = this.blocks.find(b => b.id === this.selectedBlockId);
        if (!currentBlock) return;
        
        let newIndex;
        if (direction === 'up' && currentBlock.position > 0) {
            newIndex = currentBlock.position - 1;
        } else if (direction === 'down') {
            const maxIndex = Math.max(0, (this.blocks.length - 1) / 2);
            if (currentBlock.position < maxIndex) {
                newIndex = currentBlock.position + 1;
            } else {
                return; // Can't move further down
            }
        }
        
        if (newIndex !== undefined) {
            this.blocks.push({
                id: this.selectedBlockId,
                content: '',
                position: newIndex
            });
            
            const block = this.blocks.find(b => b.id === this.selectedBlockId);
            if (block) {
                block.position = newIndex;
            }
            
            // Update all blocks with their new positions
            for (const b of this.blocks) {
                fetch('/api/blocks', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: b.id, content: b.content, position: b.position })
                }).catch(console.error);
            }
            
            this.loadBlocks();
        }
    }
    
    showPreview(text) {
        this.previewBox.textContent = text;
        this.previewBox.classList.remove('hidden');
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

// Initialize app when DOM is ready
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new App();
});
