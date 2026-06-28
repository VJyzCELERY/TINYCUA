# Notion-like Web Application

A modern, block-based rich text editor web application built with Python FastAPI backend and SQLite database. This project provides a complete implementation similar to Notion's editing experience.

![Notion-like App](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

### Core Functionality
- **Block-based Rich Text Editing** - Create, edit, and format content blocks (text, headings, lists, code, images, quotes, callouts)
- **Slash Command Menu (/)** - Insert block types with keyboard shortcuts
- **Workspace Management** - Organize pages into workspaces with custom colors and icons
- **Page Properties** - Add titles, cover images, and page-level metadata
- **Real-time Save Support** - Auto-save drafts and version history (drafts system ready)
- **Authentication & Authorization** - JWT-based auth with password hashing
- **Soft Delete & Restore** - Undo accidental deletions without data loss
- **Dark/Light Theme Toggle** - Built-in theme switching with localStorage persistence
- **Responsive Design** - Works on desktop and tablet devices

### Technical Features
- **RESTful API** - Complete CRUD endpoints for pages, blocks, workspaces, search
- **SQLAlchemy ORM** - Type-safe database models with relationships
- **Pydantic Schemas** - Request/response validation with auto-generated JSON schemas
- **JWT Authentication** - Secure token-based auth with refresh tokens
- **CORS Support** - Cross-origin requests for frontend integration
- **SQLite/PostgreSQL Ready** - Easy migration between databases
- **File Upload Handling** - Image attachments and file storage support

## Directory Structure
```
experiment-4/
├── app/                      # FastAPI application package
│   ├── __init__.py          # Package initialization
│   ├── main.py              # FastAPI entry point with routers
│   ├── config.py            # Application configuration (settings)
│   ├── models.py            # SQLAlchemy ORM models
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── database.py          # Database connection/session management
│   └── auth.py              # JWT authentication handlers
├── api/                      # API endpoints package
│   ├── __init__.py
│   └── v1/
│       ├── __init__.py      # Version 1 API namespace
│       └── endpoints/
│           ├── pages.py     # Pages CRUD: create, read, update, delete
│           ├── blocks.py    # Blocks CRUD with position management
│           ├── workspaces.py# Workspace operations and member mgmt
│           └── search.py    # Global search across content
├── static/                   # Frontend assets
│   ├── css/
│   │   ├── styles.css       # Main stylesheet (variables, dark mode)
│   │   ├── editor.css       # Block highlighting and styling
│   │   └── sidebar.css      # Navigation UI styles
│   └── js/
│       ├── app.js           # Core application logic & API client
│       ├── editor.js        # Rich text editor implementation
│       ├── blocks.js        # Block manipulation functions
│       └── ui/              # Reusable UI components (modals, dropdowns)
├── templates/                # HTML Jinja2 templates
│   ├── base.html            # Base layout with sidebar/header/footer
│   ├── auth/
│   │   └── login.html       # Login/authentication page
│   └── pages/
│       └── page_template.html# Page editing interface template
├── uploads/                  # File upload storage
│   └── images/              # Image attachments directory
├── memory/                   # Long-term session memory (if enabled)
├── requirements.txt          # Python dependencies list
├── AGENTS.md                 # Agent workspace guidelines
└── TOOLS.md                  # Local setup notes and environment info
```

## Quick Start

### Prerequisites
- Python 3.10 or higher
- pip package manager
- Git (optional, for version control)

### Installation

#### Step 1: Clone the Repository
```bash
cd experiment-4
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

#### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

#### Step 3: Configure Environment (Optional)
Create a `.env` file with:
```env
SECRET_KEY=your-secure-random-key-here-minimum-32-chars-long
DATABASE_URL=sqlite:///./notion.db
cORS_ORIGIS=http://localhost:3000,http://127.0.0.1:3000
DEBUG=true
```

#### Step 4: Run the Application
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`
OpenAPI docs at `http://localhost:8000/docs`

### Using with a Frontend
1. Build your frontend (React, Vue, etc.) to output `/dist` or similar
2. Configure public URL in CORS settings:
   ```bash
   export CORS_ORIGIS=http://your-frontend-url:3000
   uvicorn app.main:app --reload
   ```

## API Endpoints Overview

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Login with email/password, returns JWT tokens |

### Pages (`/pages`)
| Method | Endpoint | Description |
|--------|----------|---------------|
| GET | `GET /pages` | List all pages (paginated) |
| GET | `GET /pages/{page_id}` | Get single page with blocks |
| POST | `POST /pages` | Create new page |
| PUT | `PUT /pages/{page_id}` | Update page properties |
| DELETE | `DELETE /pages/{page_id}?hard_delete=false` | Soft delete/restore page |

### Blocks (`/blocks`)
| Method | Endpoint | Description |
|--------|----------|---------------|
| GET | `GET /blocks/{page_id}` | Get all blocks in a page |
| POST | `POST /blocks/{page_id}` | Create new block at end of page |
| PUT | `PUT /blocks/{page_id}/{block_id}` | Update existing block content/props |
| DELETE | `DELETE /blocks/{page_id}/{block_id}?hard_delete=false` | Soft delete/restore block |

### Workspaces (`/workspaces`)
| Method | Endpoint | Description |
|--------|----------|---------------|
| GET | `GET /workspaces` | List all workspaces |
| POST | `POST /workspaces` | Create new workspace |
| PUT | `PUT /workspaces/{workspace_id}` | Update workspace properties |
| DELETE | `DELETE /workspaces/{workspace_id}?hard_delete=false` | Archive/delete workspace |

### Search (`/search`)
| Method | Endpoint | Description |
|--------|----------|---------------|
| GET | `GET /search?query={text}&limit={num}` | Global search across pages and blocks |

## Supported Block Types

The editor supports these block types (insert via `/` command):

| Type | Slash Command | Use Case |
|------|--------------|----------|
| Text | - | Standard paragraph text |
| Heading 1 | `/#` or use API `h1` | Main page headings |
| Heading 2 | `##/` or use API `h2` | Section headings |
| Heading 3 | `###/` or use API `h3` | Subsection headings |
| Bulleted List | `/bullet-list` | Unordered item lists |
| Numbered List | `/numbered-list` | Ordered numbered items |
| To-Do List | `/todo` | Checklist with completion state |
| Quote | `/quote` | Blockquotes for citations/emphasis |
| Code Block | `/code` | Code snippets with language highlighting |
| Image | `/image` | Page attachments (images, files) |
| Callout | `/callout` | Important notes/icons at page top |

## Configuration Options

### Environment Variables
```bash
# Required for production
SECRET_KEY=<random-32-char-key>
DATABASE_URL=sqlite:///./notion.db  # or postgresql://...
CORS_ORIGIS=http://localhost:3000,http://127.0.0.1:3000
DEBUG=true/false
```

### Database Configuration (`app/config.py`)
The `Settings` class in `config.py` provides:
- **DATABASE_URL**: Connection string for SQLite or PostgreSQL
- **SECRET_KEY**: JWT signing key (generate with `openssl rand -hex 32`)
- **ALGORITHM**: Token algorithm (default: HS256)
- **ACCESS_TOKEN_EXPIRE_MINUTES**: Access token lifetime (default: 30 min)
- **REFRESH_TOKEN_EXPIRE_DAYS**: Refresh token lifetime (default: 7 days)

## Database Schema

### Core Tables
1. **users** - User accounts with email, username, password hashes
2. **workspaces** - Workspace containers with owner and settings
3. **workspace_members** - Membership roles (owner/editor/viewer)
4. **pages** - Page content with title/icon/cover properties
5. **blocks** - Rich text blocks (text, headings, lists, etc.)
6. **attachments** - Uploaded files/images linked to pages
7. **comments** - Comments on pages/blocks/attachments
8. **reactions** - Emoji reactions (👍❤️🔥😂💯🎉⚡✨)
9. **page_versions** - Drafts and version history for undo/restore
10. **database_rows** - Database tables (Notion-style databases)
11. **database_properties** - Select/multi-select/tag options

## Security Considerations

- JWT tokens with short expiration times (30 min access, 7 day refresh)
- Password hashing using bcrypt through passlib
- CORS configuration to restrict cross-origin requests
- Soft delete for all deletions by default (easy restore)
- Input validation via Pydantic schemas on all API endpoints

## Testing the API

### Create a page:
```bash
curl -X POST http://localhost:8000/api/v1/pages \
  -H "Content-Type: application/json" \
  -d '{"title": "My First Page","icon_url":"🚀"}'
```

### Create a heading block:
```bash
curl -X POST http://localhost:8000/api/v1/pages/{page_id}/blocks \
  -H "Content-Type: application/json" \
  -d '{"block_type":"h1","text_content":"# Welcome!"}'
```

### List all pages:
```bash
curl http://localhost:8000/api/v1/pages
```

## Development Workflow

1. **Make changes** to Python code in `app/` or API endpoints in `api/v1/endpoints/`
2. **Run migrations** (if using SQLAlchemy migration tool like Alembic)
3. **Test with curl** or Postman against local API at port 8000
4. **Check OpenAPI docs** at `/docs` for interactive testing
5. **Build frontend separately** and serve alongside FastAPI backend
6. **Use `uvicorn app.main:app --reload`** for hot-reloading during development

## Future Enhancements (Not Yet Implemented)

- Real-time collaboration via WebSockets/Firebase
- Full-text search with PostgreSQL full-text operators
- Image upload processing and thumbnail generation
- Database view creation and management
- Template system for page layouts
- Export functionality (PDF, Markdown export)
- Mobile-responsive improvements and touch gestures
- Keyboard shortcuts documentation modal
- Undo/redo state management within editor session
- Collaborative cursors via Operational Transformations or CRDTs

## License
MIT License - Feel free to use this code for your own projects.

For questions, issues, or contributions, please refer to the AGENTS.md file in this workspace or contact the development team.
