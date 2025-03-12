# Shroombox Project Folder Structure

This document outlines the organization of the Shroombox project codebase to help maintain consistency and make it easier to find files.

## Top-Level Directories

- **`devices/`**: Device controller classes for hardware components
- **`managers/`**: Manager classes that coordinate between devices and services
- **`utils/`**: Utility functions and helper classes
- **`web/`**: Web interface and API
- **`config/`**: Configuration files
- **`data/`**: Data storage
- **`logs/`**: Log files
- **`scripts/`**: Utility scripts and tools
- **`tests/`**: Automated tests

## Scripts Directory

The `scripts/` directory contains utility scripts and tools that are meant to be run directly. These scripts are organized with the following naming conventions:

### Naming Conventions

- **`util_*.py`**: Utility scripts for system administration and maintenance
- **`test_*.py`**: Test scripts for testing specific components
- **`calibrate_*.py`**: Calibration scripts for sensors and devices
- **`run_*.sh`**: Shell scripts for running services or components
- **`install_*.sh`**: Installation scripts

### Categories of Scripts

1. **Utility Scripts**: Tools for system administration and maintenance
   - `util_find_tapo_devices.py`: Find and identify Tapo smart devices on the network
   - `util_update_measurements.py`: Update sensor measurements file

2. **Test Scripts**: Scripts for testing specific components
   - `test_scd30.py`: Test the SCD30 CO2 sensor
   - `test_i2c.py`: Test I2C communication
   - `test_controller.py`: Test the SCD30 controller
   - `test_simple_controller.py`: Test the simplified SCD30 controller

3. **Calibration Scripts**: Scripts for calibrating sensors
   - `calibrate_scd30_sensor.py`: Calibrate the SCD30 CO2 sensor

4. **Service Scripts**: Scripts for managing services
   - `run_web.sh`: Run the web interface
   - `install_services.sh`: Install system services

## Tests Directory

The `tests/` directory contains automated tests for verifying code functionality. These tests are organized into:

- **`unit/`**: Unit tests for individual components
- **`integration/`**: Integration tests for testing multiple components together

Tests should follow the naming convention `test_*.py` and should be designed to be run with a testing framework.

## Maintaining the Structure

When adding new files:

1. **Scripts vs Tests**: 
   - If it's meant to be run directly as a utility, put it in `scripts/`
   - If it's meant to verify code functionality in an automated way, put it in `tests/`

2. **Follow naming conventions** to make the purpose of files clear

3. **Update this document** if you add new categories or change the structure 