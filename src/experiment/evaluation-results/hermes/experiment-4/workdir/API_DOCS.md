# Notion Clone - API Documentation

## Base URL
`http://localhost:8000/api/` (development) or `https://yourdomain.com/api/` (production)

---

## Authentication 🎫

### POST `/api/auth/login`
Login and get authentication token.

**Request:**
```json
{
  "username": "user@example.com",
  "password": "secure_password"
}
```

**Response:**
```json
{
  "message": "Logged in successfully",
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

---

## Pages API 📄

### POST `/api/pages/` - Create Page
Create a new page.

**Request:**
```json
{
  "title": "My New Page",
  "icon": "🚀",
  "cover_image": null,
  "parent_page_id": null,
  "user_id": 1
}
```

**Response:**
```json
{
  "id": 5,
  "title": "My New Page",
  "icon": "🚀"
}
```

---

### GET `/api/pages/{page_id}` - Get Page with Blocks
Retrieve a specific page and its blocks.

**Response:**
```json
{
  "id": 5,
  "title": "My New Page", 
  "icon": "🚀",
  "blocks": [
    {
      "id": 101,
      "type": "heading_1",
      "text": "# Welcome to My Project"
    },
    {
      "id": 102, 
      "type": "paragraph",
      "text": "This is the beginning of my project documentation."
    }
  ]
}
```

---

### GET `/api/pages/` - List All Pages (optional: filter by user_id)

**Response:**
```json
[
  {
    "id": 5,
    "title": "My New Page",
    "icon": "🚀"
  },
  {
    "id": 3,
    "title": "Project Ideas", 
    "icon": "💡"
  }
]
```

---

## Blocks API 🧱

### POST `/api/blocks/` - Create Block
Add a new content block to a page.

**Request:**
```json
{
  "page_id": 5,
  "type": "heading_2", 
  "text": "## Subsection Title"
}
```

**Response:**
```json
{
  "id": 103,
  "type": "heading_2",
  "text": "## Subsection Title"
}
```

---

### POST `/api/blocks/{block_id}/update` - Update Block Text
Modify existing block content.

**Request:**
```json
{
  "text": "# Updated Heading"
}
```

---

### DELETE `/api/blocks/{block_id}` - Delete Block
Remove a block from the page.

---

## Databases API 🗂️

### POST `/api/databases/` - Create Database/Table
Create a new database table on a page.

**Request:**
```json
{
  "page_id": 5,
  "title": "Tasks Database", 
  "icon": "📊"
}
```

---

### GET `/api/databases/{database_id}` - Get Database Schema & Data
Retrieve database structure and entries.

**Response:**
```json
{
  "id": 1,
  "title": "Tasks Database", 
  "icon": "📊",
  "properties": [
    {"name": "Name", "type": "text"},
    {"name": "Status", "type": "select"},
    {"name": "Priority", "type": "select"}
  ],
  "entries": [
    {
      "id": 1,
      "title": "Build Website", 
      "property_values": {
        "Name": "Build Website",
        "Status": "In Progress", 
        "Priority": "High"
      }
    },
    {
      "id": 2,
      "title": "Write Documentation",
      "property_values": {
        "Name": "Write Documentation", 
        "Status": "Not Started",
        "Priority": "Medium"  
      }
    }
  ]
}
```

---

### GET `/api/databases/{database_id}/entries` - Get All Entries
Retrieve all database entries with their property values.

**Response:** Same as above (without schema properties)

---

## Comments API 💬

### POST `/api/comments/` - Add Comment to Block/Page
Create a new comment on any block or page.

**Request:**
```json
{
  "page_id": 5, 
  "text": "Great job on this section!",
  "user_id": 1
}
```

---

### GET `/api/comments/{comment_id}` - Get Comment Details
Retrieve specific comment with author info.

**Response:**
```json
{
  "id": 42,
  "text": "Great job on this section!", 
  "user_id": 1,
  "created_at": "2026-06-21T10:30:00Z"
}
```

---

## API Error Responses ⚠️

### 400 Bad Request
Invalid request format or missing required fields.

**Response:** `{"detail": "Missing required field: page_id"}`

---

### 401 Unauthorized  
Authentication token invalid or expired.

**Response:** `{"detail": "Not authenticated"}`

---

### 403 Forbidden
User doesn't have permission to access resource.

**Response:** `{"detail": "Access denied"}`

---

### 404 Not Found
Resource doesn't exist.

**Response:** `{"detail": "Page not found: page_id=999"}`

---

### 500 Internal Server Error
Server-side error occurred.

**Response:** `{"detail": "An unexpected error occurred"}`

---

## Rate Limiting 📊

API requests are rate-limited to prevent abuse:
- **Default limit**: 100 requests per minute per IP
- **Burst allowance**: Up to 200 requests in first second

Rate limit headers included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
Retry-After: 60 (when exceeded)
```

---

## Webhooks 🔄

Enable webhook support for real-time updates:

### POST `/api/webhooks/subscribe`
Subscribe to page/block changes.

**Request:**
```json
{
  "url": "https://yourapp.com/api/hooks/notion-clone", 
  "events": ["page.created", "block.updated"],
  "secret_token": "your_webhook_secret"
}
```

---

## WebSocket Connection 📡 (Future)

Real-time collaboration features will use WebSockets:

**Connect:** `ws://localhost:8000/ws?token=YOUR_TOKEN`  
**Events:** 
- `block.updated` - Block content changed in other editor sessions
- `user.joined` - New user opened this page
- `comment.added` - Someone added a comment

---

For full API specification with OpenAPI/Swagger, visit:
`http://localhost:8000/docs` (development) or configured production URL.
