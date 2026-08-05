#!/bin/sh
# Notion-like Web App - Start Script
# Usage: PORT=8765 sh start.sh
# This script installs dependencies and runs the app in foreground.

set -e

# Get port from environment variable or use default
PORT="${PORT:-8765}"

echo "Starting Notion-like app on PORT=${PORT}"

# Check if virtual environment exists, create if not
if [ ! -d "/workspace/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv /workspace/venv
    
    # Upgrade pip
    /workspace/venv/bin/pip install --upgrade pip
fi

# Install dependencies from requirements.txt
echo "Installing dependencies..."
/workspace/venv/bin/pip install -r /workspace/requirements.txt

# Run the application in foreground as child process
echo "Starting app on port ${PORT}..."
exec /workspace/venv/bin/python /workspace/app.py
