# Scripts Data Directory

This directory is for **test data and temporary files only**. It should not be used for production data.

## Important Note

Do not store measurements.json or other production data files in this directory. All production data should be stored in the main `/data` directory at the project root.

## Appropriate Uses

- Test data files for script development
- Temporary output files for scripts
- Sample data for testing

## Inappropriate Uses

- Storing sensor measurements (use `/data/measurements.json` instead)
- Storing configuration files (use `/config` instead)
- Storing logs (use `/logs` instead)

When writing scripts that need to access or update measurements, always use the path to the main data directory:

```python
# Correct way to access measurements.json
import os
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEASUREMENTS_FILE = os.path.join(parent_dir, 'data', 'measurements.json')
``` 