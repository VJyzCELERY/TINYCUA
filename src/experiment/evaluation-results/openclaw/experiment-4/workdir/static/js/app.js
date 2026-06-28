"""
Main application logic for Notion-like Web Application.
Handles initialization, theme management, and global UI interactions. """

// ============================================
// Configuration & Constants
// ============================================
const CONFIG = {
  API_BASE: '/api/v1',
  STORAGE_KEYS: {
    THEME_PREFERENCE: 'notion-theme-preference',
    CURRENT_WORKSPACE: 'current-workspace-id',
    PAGES_CACHE: 'pages-cache',
  },
};

// ============================================
// DOM Elements Cache (Performance)
// ============================================
class ElementCache {
  constructor() {
    this.elements = {};
  }

  get(selector) {
    if (!this.elements[selector]) {
      this.elements[selector] = document.querySelector(selector);
    }
    return this.elements[selector];
  }
}

const $ = new ElementCache();

// ============================================
// Theme Manager - Dark/Light Mode Toggle
// ============================================
class ThemeManager {
  constructor() {
    this.darkModeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    
    // Try to load saved preference first, then system default
    const savedTheme = localStorage.getItem(CONFIG.STORAGE_KEYS.THEME_PREFERENCE);
    if (savedTheme === 'dark' || !savedTheme && this.darkModeMediaQuery.matches) {
      document.body.classList.add('dark');
    }
  }

  toggle() {
    document.body.classList.toggle('dark');
    const isDark = document.body.classList.contains('dark');
    localStorage.setItem(CONFIG.STORAGE_KEYS.THEME_PREFERENCE, isDark ? 'dark' : 'light');
    this.updateThemeIcon();
  }

  setMode(mode) {
    if (mode === 'dark') {
      document.body.classList.add('dark');
    } else {
      document.body.classList.remove('dark');
    }
    localStorage.setItem(CONFIG.STORAGE_KEYS.THEME_PREFERENCE, mode);
    this.updateThemeIcon();
  }

  updateThemeIcon() {
    const toggleBtn = $('.theme-toggle-btn') || $('#theme-toggle');
    if (toggleBtn) {
      toggleBtn.innerHTML = document.body.classList.contains('dark') 
        ? '☀️' : '🌙';
    }
  }
}

// ============================================
// Sidebar Manager - Collapse/Expand Toggle
// ============================================
class SidebarManager {
  constructor() {
    this.isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
    this.applyState();
  }

  applyState() {
    const sidebar = $('.sidebar');
    if (sidebar) {
      sidebar.classList.toggle('collapsed', this.isCollapsed);
      localStorage.setItem('sidebar-collapsed', String(this.isCollapsed));
    }
  }

  toggle() {
    this.isCollapsed = !this.isCollapsed;
    this.applyState();
  }
}

// ============================================
// API Client - HTTP Requests to Backend
// ============================================
class APIClient {
  constructor(baseURL) {
    this.baseURL = baseURL || CONFIG.API_BASE;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    
    // Add Authorization header if token exists
    let headers = { ...options.headers };
    const token = localStorage.getItem('access-token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    try {
      const response = await fetch(url, {
        method: options.method || 'GET',
        headers,
        body: options.body ? JSON.stringify(options.body) : undefined,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      return { ok: true, status: response.status, json: data };
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  async get(endpoint) {
    const result = await this.request(endpoint, { method: 'GET' });
    return result.json();
  }

  async post(endpoint, body) {
    const result = await this.request(endpoint, { 
      method: 'POST', 
      headers: { 'Content-Type': 'application/json' },
      body,
    });
    return result.json();
  }

  async put(endpoint, body) {
    const result = await this.request(endpoint, { 
      method: 'PUT', 
      headers: { 'Content-Type': 'application/json' },
      body,
    });
    return result.json();
  }

  async patch(endpoint, body) {
    const result = await this.request(endpoint, { 
      method: 'PATCH', 
      headers: { 'Content-Type': 'application/json' },
      body,
    });
    return result.json();
  }

  async delete(endpoint) {
    const result = await this.request(endpoint, { method: 'DELETE' });
    return result.ok;
  }
}
