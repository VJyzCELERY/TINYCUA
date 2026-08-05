# Notion-like Workspace

A simple, intuitive web app for creating pages with text blocks - inspired by Notion.

## Tech Stack

- **Backend**: Python + Flask
- **Database**: SQLite (persistent storage)
- **Frontend**: Vanilla JavaScript + CSS
- **Port**: 8765 (configurable via PORT env var)

## Files

```
/workspace/
├── start.sh              # Start script
├── README.md             # This file
└── app/                  # Application directory
    ├── app.py            # Flask backend API
    ├── database.py       # SQLite database module
    ├── templates/
    │   └── index.html    # Main HTML template
    └── static/
        ├── css/
        │   └── style.css     # Styling
        └── js/
            └── app.js        # Frontend logic
```

## Features

✅ Create, edit, and delete pages  
✅ Add unlimited text blocks to each page  
✅ Edit any block by clicking it  
✅ Delete blocks or entire pages  
✅ Persistent SQLite storage  
✅ Keyboard accessible (Tab navigation)  
✅ No authentication required  

## Usage

### Start the application:

```sh
cd /workspace
PORT=8765 sh start.sh
```

Or manually:

```sh
cd /workspace/app
PORT=8765 uv run python app.py
```

Then visit: http://127.0.0.1:8765/

### Browser Controls

- **Click `+` in sidebar** → Create new page  
- **Click any block** → Edit its content  
- **Hover over a block** → Shows delete button (×)  
- **Use Tab key** → Navigate between blocks  
- **Enter** → Focus the currently selected block  

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/pages` | List all pages |
| POST | `/api/pages` | Create new page |
| PUT | `/api/pages/<id>` | Update page title |
| DELETE | `/api/pages/<id>` | Delete a page |
| GET | `/api/pages/<id>/blocks` | Get blocks for a page |
| POST | `/api/pages/<id>/blocks` | Add new block |
| PUT | `/api/pages/<id>/blocks/<block_id>` | Update block content |
| DELETE | `/api/pages/<id>/blocks/<block_id>` | Delete a block |

## Persistence

All data is stored in SQLite database at `app/blocks.db`. Data persists across server restarts.

## Accessibility

- All controls are keyboard accessible (Tab navigation)  
- Screen reader friendly labels  
- Focus indicators on interactive elements  

## License

MIT - Feel free to use and modify!
