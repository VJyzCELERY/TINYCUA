# NoteSpace - Notion-like App

A simple note-taking app inspired by Notion with Python backend and React frontend.

## Project Structure

```
experiment-4/
├── backend/              # Flask API server
│   ├── app.py           # Main application file
│   ├── models/database.py  (not used in final version)
│   └── requirements.txt
├── frontend/            # React SPA with Vite
│   ├── src/
│   │   ├── App.jsx     # Root component with routing
│   │   ├── main.jsx    # React entry point
│   │   ├── index.css   # Global styles
│   │   └── pages/      # Page components (Home, Editor, Search)
│   └── package.json
├── backend/notion.db   # SQLite database (created on first run)
```

## Running the Application

### Backend Server (Flask API - Port 5000)

The Flask backend is already running in background. If you need to restart:

```bash
cd /workspace/experiment-4/backend
python3 app.py &
# Or detach with: nohup python3 app.py > logs/server.log 2>&1 &
```

### Frontend Server (React SPA - Port 3000)

In a new terminal, install dependencies and start the frontend:

```bash
cd /workspace/experiment-4/frontend
npm install
npm run dev
```

This will open http://localhost:3000 in your browser.

## API Endpoints (Backend - http://localhost:5000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/pages` | Create new page (`{title, properties}`) |
| GET | `/api/pages/<id>` | Get page details |
| POST | `/api/search?q=` | Search pages by title |
| POST | `/api/pages/:id/blocks` | Add block to page `{type: 'text'/'heading_1'...}` |
| POST | `/api/pages/:id/comments` | Create comment |

## Features Implemented

- ✅ Block-based editor (paragraph, headings)
- ✅ Page creation and navigation
- ✅ SQLite database storage
- ✅ RESTful API with Flask
- ✅ Search functionality
- ✅ CORS enabled for frontend communication

## Next Steps (Optional Enhancements)

1. **Real-time collaboration** - Add WebSocket support using `flask-socketio`
2. **Rich text editor** - Integrate Draft.js or Slate.js for advanced editing
3. **Authentication** - Add JWT-based auth with user management
4. **File uploads** - Support images and attachments in pages
5. **Database optimization** - Indexing, migrations (using `alembic`)

## License

MIT License
