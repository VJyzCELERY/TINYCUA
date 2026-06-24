"""
Block manipulation functions for Notion-like Web Application.
Handles block creation, deletion, moving, and formatting operations. """

class BlockManager {
  constructor(apiClient) {
    this.api = apiClient;
    this.pageId = null; // Will be set when a page is opened
  }

  /**
   * Add a new block at the end of current page
   */
  async addBlock(blockType, content = '') {
    if (!this.pageId) throw new Error('No active page');
    
    const response = await this.api.post(`/blocks/${this.pageId}`, { 
      block_type: blockType,
      text_content: content
    });
    return response;
  }

  /**
   * Add a new block at specific position (for inserting before/after)
   */
  async addBlockAtPosition(blockType, content, position) {
    if (!this.pageId) throw new Error('No active page');
    
    const response = await this.api.post(`/blocks/${this.pageId}?position_index=${position}`, { 
      block_type: blockType,
      text_content: content
    });
    return response;
  }

  /**
   * Update existing block content and properties
   */
  async updateBlock(blockId, updates) {
    if (!this.pageId || !blockId) throw new Error('Invalid page or block ID');
    
    const response = await this.api.put(`/blocks/${this.pageId}/${blockId}`, { ...updates });
    return response;
  }

  /**
   * Delete a block (soft delete - restore with ?hard_delete=false)
   */
  async deleteBlock(blockId, hardDelete = false) {
    if (!this.pageId || !blockId) throw new Error('Invalid page or block ID');
    
    const response = await this.api.delete(`/blocks/${this.pageId}/${blockId}?hard_delete=${hardDelete}`);
    return response;
  }

  /**
   * Get all blocks for current page
   */
  async getBlocks() {
    if (!this.pageId) throw new Error('No active page');
    
    const response = await this.api.get(`/blocks/${this.pageId}`);
    return response;
  }

  /**
   * Get a single block by ID
   */
  async getBlock(blockId) {
    if (!this.pageId || !blockId) throw new Error('Invalid page or block ID');
    
    const response = await this.api.get(`/blocks/${this.pageId}/${blockId}`);
    return response;
  }

  /**
   * Toggle code/callout block collapse state
   */
  async toggleBlockCollapse(blockId, collapsed) {
    if (!this.pageId || !blockId) throw new Error('Invalid page or block ID');
    
    const response = await this.api.put(`/blocks/${this.pageId}/${blockId}`, { is_collapsed: collapsed });
    return response;
  }

  /**
   * Toggle todo list item completion state
   */
  async toggleTodo(blockId, checked) {
    if (!this.pageId || !blockId) throw new Error('Invalid page or block ID');
    
    const response = await this.api.put(`/blocks/${this.pageId}/${blockId}`, { todo_checked: checked });
    return response;
  }

  /**
   * Get available slash command options based on cursor position and context
   */
  async getSlashMenuOptions(blockType) {
    const validTypes = [
      'text', 'h1', 'h2', 'h3', 
      'bulleted_list_item', 'numbered_list_item',
      'todo', 'quote', 'code_block', 'image', 'callout'
    ];

    return {
      options: validTypes.map(type => ({
        type,
        label: this.getBlockLabel(type),
        icon: this.getBlockIcon(type),
        shortcut: this.getShortcutForType(type)
      })),
      position: 'after' // Insert block after current cursor position
    };
  }

  getBlockLabel(type) {
    const labels = {
      'text': 'Text',
      'h1': 'Heading 1',
      'h2': 'Heading 2', 
      'h3': 'Heading 3',
      'bulleted_list_item': 'Bulleted List',
      'numbered_list_item': 'Numbered List',
      'todo': 'To-do List',
      'quote': 'Quote',
      'code_block': 'Code',
      'image': 'Image',
      'callout': 'Callout'
    };
    return labels[type] || type.replace('_', ' ').replace(/([A-Z])/g, ' $1');
  }

  getBlockIcon(type) {
    const icons = {
      'text': '', // Empty for text blocks (uses emoji in content)
      'h1': '#', 
      'h2': '##',
      'h3': '###',
      'bulleted_list_item': '•',
      'numbered_list_item': '1.',
      'todo': '[ ]',
      'quote': '"""',
      'code_block': '</>',
      'image': '<img>',
      'callout': '' // Empty for callouts
    };
    return icons[type] || type;
  }

  getShortcutForType(type) {
    const shortcuts = {
      'h1': 'Cmd/Ctrl + Alt + 1',
      'h2': 'Cmd/Ctrl + Alt + 2',
      'h3': 'Cmd/Ctrl + Alt + 3'
    };
    return shortcuts[type] || null;
  }
}
