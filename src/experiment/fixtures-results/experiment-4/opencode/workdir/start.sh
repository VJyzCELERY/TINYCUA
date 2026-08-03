#!/bin/bash
set -e

# Install dependencies using uv
uv sync 2>/dev/null || true

# Run the application with uv (uses virtual env)
exec uv run python app.py
