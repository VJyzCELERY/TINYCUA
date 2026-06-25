# Notion-like Application

A simple Notion-inspired notes application built with Flask, SQLAlchemy (SQLite), and vanilla JavaScript.

## Project Structure

```
experiment-4/
├── backend/
│   ├── app.py          # Main Flask application
│   ├── models.py       # SQLAlchemy ORM models (Pages & Blocks)
│   ├── routes.py       # REST API endpoints
│   └── requirements.txt # Python dependencies
├── frontend/
│   ├── index.html      # Main HTML file
│   ├── styles.css      # CSS styling
│   └── app.js          # Frontend JavaScript logic
└── README.md           # This file
```

## Features

- **Pages System**: Create, read, update, and delete pages with titles
- **Block-based Content**: Support for paragraph, heading 1/2, and bullet list blocks
- **SQLite Database**: Persistent storage using SQLAlchemy ORM
- **Simple Authentication**: Bearer token-based auth (demo mode)
- **Modern UI**: Clean, intuitive interface similar to Notion

## Getting Started

### Prerequisites

- Python 3.8+
- pip/pipx for package management

### Installation

1. Navigate to the backend directory:
   ```bash
   cd /workspace/experiment-4/backend
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Start the Flask server:
   ```bash
   python app.py
   ```

The application will be available at `http://localhost:5000`

### Frontend Access

Open your browser and navigate to:
- **Frontend**: http://localhost/frontend/index.html
- **API Documentation**: View the API docs in the frontend UI or see below

## API Endpoints

All APIs are prefixed with `/api`:

### Authentication

| Method | Endpoint       | Description           |
|--------|---------------|----------------------|
| POST   | `/auth/login`  | Get authentication token |

Request body:
```json
{
    "username": "demo_user",
    "remember_me": true
}
```

Response includes a Bearer token for authenticated requests.

### Pages CRUD

| Method | Endpoint                    | Description           |
|--------|----------------------------|----------------------|
| POST   | `/pages`                   | Create new page      |
| GET    | `/pages` / `pages?page=N&per_page=M` | List all pages (paginated) |
| GET    | `/pages/<id>`              | Get single page with blocks |
| PUT    | `/pages/<id>`              | Update page          |
| DELETE | `/pages/<id>`              | Delete page and its blocks |

### Blocks CRUD

Blocks are child elements of pages (paragraphs, headings, lists).

| Method | Endpoint                        | Description           |
|--------|---------------------------------|----------------------|
| POST   | `/pages/<page_id>/blocks`       | Create new block     |
| GET    | `/pages/<page_id>/blocks`       | Get all blocks for a page |
| PUT    | `/pages/<page_id>/blocks/<id>`  | Update block         |
| DELETE | `/pages/<page_id>/blocks/<id>`  | Delete block         |

#### Block Types Supported:
- `paragraph`: Default text paragraph
- `heading_1`: Large heading (3rem)
- `heading_2`: Medium heading (2.5rem)
- `bulleted_list_item`: Bullet list item

### Examples

**Create a page:**
```bash
curl -X POST http://localhost:5000/api/pages \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "My First Page", "content": ""}'
```

**Get a page with its blocks:**
```bash
curl http://localhost:5000/api/pages/1
```

**Create a block for a page:**
```bash
curl -X POST http://localhost:5000/api/pages/1/blocks \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"type": "paragraph", "data": {}}'
```

## Database Schema

### Pages Table
| Column          | Type      | Description                    |
|-----------------|-----------|-------------------------------|
| id              | INTEGER   | Primary key                   |
| title           | VARCHAR(255) | Page title (required)        |
| content         | TEXT      | First paragraph content       |
| parent_page_id  | INTEGER   | Optional: for nested pages    |
| created_at      | DATETIME  | Creation timestamp            |
| updated_at      | DATETIME  | Last modification timestamp   |

### Blocks Table
| Column          | Type     | Description                    |
|-----------------|----------|-------------------------------|
| id              | INTEGER  | Primary key                   |
| page_id         | INTEGER  | Foreign key to pages table    |
| type            | VARCHAR(50) | Block type (paragraph, heading_1, etc.) |
| data            | TEXT     | JSON-like block properties    |
| created_at      | DATETIME | Creation timestamp            |

## Configuration

Create a `.env` file in the backend directory:

```bash
# Optional configuration
DATABASE_URL=sqlite:///notion.db  # Default SQLite path
FLASK_ENV=development             # Set to production for prod
DEBUG=true                       # Enable debug mode
```

## Usage Tips

1. **Creating Pages**: Click "+ New Page" in the sidebar or use the API
2. **Block Management**: 
   - Use block actions (+ Add) to add new blocks after existing ones
   - Select from dropdown to change block types (paragraph → heading, etc.)
3. **Keyboard Shortcuts** (when editing title):
   - `Enter`: Create a new paragraph block below the title
   - `Escape`: Create a new paragraph block below the title  
   - `Backspace` (empty title): Delete last block

## Current Limitations

- Single sign-on authentication (demo mode)
- No real-time collaboration features
- Basic duplicate detection at root level only
- SQLite storage (not suitable for production with concurrent writes)

## License

MIT License - Feel free to use and modify!
