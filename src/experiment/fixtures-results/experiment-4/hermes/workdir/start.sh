#!/bin/bash
# Notion-like Workspace Application Startup Script
# Usage: PORT=8765 sh start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create data directory if it doesn't exist
mkdir -p /workspace/data

# Install dependencies using uv (if available) or pip
if command -v uv &> /dev/null; then
    echo "Installing dependencies with uv..."
    uv venv --python 3.12 2>/dev/null || true
    source .venv/bin/activate 2>/dev/null || deactivate 2>/dev/null || true
    uv pip install -r requirements.txt 2>/dev/null || pip install -r requirements.txt
else
    echo "Installing dependencies with pip..."
    pip install -r requirements.txt
fi

echo ""
echo "=========================================="
echo "Notion-like Workspace Application"
echo "=========================================="
echo "Available at: http://localhost:${PORT:-8765}"
echo ""
echo "Features:"
echo "  - Create, edit, and delete text blocks"
echo "  - Persistent storage across reloads"
echo "  - Keyboard shortcuts (Ctrl+Backspace to delete)"
echo ""

# Run the application in foreground
exec python3 app.py
