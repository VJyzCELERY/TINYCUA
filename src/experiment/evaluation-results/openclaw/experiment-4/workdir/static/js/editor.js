"""
Rich text editor implementation for Notion-like Web Application.
Handles block creation, selection management, and slash command menu. """

class BlockEditor {
  constructor() {
    this.blocks = new Map(); // ID -> Block object
    this.currentBlockId = null;
    this.selectedBlocks = new Set();
    this.blockTemplate = document.createElement('template');
    
    this.init();
  }

  init() {
    // Load existing blocks from storage or empty state
    const savedBlocks = localStorage.getItem(CONFIG.STORAGE_KEYS.PAGES_CACHE);
    if (savedBlocks) {
      try {
        this.blocks = new Map(JSON.parse(savedBlocks));
      } catch (e) {
        console.error('Failed to load cached blocks:', e);
      }
    }

    // Set up event listeners for block interactions
    document.addEventListener('click', (e) => this.handleBlockClick(e));
    
    // Handle keyboard shortcuts
    document.addEventListener('keydown', (e) => this.handleKeyDown(e));
  }

  createBlock(type, content = null, positionAtEnd = true) {
    const blockId = `block-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    let newBlock = {
      id: blockId,
      type: this.getBlockType(type),
      text_content: content || '',
      language: null,
      is_collapsed: false,
      list_style: null,
      todo_checked: false,
      position_index: 0, // Will be set when inserted
    };

    const blocks = Array.from(this.blocks.values());
    
    if (positionAtEnd) {
      newBlock.position_index = blocks.length > 0 ? Math.max(...blocks.map(b => b.position_index || 0)) + 1 : 0;
    }

    this.blocks.set(blockId, newBlock);
    localStorage.setItem(CONFIG.STORAGE_KEYS.PAGES_CACHE, JSON.stringify(Array.from(this.blocks.entries())));

    // Render the block in DOM (would be integrated with main editor)
    return newBlock;
  }

  getBlockType(shortName) {
    const typeMap = {
      'text': 'text',
      'h1': 'h1',
      'h2': 'h2',
      'h3': 'h3',
      '/bullet-list': 'bulleted_list_item',
      '/numbered-list': 'numbered_list_item',
      '/todo': 'todo',
      '/quote': 'quote',
      '/code': 'code_block',
      '/image': 'image',
      '/callout': 'callout',
    };

    return typeMap[shortName] || shortName;
  }

  handleBlockClick(e) {
    // Select clicked block by focusing its contenteditable element
    const blockEl = e.target.closest('.block');
    if (blockEl && !e.ctrlKey && !e.metaKey) {
      this.selectBlock(blockEl.dataset.id);
    }
  }

  selectBlock(blockId) {
    // Deselect previous selection
    document.querySelectorAll('.selected').forEach(el => el.classList.remove('selected'));
    
    const block = this.blocks.get(blockId);
    if (!block) return;

    // Highlight selected block
    const blockEl = document.querySelector(`[data-id="${block.id}"]`);
    if (blockEl) {
      blockEl.classList.add('selected');
      this.currentBlockId = blockId;
    }
  }
