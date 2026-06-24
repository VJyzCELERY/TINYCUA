"""
Modal dialogs for Notion-like Web Application.
Handles page properties, image upload modals, and other dialog interfaces. """
class ModalManager {
  constructor() {
    this.activeModal = null;
    this.modals = {};

    // Setup event delegation on document
    document.addEventListener('click', (e) => this.handleDocumentClick(e));
    
    // Initialize modal containers if they exist in DOM
    const existingModals = document.querySelectorAll('.modal-backdrop');
    existingModals.forEach(modalEl => {
      const id = modalEl.dataset.modalId;
      this.modals[id] = { element: modalEl, isOpen: false };
    });
  }

  /**
   * Open a modal dialog
   */
  open(id) {
    if (!this.modals[id]) return null;
    
    const modal = this.modals[id];
    modal.isOpen = true;
    document.body.style.overflow = 'hidden'; // Prevent background scrolling
    
    // Close active modal first (stacking not supported)
    if (this.activeModal) {
      this.close(this.activeModal);
    }
    
    this.activeModal = id;
    return modal.element.querySelector('.modal-content');
  }

  /**
   * Close the currently active modal
   */
  close() {
    if (!this.activeModal) return null;
    
    const modalEl = document.querySelector(`[data-modal-id="${this.activeModal}"]`);
    if (modalEl) {
      // Animate out or simply hide
      modalEl.style.opacity = '0';
      setTimeout(() => {
        modalEl.hidden = true;
        this.modals[this.activeModal].isOpen = false;
      }, 150);
    }
    
    document.body.style.overflow = '';
    this.activeModal = null;
    return modalEl;
  }

  /**
   * Handle clicks outside modal content to close
   */
  handleDocumentClick(e) {
    if (!this.activeModal) return;
    
    const activeModalEl = document.querySelector(`[data-modal-id="${this.activeModal}"]`);
    if (e.target === e.currentTarget || e.target.classList.contains('modal-backdrop')) {
      this.close();
    }
  }

  /**
   * Create a new modal dynamically (for programmatic use)
   */
  create(id, options = {}) {
    const containerId = `modal-${id}`;
    
    // Check if element already exists
    let existingEl = document.getElementById(containerId);
    if (!existingEl) {
      this.modals[id] = { element: null, isOpen: false };
      return null;
    }
    
    const modalContent = options.content || '';
    const title = options.title || 'Dialog';
    const footerButtons = options.footerButtons || [];

    // Render modal HTML structure (would use template literal or render function)
    this.modals[id].element = existingEl;
    return {
      element: existingEl,
      content: modalContent,
      title: title,
      footerButtons: footerButtons,
    };
  }
}
