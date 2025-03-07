#!/bin/bash

# Activate virtual environment
export VIRTUAL_ENV="/home/danny/Github/shroombox/shroombox3/env_shrooms"
export PATH="$VIRTUAL_ENV/bin:$PATH"
unset PYTHON_HOME

# Set the working directory
cd /home/danny/Github/shroombox/shroombox3

# Run the Flask app
exec python3 web/app.py
