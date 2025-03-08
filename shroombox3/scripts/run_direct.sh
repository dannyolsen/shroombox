#!/bin/bash

# Get the absolute path to the project directory
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Activate virtual environment
source "$PROJECT_DIR/venv/bin/activate"

# Set environment variables
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
export PYTHONUNBUFFERED=1

echo "Running main.py directly..."
echo "Project directory: $PROJECT_DIR"
echo "Python executable: $(which python)"
echo "----------------------------------------"

# Run main.py directly
cd "$PROJECT_DIR"
python main.py 