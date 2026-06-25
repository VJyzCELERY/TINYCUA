# Notion-Like App - Deployment & Documentation

## Overview

A full-stack Notion-like document editor with:
- **Backend**: FastAPI (Python 3.12) with SQLite database, JWT authentication
- **Frontend**: React + Vite + TypeScript with TipTap rich text editor
- **Storage**: SQLite (app.db in workspace root)

## Architecture

```
/workspace/experiment-4/
├── src/                 # FastAPI backend
│   ├── auth/           # JWT authentication, password hashing
│   ├── router/         # API route handlers
│   ├── schemas/        # Pydantic models (request/response)
│   ├── models/         # SQLAlchemy/sqlmodel database models
│   ├── config/         # Database init, settings
│   └── main.py         # FastAPI app entry point
├── frontend/           # React + Vite frontend
│   ├── src/
│   │   ├── components/ # DocumentView.tsx, TipTapEditor.tsx, BlockToolbar.tsx
│   │   ├── hooks/      # useUndoRedo.ts
│   │   └── assets/     # CSS files
│   └── package.json    # Dependencies
├── alembic/            # Database migrations
├── .env.template       # Environment template
├── app.db              # SQLite database (auto-created)
└── DEPLOYMENT.md       # This file
```

---

## Local Development Setup

### Prerequisites
- Python 3.12+
- Node.js 20 LTS + npm
- Git (recommended)

### Step 1: Clone & Navigate
```bash
cd /workspace/experiment-4
```

### Step 2: Backend Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Copy environment template and configure
cp .env.template .env
# Edit .env with your settings (DATABASE_URL, CORS_ORIGINS, JWT_SECRET_KEY)
```

### Step 3: Frontend Setup
```bash
cd frontend
npm install
```

### Step 4: Run Development Servers

**Terminal 1 - Backend:**
```bash
cd /workspace/experiment-4
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```
Backend runs at `http://localhost:8000`

API Endpoints:
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/version` | API version info |
| POST | `/api/v1/auth/login` | User login (requires username/password) |
| GET | `/api/v1/auth/me` | Current user info (auth required) |
| POST | `/api/v1/auth/logout` | Logout |
| GET | `/api/v1/blocks/{block_id}` | Get block by ID |
| PUT | `/api/v1/blocks/{block_id}/update` | Update block content/type |
| DELETE | `/api/v1/blocks/{block_id}` | Delete block |
| POST | `/api/v1/blocks` | Create new block |
| GET | `/api/v1/search?q={query}` | Search blocks with pagination |

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev -- --port 3000
```
Frontend runs at `http://localhost:3000`

### Step 5: Test Full Flow

1. **Create a user account**: Visit http://localhost:3000 and login with any credentials (backend stores in memory via JWT)

2. **Create blocks**: Use the toolbar to insert text/code/heading blocks

3. **Edit content**: Click on any block to edit its content using TipTap editor

4. **Undo/Redo**: Use Ctrl+Z/Ctrl+Y or the action toolbar buttons

5. **Verify API calls**: Open browser DevTools → Network tab to see requests to `http://localhost:8000`

### Health Check
```bash
curl http://localhost:8000/health
# Returns: {"status":"healthy","service":"notion-like-app"}

curl http://localhost:8000/api/v1/version
# Returns: {"version":"0.1.0","service":"notion-like-app","api_version":"v1"}
```

---

## Production Deployment Instructions

### Option 1: Docker Compose (Recommended)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:///app.db
      - CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
      - JWT_SECRET_KEY=your-production-secret-key-here
    volumes:
      - ./src:/app/src
      - app_db:/app/data
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - VITE_API_BASE=http://localhost:8000/api/v1
    depends_on:
      - backend

volumes:
  app_db:
