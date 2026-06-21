# 🏛️ Architecture Overview - Notion Clone

## High-Level Design

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (Client)                      │
│  ┌──────────────┬────────────────────────────────────┐  │
│  │   HTML/CSS/JS│     Flask Backend (Python)         │  │
│  │              │                                     │  │
│  │ - app_enhanced.js    │ Database: SQLite            │  │
│  │ - auth.js           │                             │  │
│  └──────────────┴─────────┬──────────────────────────┘  │
└────────────────────────────┼────────────────────────────┘
                            │ HTTP/JSON
                    ┌───────▼────────┐
                    │ Flask Server   │
                    │ (port 5000)    │
                    ├────────────────┤
                    │ API Endpoints: │
                    │ - /api/login   │
                    │ - /pages/*     │
                    │ - /blocks/*    │
                    └───────▲────────┘
                            │ SQL Queries
                    ┌───────▼────────┐
                    │  SQLite DB     │
                    ├────────────────┤
                    │ users, pages   │
                    │ blocks, tables │
                    └────────────────┘
```

---

## Data Flow Example: Creating a Page

### User Action:
Click "+ New Page" → Enter "My Notes"

### Frontend (JavaScript):
```javascript
// 1. Show prompt for title
title = prompt("Enter page title:"); // "My Notes"

// 2. Call backend API to create page
fetch('/api/users/YOUR_USER_ID/pages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
        title: "My Notes",
        icon: ''  // empty icon for now
    })
});
```

### Backend (Python/Flask):
```python
# 3. Receive POST request at /api/users/{id}/pages
@app.route('/api/users/<int:user_id>/pages', methods=['POST'])
def create_page(user_id):
    data = request.get_json()  # {title: "My Notes"}
    
    # 4. Query database to insert new page
    cursor.execute('''INSERT INTO pages (user_id, title) VALUES (?, ?)
        ''', (user_id, "My Notes"))
    db.commit()
    new_page_id = cursor.lastrowid
```

### Database:
```sql
-- 5. SQLite creates: id=1, user_id=X, title="My Notes"
CREATE TABLE pages (
    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    title TEXT NOT NULL
)
```

### Frontend Response:
```javascript
// 6. Backend returns: {"pageId": "1", "userId": "X"}
app.loadPages(); // Reload page list to show new page
location.reload(); // Refresh browser to display it
```

---

## Database Schema Details

### users Table:
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,      -- Email for login
    name TEXT DEFAULT 'User',        -- Display name (auto-generated)
    created_at TIMESTAMP             -- When user was created
);
```

### pages Table:
```sql
CREATE TABLE pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,  -- Link to user
    title TEXT NOT NULL,                                      -- Page title
    icon TEXT DEFAULT '',                                     -- Emoji icon (e.g., "📝")
    cover_image BLOB,                                         -- Base64-encoded image data
    parent_page_id INTEGER REFERENCES pages(id),             -- For nested pages
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### blocks Table:
```sql
CREATE TABLE blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER REFERENCES pages(id) ON DELETE CASCADE,   -- Link to parent page
    type TEXT NOT NULL DEFAULT 'text',                        -- Block type: h1, h2, text, etc.
    content TEXT NOT NULL DEFAULT '',                         -- Text content of block
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP            -- When added
);
```

### database_tables Table:
```sql
CREATE TABLE database_tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,   -- Link to user
    page_id INTEGER REFERENCES pages(page_id),                -- Parent link (optional)
    title TEXT NOT NULL,                                      -- User-facing table name
    columns_data JSON DEFAULT '{}',                           -- Column definitions as JSON
    rows_data JSON DEFAULT '[]'                               -- Sample data as JSON
);
```

---

## API Endpoint Reference

### Authentication:
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/login` | Email-based login (no password) |

### Pages Management:
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/users/{id}/pages` | List all root-level pages |
| POST | `/api/users/{id}/pages` | Create new page with title/icon/coverImage |
| PUT | `/api/users/{id}/pages/{page_id}` | Update page metadata (title, icon, cover) |

### Blocks Management:
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/users/{id}/pages/{page_id}/blocks` | Add single block to page |
| PUT | `/api/users/{id}/pages/{page_id}` | Replace all blocks in page |

### Database Tables:
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/users/{id}/pages/tables` | Create new database table |
| PUT | `/api/users/{id}/pages/tables/*` | Add rows to existing table |

---

## Security Considerations

### Current Implementation:
- ✅ Session-based auth with Flask (server-side sessions)
- ✅ SQL injection prevention via parameterized queries
- ⚠️ No password hashing (email-only login for simplicity)
- ⚠️ CORS enabled for all origins (development mode)
- ⚠️ Images stored as base64 in SQLite (not scalable)

### Recommended Production Improvements:
1. Add bcrypt/argon2 for password hashing
2. Implement JWT tokens with expiration
3. Set `CORS(app, resources={"r/*": {"origins":"[https://yourdomain.com]"}})`
4. Use HTTPS/TLS in production environment
5. Add input sanitization (XSS prevention)
6. Rate limiting on API endpoints
7. SQL query logging for monitoring
8. Error tracking with Sentry or similar
9. Input validation using Marshmallow/Pydantic
10. CSRF protection headers

---

## Performance Characteristics

### SQLite:
- Single-file database (no setup required)
- Good for < 1M rows, typical use case here: thousands of pages/blocks
- `ON DELETE CASCADE` ensures cleanup when users delete
- BLOB storage for images works but not ideal for large apps

### Flask:
- Synchronous request/response model
- Single-threaded by default (good enough for single-user app)
- For multi-user/concurrent use, consider Gunicorn + multiple workers

### Frontend JavaScript:
- No framework overhead - vanilla JS is lightweight
- ContentEditable API provides instant feedback to users
- Minimal memory footprint compared to React/Vue apps

---

## Deployment Considerations

### Local Development (Current):
```bash
python backend/app.py  # Runs on localhost:5000
```

### Production Options:
1. **Gunicorn + Nginx** - Standard Python WSGI server setup
2. **uWSGI + Nginx** - Alternative high-performance option
3. **Flask-RESTX** - For more RESTful API conventions
4. **Docker containerization** for easy deployment
5. **Cloud hosting**: Heroku, Railway, Render (all support Flask)

### Database Migration:
For production with multiple users or large datasets:
1. Switch to PostgreSQL/MySQL
2. Use Alembic for schema migrations
3. Separate database per tenant/user if needed
4. Implement connection pooling
5. Add read replicas for scaling reads vs writes
