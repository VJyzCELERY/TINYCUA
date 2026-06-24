#!/bin/bash
# Start script for Notion-like Web Application
#
# Usage:
#   ./start.sh              # Development mode with hot-reload
#   ./start.sh production   # Production mode without debug
#   ./start.sh --db postgresql://user:pass@localhost/notion  # Custom database URL

set -e  # Exit on error

echo "=================================================="
echo "Notion-like Web Application Startup Script v1.0"
echo "=================================================="

# Check if virtual environment exists and activate it
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate 2>/dev/null || source ./bin/activate  # Handle both Unix and Windows paths

echo "Virtual environment activated."
echo ""

# Parse command line arguments
MODE="${1:-development}"
declare -A ENV_VARS=( [DATABASE_URL]=$(grep -i ^database_url=\.env.example | cut -d'=' -f2) )
db_url=${ENV_VARS[DATABASE_URL]:-sqlite:///./notion.db}
mode_lower=$(echo "$MODE" | tr '[:upper:]' '[:lower:]')

# Determine database URL from environment or default
case $mode_lower in
    development|dev)
        echo "Starting application..."
        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 || true
        ;;
    production|prod)
        # Production mode - no hot reload, better error messages
        export DEBUG=false
        echo "Starting application (production mode)..."
        uvicorn app.main:app --host 0.0.0.0 --port 8000 || true
        ;;
    *)
        # Default to development but allow custom database URL
        if [ "$MODE" != ".env.example" ]; then
            export DATABASE_URL="$db_url"
        fi
        echo "Starting application (development mode)..."
        uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 || true
        ;;
esac

echo ""
echo "API available at: http://localhost:8000"
echo "OpenAPI docs at: http://localhost:8000/docs"
echo "Health check at: http://localhost:8000/health"
