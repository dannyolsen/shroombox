#!/bin/bash

# Script to fix permissions on the settings.json file
# This ensures that the file is always editable by everyone

# Path to the settings file
SETTINGS_FILE="config/settings.json"

# Check if the file exists
if [ -f "$SETTINGS_FILE" ]; then
    echo "Fixing permissions on $SETTINGS_FILE"
    
    # Set permissions to allow everyone to read/write
    chmod 666 $SETTINGS_FILE
    
    echo "Permissions fixed. Current permissions:"
    ls -la $SETTINGS_FILE
else
    echo "Error: $SETTINGS_FILE not found"
    exit 1
fi

echo "Done!"
exit 0 