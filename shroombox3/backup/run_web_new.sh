#!/bin/bash

# This script runs the web server with the new structure

# Activate virtual environment if it exists
if [ -d "env_shrooms" ]; then
    echo "Activating virtual environment..."
    source env_shrooms/bin/activate
fi

# Set the working directory to the project root
cd "$(dirname "$0")"

# Run the web server
echo "Starting web server..."
python web/web_server.py 