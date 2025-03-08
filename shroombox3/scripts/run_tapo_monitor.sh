#!/bin/bash

# run_tapo_monitor.sh - Runs the Shroombox Tapo device monitor directly (without service)
# Usage: ./run_tapo_monitor.sh [--verbose]

# Get the absolute path to the project directory
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Activate virtual environment
source "$PROJECT_DIR/venv/bin/activate"

# Set environment variables
export PYTHONPATH="$PROJECT_DIR"
export PYTHONUNBUFFERED=1

# Create necessary directories
mkdir -p "$PROJECT_DIR/config"
mkdir -p "$PROJECT_DIR/logs"

echo "Starting Shroombox Tapo Device Monitor..."
echo "Project directory: $PROJECT_DIR"
echo "Settings file: $PROJECT_DIR/config/settings.json"
echo "Press Ctrl+C to stop"
echo "----------------------------------------"

# Run the Tapo monitor
# Pass any command line arguments to the script (like --verbose)
exec python "$PROJECT_DIR/scripts/util_monitor_tapo_devices.py" "$@" 