```

Build and run:
```bash
docker-compose up --build -d
```

### Option 2: Static Site + Backend Server

**Step 1: Build Frontend for Production**
```bash
cd frontend
npm run build
# Output in frontend/dist/
```

**Step 2: Serve Frontend with Nginx/Apache (or any static server)**
- Configure to serve `frontend/dist/index.html` at `/`
- Proxy API requests (`/api/*`) to backend at port 8000

**Step 3: Backend Production Run**
```bash
cd /workspace/experiment-4
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
# Or use gunicorn for better production performance
pip install gunicorn
gunicorn -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    src.main:app
```

### Step 4: Environment Variables for Production

Create `.env`:
```bash
DATABASE_URL=sqlite:////workspace/experiment-4/app.db
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
JWT_SECRET_KEY=change-this-to-a-long-random-secret-key
# Optional: Add admin user credentials or OAuth providers if needed
```

### Step 5: Database Migration (if schema changes)
```bash
cd /workspace/experiment-4
alembic upgrade head
```

---

## API Documentation Summary

### Authentication Flow
1. **Register/Login**: `POST /api/v1/auth/login` with `{username, password}`
2. **Get Token**: Response includes JWT `access_token` and `username`
3. **Authenticated Requests**: Include header `Authorization: Bearer <token>`
4. **Check Status**: `GET /api/v1/auth/me` returns current user info

### Block Operations (all require auth)
| Operation | Endpoint | Method | Description |
|-----------|----------|--------|-------------|
| Create block | `/api/v1/blocks` | POST | Creates new block with type (text/code/heading/image/bullet-list) |
| Get block | `/api/v1/blocks/{block_id}` | GET | Retrieves full block data including content |
| Update block | `/api/v1/blocks/{block_id}/update` | PUT | Modifies content/type/title of existing block |
| Delete block | `/api/v1/blocks/{block_id}` | DELETE | Removes block from database |

### Search
- **Endpoint**: `GET /api/v1/search?q={query}&page=1&page_size=10`
- Returns paginated results across all blocks/pages/document properties

---

## Testing Checklist

Before production deployment:

- [ ] Health endpoint responds: `curl http://localhost:8000/health`
- [ ] Version endpoint works: `curl http://localhost:8000/api/v1/version`
- [ ] Login creates valid JWT token
- [ ] Authenticated GET /api/v1/auth/me returns user info
- [ ] POST /api/v1/blocks creates block with correct schema
- [ ] GET /api/v1/blocks/{id} retrieves block data
- [ ] PUT /api/v1/blocks/{id}/update modifies content
- [ ] DELETE /api/v1/blocks/{id} removes block
- [ ] Search endpoint returns paginated results
- [ ] Frontend builds without errors: `cd frontend && npm run build`
- [ ] Frontend serves at http://localhost:3000
- [ ] TipTap editor loads and is editable
- [ ] Undo/Redo functionality works (Ctrl+Z/Y)

---

## Troubleshooting

### Database not found
```bash
# Ensure database path is absolute in .env
DATABASE_URL=sqlite:////workspace/experiment-4/app.db
```

### CORS errors from browser
- Check CORS_ORIGINS in .env includes your frontend origin (e.g., `http://localhost:3000`)
- Backend middleware handles preflight OPTIONS requests automatically

### Frontend can't reach backend
- Ensure both servers are running
- CORS_ORIGINS must include the exact frontend URL including port
- For production, use full domain without protocol in CORS_ORIGINS (handled by server)

---

## Next Steps for Enhancement

1. **Add user registration**: Implement password reset and email verification
2. **OAuth integration**: Add Google/GitHub login support
3. **Real-time sync**: Implement WebSockets or SSE for collaborative editing
4. **File uploads**: Add image/file storage (local disk, S3, or CDN)
5. **Rich text formatting**: Extend TipTap with bold/italic/code block extensions
6. **Database backup**: Implement periodic SQLite dumps to external storage

---

## License & Credits

Built with:
- FastAPI backend framework
- SQLAlchemy/sqlmodel ORM
- React + Vite frontend build tooling
- TipTap rich text editor
- JWT authentication (python-jose)
- bcrypt password hashing
