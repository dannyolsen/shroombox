#!/bin/bash

# run_main.sh - Runs the Shroombox main control script directly (without service)
# Usage: ./run_main.sh

# Get the absolute path to the project directory
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Activate virtual environment
source "$PROJECT_DIR/venv/bin/activate"

# Set environment variables
export PYTHONPATH="$PROJECT_DIR"
export PYTHONUNBUFFERED=1

echo "Starting Shroombox Main Controller..."
echo "Project directory: $PROJECT_DIR"
echo "Press Ctrl+C to stop"
echo "----------------------------------------"

# Run the main script
exec python "$PROJECT_DIR/main.py" 