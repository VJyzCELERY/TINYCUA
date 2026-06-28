#!/bin/bash

# Startup script for Notion-like App

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/backend"

echo "=========================================="
echo "Notion-like Application"
echo "=========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH."
    exit 1
fi

cd "$BACKEND_DIR"

# Create .env file from example if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating default .env file..."
    cp .env.example .env
fi

echo "Installing dependencies (pip install -r requirements.txt)..."
pip install -r requirements.txt 2>&1 | tail -5

# Remove any existing database for fresh start
if [ ! -f "notion.db" ]; then
    echo ""
    echo "Creating new SQLite database..."
fi

echo ""
echo "Starting Flask server on http://0.0.0.0:5000"
echo "=========================================="
echo ""
python app.py
