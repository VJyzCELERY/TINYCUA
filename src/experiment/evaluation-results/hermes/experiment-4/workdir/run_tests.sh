#!/bin/bash


echo "Running tests..."
python3 -c "from app.models import User, Page; print('✓ Models OK')"
