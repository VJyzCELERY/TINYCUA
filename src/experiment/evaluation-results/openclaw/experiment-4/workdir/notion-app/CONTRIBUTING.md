# 🤝 Contributing to Notion Clone

## Overview

Notion Clone is a lightweight, educational project demonstrating how to build a productivity app using Python Flask and SQLite. This guide helps you understand the codebase and contribute improvements.

---

## Project Architecture

### Backend (`backend/app.py`)
- **Flask routes** handle all API requests
- **SQLite database** stores users, pages, blocks, tables
- **Session-based authentication** (email-only login)
- **Base64 image encoding** for cover images

### Frontend (`frontend/public/`)
- **Vanilla JavaScript** - no framework dependencies
- **ContentEditable API** for rich text editing
- **CSS Grid/Flexbox** layout matching Notion's design

---

## Code Style Guide

### Python (Backend)
```python
# Use 4-space indentation
from flask import Flask, request, jsonify

@app.route('/api/endpoint', methods=['GET'])
def get_data():
    """Docstring explaining what this does."""
    data = request.get_json() if request.method == 'POST' else {}
    return jsonify({'data': data})
```

### JavaScript (Frontend)
```javascript
// Use ES6+ syntax with clear naming conventions
class NotionApp {
    constructor() {
        this.currentPageId = null;
    }
}
```

---

## Adding New Features

### 1. Add a Block Type (e.g., Code Blocks)

**Backend (`backend/app.py`):**
```python
@app.route('/api/users/<int:user_id>/pages/<int:page_id>/blocks', methods=['POST'])
def create_block(user_id, page_id):
    data = request.get_json()
    block_type = data.get('type') or 'text'
    # ... rest of implementation
```

**Frontend (`frontend/public/js/app_enhanced.js`):**
```javascript
renderSingleBlock(block, output) {
    const type = block.type || 'text';
    switch (type.toLowerCase()) {
        case 'code': 
            output += `<pre><code>${block.content}</code></pre>`;
            break;
        // ... other cases
    }
}
```

### 2. Add a New Page Type (e.g., Gallery View)

Create new route in `backend/app.py`:
```python
@app.route('/api/users/<int:user_id>/pages/gallery', methods=['GET'])
def get_gallery(user_id):
    # Implement gallery view logic
```

### 3. Add API Endpoint Documentation

Update the README.md or create separate `/docs/api.md` file.

---

## Testing Your Changes

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt --upgrade
   ```

2. **Run the app:**
   ```bash
   python backend/app.py
   ```

3. **Test in browser:** http://localhost:5000

4. **Check console for errors** (F12 → Console tab)

---

## Database Schema Changes

If modifying database structure, update `backend/init_db.py` and:
```bash
python backend/init_db.py  # Reinitialize if needed
```

Or use SQLite migration tools like Alembic for production.

---

## Best Practices

### ✅ DO
- Keep functions small and single-purpose
- Use descriptive variable/function names
- Add docstrings to complex logic
- Handle errors gracefully (return proper JSON responses)
- Test both happy path AND edge cases

### ❌ DON'T
- Mix backend/frontend in same file unless necessary
- Hardcode values - use constants/config
- Ignore database constraints
- Forget to handle null/undefined values in frontend

---

## Common Improvements to Consider

1. **Add Code Blocks** (`type: 'code'` with language detection)
2. **Callouts/Tips Box** (like Notion's quote blocks for tips)
3. **Toggle Lists** (collapsible sections)
4. **Embeds** (YouTube, Spotify, etc.)
5. **Rich Text Toolbar** (bold, italic, underline buttons)
6. **File Uploads** (local storage or S3 integration)
7. **Dark Mode Toggle** (CSS variables for theming)
8. **Markdown Support** (parse markdown input to blocks)
9. **Search/Filter Pages** (by title or content)
10. **Export as PDF/MHTML**

---

## Reporting Issues

When reporting bugs:
- Include browser version and OS
- Steps to reproduce the issue
- Console error messages (F12 → Console)
- Network tab screenshots if API-related

---

## License & Attribution

This project uses MIT license - feel free to modify, fork, or distribute!

Give credit where due:
```
Notion Clone © 2026 | Built with Flask + SQLite
Inspired by Notion's block-based editing approach.
```
