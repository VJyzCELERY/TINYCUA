#!/bin/sh
# start.sh - Entry point for Notion-like web app
# Handles dependency installation, runs in foreground, preserves data across invocations

set -e

# Get port from environment or default to 8765
PORT="${PORT:-8765}"

# Ensure parent directory exists
mkdir -p "$(dirname "$0")"

echo "=========================================="
echo "Notion-like Web App - Starting..."
echo "=========================================="
echo "Port: $PORT"
echo "Database: /workspace/notion.db"
echo "=========================================="

# Install dependencies using uv (harness includes uv)
# This handles fresh installs and updates
echo ""
echo "Installing/updating dependencies..."
uv pip install --system fastapi uvicorn pydantic 2>&1 || echo "Dependency installation may have issues, continuing..."

# Initialize database if it doesn't exist
python3 -c "
import sys
sys.path.insert(0, '/workspace')
from app import init_db
init_db()
print('Database initialized successfully.')
"

echo ""
echo "=========================================="
echo "Notion-like Web App is running!"
echo "=========================================="
echo "API available at: http://localhost:$PORT/"
echo "API docs: http://localhost:$PORT/docs"
echo "=========================================="
echo ""

# Run the FastAPI app in foreground (no daemonization)
exec python3 /workspace/app.py
