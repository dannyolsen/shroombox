# Data Directory

This directory contains data files used by the Shroombox project. These files store sensor readings, configuration data, and other information needed by the application.

## Files

- `measurements.json`: Contains the latest sensor measurements (CO2, temperature, humidity)
- `sensor_test.json`: Contains test data for sensors in JSON format
- `sensor_test.csv`: Contains test data for sensors in CSV format

## File Formats

### measurements.json
This file is updated regularly by the `util_update_measurements.py` script and contains the latest sensor readings:

```json
{
  "timestamp": "2023-03-08T08:09:00",
  "co2": 800,
  "temperature": 22.5,
  "humidity": 55.2
}
```

### sensor_test.json
This file contains test data for sensors in JSON format, used for testing and development:

```json
{
  "readings": [
    {"timestamp": "2023-03-08T08:00:00", "co2": 800, "temperature": 22.5, "humidity": 55.2},
    {"timestamp": "2023-03-08T08:05:00", "co2": 810, "temperature": 22.6, "humidity": 55.3}
  ]
}
```

### sensor_test.csv
This file contains test data for sensors in CSV format, used for testing and data analysis:

```csv
timestamp,co2,temperature,humidity
2023-03-08T08:00:00,800,22.5,55.2
2023-03-08T08:05:00,810,22.6,55.3
```

## Usage

The data files in this directory are used by various components of the Shroombox system:

- The `measurements.json` file is read by the web interface to display current conditions
- The test files are used by automated tests to verify functionality
- Data files may be backed up periodically to preserve historical data

## Adding New Data Files

When adding new data files:
1. Use appropriate file formats (JSON, CSV, etc.) based on the data structure
2. Document the file format and purpose in this file
3. Ensure proper error handling when reading/writing to data files
4. Consider data validation to maintain integrity 