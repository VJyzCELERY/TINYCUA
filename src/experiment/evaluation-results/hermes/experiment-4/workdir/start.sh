#!/bin/bash

# Notion Clone Startup Script

echo "╔═══════════════════════════════════════════╗"
echo "║     Starting Notion Clone Application!    ║"
echo "╚═══════════════════════════════════════════╝"

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

echo ""
echo "Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

echo ""
echo "Initializing database..."
python app/init_db.py

echo ""
echo "Starting server at http://localhost:8000"
echo "Press Ctrl+C to stop the server"
echo ""

# Start uvicorn with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
