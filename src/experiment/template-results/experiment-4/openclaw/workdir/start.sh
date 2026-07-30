#!/bin/bash
# Notion-like Workspace - Start Script

set -e

WORKDIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8765}"

echo "Starting Notion-like workspace on port $PORT..."

# Change to workdir and run the application
cd "$WORKDIR/app"

# Install dependencies using uv
uv sync --no-dev

# Run the Flask application
uv run python app.py
