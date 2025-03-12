#!/bin/bash

# Script to make the settings.json file editable by everyone

# Path to the settings file
SETTINGS_FILE="config/settings.json"

# Check if the file exists
if [ -f "$SETTINGS_FILE" ]; then
    echo "Making $SETTINGS_FILE editable by everyone..."
    
    # Set permissions to allow everyone to read/write
    sudo chmod 666 $SETTINGS_FILE
    
    echo "Permissions set. Current permissions:"
    ls -la $SETTINGS_FILE
else
    echo "Error: $SETTINGS_FILE not found"
    exit 1
fi

echo "Done! You can now edit the file in your code editor."
echo "The file will remain editable until the service writes to it again."
echo "Run this script again if you need to edit the file later."
exit 0 