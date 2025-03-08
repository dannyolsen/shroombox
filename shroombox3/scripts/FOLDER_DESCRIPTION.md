# Scripts Directory

This directory contains utility scripts and tools meant to be run directly. These scripts provide various functionality for the Shroombox project, including calibration, testing, service installation, and utility functions.

## Naming Conventions

Scripts in this directory follow these naming conventions:
- `util_*.py`: Utility scripts for various tasks
- `calibrate_*.py`: Scripts for calibrating sensors
- `run_*.sh`: Shell scripts for running components of the system
- `start_*.sh`: Shell scripts for starting services
- `install_*.sh`: Shell scripts for installing services
- `*.service`: Service definition files for systemd

## Utility Scripts

- `util_update_measurements.py`: Updates the measurements.json file with current sensor readings
- `util_find_tapo_devices.py`: Discovers Tapo devices on the local network
- `util_simulate_sensor.py`: Simulates sensor readings for testing
- `util_tapo_ip_finder.py`: Finds IP addresses of Tapo devices
- `util_init_devices.py`: Initializes devices for the Shroombox system
- `util_update_test_imports.py`: Updates import statements in test files

## Calibration Scripts

- `calibrate_scd30_sensor.py`: Calibrates the SCD30 CO2 sensor
- `calibrate_scd30_force.py`: Forces calibration of the SCD30 CO2 sensor
- `calibrate_scd30.py`: Simplified calibration for the SCD30 CO2 sensor

## Shell Scripts

- `run_tests.sh`: Runs automated tests for the project
- `run_web.sh`: Runs the web interface
- `start_web.sh`: Starts the web service
- `install_services.sh`: Installs systemd services for the Shroombox

## Service Files

- `shroombox-measurements.service`: Service definition for the measurements updater

## Usage Examples

### Running Tests
```bash
./run_tests.sh
```

### Installing Services
```bash
./install_services.sh
```

### Calibrating the CO2 Sensor
```bash
python calibrate_scd30.py
```

### Finding Tapo Devices
```bash
python util_find_tapo_devices.py
```

### Updating Measurements
```bash
python util_update_measurements.py
``` 