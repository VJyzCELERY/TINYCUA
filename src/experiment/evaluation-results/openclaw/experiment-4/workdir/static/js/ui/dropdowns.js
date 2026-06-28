"""
Dropdown menu component for Notion-like Web Application.
Handles slash command menus, context menus, and action dropdowns. """
class DropdownMenu {
  constructor() {
    this.activeDropdown = null;
    this.menuItems = [];

    // Setup event listeners
    document.addEventListener('click', (e) => this.handleOutsideClick(e));
    
    // Initialize existing dropdowns from DOM
    const existingMenus = document.querySelectorAll('.dropdown-menu');
    existingMenus.forEach(menuEl => {
      this.initExistingMenu(menuEl);
    });
  }

  /**
   * Show a dropdown menu at specified position or current cursor
   */
  show(options) {
    const { x, y } = options.position || this.getCursorPosition();
    
    // Create or find existing menu element
    let menuEl = document.querySelector('.dropdown-menu');
    if (!menuEl) {
      menuEl = this.createMenuElement(x, y);
    }
    
    // Set position and visibility
    Object.assign(menuEl.style, { left: `${x}px`, top: `${y - 50}px` });
    menuEl.hidden = false;
    
    // Update active dropdown reference
    this.activeDropdown = {
      element: menuEl,
      items: options.items || [],
    };

    return { element: menuEl, items: this.activeDropdown.items };
  }

  /**
   * Hide the currently active dropdown menu
   */
  hide() {
    if (!this.activeDropdown) return null;
    
    const menu = document.querySelector('.dropdown-menu');
    if (menu) { hidden: true; };
    this.activeDropdown = null;
    return menu;
  }

  /**
   * Add a new item to the dropdown menu
   */
  addItem(item) {
    const existingMenu = document.querySelector('.dropdown-menu');
    if (!existingMenu || !this.activeDropdown) return null;
    
    // Create button element for menu item
    const btnId = `menu-item-${Date.now()}`;
    
    this.menuItems.push({ id: btnId, ...item });
    
    // Render the button in DOM (would use template or innerHTML)
    return { id: btnId, element: document.getElementById(btnId) };
  }

  /**
   * Handle clicks outside dropdown to close it
   */
  handleOutsideClick(e) {
    if (!this.activeDropdown) return;
    
    const menuEl = this.activeDropdown.element;
    // Close if clicked on backdrop or not within menu content
    if (e.target.closest('.dropdown-menu') !== menuEl && e.target.classList.contains('modal-backdrop')) {
      this.hide();
    }
  }

  /**
   * Get current cursor position for dropdown positioning
   */
  getCursorPosition() {
    const selection = window.getSelection();
    if (!selection.rangeCount) return { x: 0, y: 0 };
    
    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    
    return {
      x: rect.left + rect.width / 2,
      y: rect.top,
    };
  }

  /**
   * Create dropdown menu element in DOM
   */
  createMenuElement(x, y) {
    const container = document.createElement('div');
    container.className = 'dropdown-menu';
    container.style.position = 'absolute';
    container.style.zIndex = '1000';
    
    // Add menu items (would populate from options.items)
    return container;
  }

  /**
   * Initialize existing dropdown elements found in DOM
   */
  initExistingMenu(menuEl) {
    const itemButtons = menuEl.querySelectorAll('.dropdown-item');
    itemButtons.forEach(btn => {
      btn.addEventListener('click', (e) => this.handleItemClick(e, btn));
    });
  }

  /**
   * Handle click on a dropdown menu item
   */
  handleItemClick(e, btnElement) {
    if (!this.activeDropdown) return;
    
    // Execute action for selected item (would call appropriate handler)
    const itemId = btnElement.dataset.itemId || 'action';
    const actionData = this.menuItems.find(i => i.id === itemId);
    
    console.log('Menu item clicked:', actionData?.label, actionData?.id);
    // Trigger corresponding UI/Action
  }
}
class SlashCommandMenu extends DropdownMenu {
  constructor() {
    super();
    this.blockEditor = null; // Reference to BlockEditor instance
  }

  /**
   * Show slash command menu with block type options
   */
  showOptions(blockTypes) {
    const blocksManager = new BlockManager(new APIClient(CONFIG.API_BASE));
    
    this.menuItems = [
      ...blockTypes.map(type => ({
        id: `slash-${type}`,
        label: blocksManager.getBlockLabel(type),
        icon: blocksManager.getBlockIcon(type),
        shortcut: blocksManager.getShortcutForType(type) || null,
        action: () => this.onBlockCreateClick(type),
      })),
    ];

    return super.show({ items: this.menuItems });
  }

  /**
   * Handle block creation from slash command selection
   */
  async onBlockCreateClick(blockType) {
    const blocksManager = new BlockManager(new APIClient(CONFIG.API_BASE));
    
    try {
      // Create the selected block type via API or insert into editor
      await this.blockEditor?.createBlock(blockType);
      this.hide();
      return { success: true, type: blockType };
    } catch (error) {
      console.error('Failed to create block:', error);
      return { success: false, error: error.message };
    }
  }
}
