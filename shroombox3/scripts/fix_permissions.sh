#!/bin/bash
# Script to fix permissions for the Shroombox project
# Run this script with sudo when you encounter permission issues

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Get the current user
USER=$(whoami)
if [ "$USER" = "root" ]; then
    # If run with sudo, get the actual user
    USER=$(logname)
fi

echo "Fixing permissions for user: $USER"
echo "Project directory: $PROJECT_DIR"

# Create necessary directories if they don't exist
echo "Creating necessary directories..."
mkdir -p "$PROJECT_DIR/config"
mkdir -p "$PROJECT_DIR/data"
mkdir -p "$PROJECT_DIR/logs"

# Create log files if they don't exist and set permissions
echo "Setting up log files..."
touch "$PROJECT_DIR/logs/main.log"
touch "$PROJECT_DIR/logs/web.log"

# Fix permissions for config files
echo "Fixing permissions for config files..."
chown -R $USER:$USER "$PROJECT_DIR/config"
chmod -R u+rw "$PROJECT_DIR/config"

# Fix permissions for data files
echo "Fixing permissions for data files..."
chown -R $USER:$USER "$PROJECT_DIR/data"
chmod -R u+rw "$PROJECT_DIR/data"

# Fix permissions for log files and directory with more permissive settings
echo "Fixing permissions for log files..."
chown -R $USER:$USER "$PROJECT_DIR/logs"
chmod 775 "$PROJECT_DIR/logs"  # Directory needs to be executable and group writable
find "$PROJECT_DIR/logs" -type f -exec chmod 664 {} \;  # Files need to be writable by user and group

# Fix permissions for Python cache files
echo "Fixing permissions for Python cache files..."
find "$PROJECT_DIR" -name "__pycache__" -type d -exec chown -R $USER:$USER {} \; 2>/dev/null
find "$PROJECT_DIR" -name "*.pyc" -type f -exec chown $USER:$USER {} \; 2>/dev/null

echo "Permissions fixed successfully!" 