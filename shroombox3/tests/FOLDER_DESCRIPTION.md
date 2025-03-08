# Shroombox Tests

This directory contains automated tests for the Shroombox project.

## Directory Structure

- **`unit/`**: Unit tests for individual components
  - `test_scd30_measurements.py`: Tests for the SCD30 CO2 sensor measurements
  - `test_simple_controller.py`: Tests for the simplified SCD30 controller
  - `test_controller.py`: Tests for the SCD30 controller
  - `test_simple_scd30.py`: Tests for the simplified SCD30 sensor
  - `test_direct_scd30.py`: Tests for direct access to the SCD30 sensor
  - `test_scd30.py`: Tests for the SCD30 sensor
  - `test_i2c.py`: Tests for I2C communication
  - `test_sensor.py`: Tests for the sensor interface

- **`integration/`**: Integration tests for testing multiple components together

## Running Tests

You can run individual tests directly:

```bash
# Run a specific test
python tests/unit/test_scd30_measurements.py

# Run with specific options
python tests/unit/test_scd30_measurements.py --count 5 --json
```

Or use the test runner script:

```bash
# Run all tests
./scripts/run_tests.sh

# Run specific test categories
./scripts/run_tests.sh unit
./scripts/run_tests.sh integration
```

## Adding New Tests

When adding new tests:

1. Place unit tests in the `unit/` directory
2. Place integration tests in the `integration/` directory
3. Follow the naming convention `test_*.py`
4. Ensure tests can be run both individually and through the test runner 