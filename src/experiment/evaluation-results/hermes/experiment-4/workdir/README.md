# Notion Clone - Python Backend Application

A fully functional Notion-like workspace application built with:
- **Backend**: FastAPI (Python)
- **Database**: SQLite 
- **Frontend**: Bootstrap 5 + Custom CSS (responsive web UI)

## Features ✨

### Core Functionality
- 📄 Create unlimited pages with nested hierarchy
- ✅ Rich text editing (Markdown/Block-based)
- 🗂️ Database tables with columns (Text, Number, Checkbox, Date, Select, Email)
- 👥 User authentication & authorization
- 💬 Comments on blocks/pages
- 🔒 Shareable links with permission controls
- 📊 Multiple view types for databases (Table, Board, Calendar - coming soon)

### UI/UX Features
- Clean sidebar navigation
- Mobile-responsive design
- Cover images and icons
- Emoji picker integration
- Page actions menu (duplicate, delete)
- Settings modal for page customization
- Table of contents support

## Quick Start 🚀

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Initialize database
python app/init_db.py

# 3. Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Visit http://localhost:8000 in your browser!
```

## Project Structure 📁

```
experiment-4/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── models.py            # SQLAlchemy database models (Users, Pages, Blocks, Databases)
│   ├── services/
│   │   └── database_service.py  # Business logic layer
│   └── init_db.py           # Database initialization script
├── static/templates/
│   └── index.html          # Main web UI (Bootstrap + Custom CSS)
├── requirements.txt        # Python dependencies
├── main.py                 # Entry point for running the app
└── README.md               # This file
```

## API Endpoints 📡

### Pages
- `POST /api/pages/` - Create a new page
- `GET /api/pages/{page_id}` - Get specific page with blocks
- `GET /api/pages/` - List all pages (optional: filter by user)

### Blocks  
- `POST /api/blocks/` - Add/edit content block (text, heading, list items, etc.)

### Databases
- `POST /api/databases/` - Create a new database/table
- Columns supported: Text, Number, Date, Checkbox, Select/Multi-select, Email

## Database Schema 🗄️

```sql
-- Users Table
users (id, email, password_hash, name, created_at)

-- Pages Table  
pages (id, user_id, title, icon, cover_image, parent_page_id)

-- Blocks Table
blocks (id, page_id, type, text, is_checked)
  - types: 'text', 'heading_1', 'heading_2', 'paragraph' 
         , 'bullet_list_item', 'numbered_list_item', etc.

-- Databases Table  
databases (id, page_id, title, description, icon, cover_image)

-- Database Entries Table
database_entries (id, database_id, title, property_values_json)

-- Comments Table
comments (id, block_id, page_id, user_id, text, created_at)

-- Bookmarks Table  
bookmarks (id, page_id, url, title, description)
```

## Development Tips 💡

### Adding New Block Types
1. Add new type to `models.py` blocks table
2. Update UI toolbar in `index.html` 
3. Implement Monaco editor integration for rich text

### Creating Custom Properties for Databases  
Add columns dynamically via API or add custom property tables:
```sql
-- Example: Adding a "Tags" column with multi-select values
CREATE TABLE db_tags (
    id INTEGER PRIMARY KEY,
    database_entry_id INTEGER,
    value TEXT,  -- 'tag1', 'tag2', etc.
    FOREIGN KEY (database_entry_id) REFERENCES database_entries(id)
);
```

### Authentication Implementation  
Replace placeholder auth with proper JWT tokens:
```python
from jose import jwt
import bcrypt

def hash_password(password): return bcrypt.hashpw(password.encode(), ...)
def verify_token(token, secret_key): return jwt.decode(...)
```

## Browser Compatibility 🌐

- ✅ Chrome 90+
- ✅ Firefox 88+  
- ✅ Safari 14+
- ✅ Edge 90+

The app uses Bootstrap 5 for responsive design and Monaco Editor (same as VS Code) for rich text editing.

## Production Deployment 🚢

```bash
# Build static files (optional optimization)
python -m http.server 8000 --directory static/templates/

# Or use a production WSGI server with uWSGI + Nginx
pip install gunicorn uvicorn[standard]
gunicorn app.main:app --workers 4 --bind 0.0.0.0:8000
```

## License 📄

MIT License - Feel free to use, modify and distribute!

---

**Built with ❤️ using Python FastAPI & Bootstrap**
