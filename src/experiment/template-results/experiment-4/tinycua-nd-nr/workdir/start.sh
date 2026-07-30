#!/bin/sh

# Install uv-managed dependencies
uv pip install -r requirements.txt

# Export PORT for Flask application
export PORT="${PORT:-8765}"

# Initialize database if it doesn't exist (creates data/blocks.db)
cd "$(dirname "$0")"
python -c "from database.database import init_db; init_db()"

# Launch the Flask application in foreground
export FLASK_APP=app.py
export FLASK_ENV=development
flask run --host=0.0.0.0 --port="$PORT"
