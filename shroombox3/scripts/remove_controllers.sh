#!/bin/bash

# Script to remove the controllers directory after backing it up

# Set the project root directory
PROJECT_ROOT=$(pwd)
echo "Project root: $PROJECT_ROOT"

# Check if backup exists
if [ ! -d "backup/controllers_backup" ]; then
    echo "Backup directory not found. Creating backup first..."
    mkdir -p backup/controllers_backup
    cp -r controllers/* backup/controllers_backup/
    echo "Backup created in backup/controllers_backup/"
fi

# Verify backup
echo "Verifying backup..."
if [ -f "backup/controllers_backup/environment_controller.py" ] && \
   [ -f "backup/controllers_backup/fan_controller.py" ] && \
   [ -f "backup/controllers_backup/humidity_controller.py" ] && \
   [ -f "backup/controllers_backup/temperature_controller.py" ]; then
    echo "Backup verification successful."
    
    # Remove controllers directory
    echo "Removing controllers directory..."
    rm -rf controllers
    
    echo "Controllers directory removed successfully."
    echo "If you need to restore the files, they are available in backup/controllers_backup/"
else
    echo "Backup verification failed. Aborting removal."
    echo "Please check the backup directory and try again."
fi 