#!/bin/bash

# run_measurements.sh - Runs the Shroombox measurements updater directly (without service)
# Usage: ./run_measurements.sh

# Get the absolute path to the project directory
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Activate virtual environment
source "$PROJECT_DIR/venv/bin/activate"

# Set environment variables
export PYTHONPATH="$PROJECT_DIR"
export PYTHONUNBUFFERED=1

# Create necessary directories
mkdir -p "$PROJECT_DIR/data"
mkdir -p "$PROJECT_DIR/logs"

echo "Starting Shroombox Measurements Updater..."
echo "Project directory: $PROJECT_DIR"
echo "Measurements will be written to: $PROJECT_DIR/data/measurements.json"
echo "Press Ctrl+C to stop"
echo "----------------------------------------"

# Run the measurements updater
exec python "$PROJECT_DIR/scripts/util_update_measurements.py" 