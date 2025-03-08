#!/bin/bash

# run_web.sh - Runs the Shroombox web interface directly (without service)
# Usage: ./run_web.sh

# Get the absolute path to the project directory
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Activate virtual environment
source "$PROJECT_DIR/venv/bin/activate"

# Set environment variables
export PYTHONPATH="$PROJECT_DIR"
export QUART_APP="web.web_server:app"
export QUART_ENV="development"  # Use development for direct running
export PYTHONUNBUFFERED=1

# Create log directory if it doesn't exist
mkdir -p "$PROJECT_DIR/logs"

echo "Starting Shroombox Web Interface..."
echo "Project directory: $PROJECT_DIR"
echo "Access the web interface at: http://localhost:5000"
echo "Press Ctrl+C to stop the server"
echo "----------------------------------------"

# Run the web server using hypercorn
exec hypercorn \
    --bind 0.0.0.0:5000 \
    --workers 1 \
    --log-level debug \
    web.web_server:app 