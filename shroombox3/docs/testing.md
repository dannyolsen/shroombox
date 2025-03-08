# Shroombox Testing Documentation

This document provides an overview of all test scripts available in the Shroombox project and how to use them.

## Temperature Control Tests

### `scripts/test_temperature_control.py`
Tests the temperature control logic with different scenarios:
- Normal operation with gradual temperature changes
- Rapid temperature changes (tests debouncing)
- Edge cases (invalid temperatures)
- Threshold testing around setpoint

Usage:
```bash
./scripts/test_temperature_control.py
```

Features:
- Mock device manager for safe testing
- Configurable test scenarios
- Detailed logging of state changes
- Validates hysteresis and debouncing

## Heater Control Tests

### `backup/test_direct_heater.py`
Tests direct control of the Tapo P115 smart plug used as a heater:
- Direct API communication
- Basic ON/OFF functionality
- State synchronization with settings.json

### `backup/test_heater_tapo.py`
Tests the heater control using the Tapo controller wrapper:
- Tests the abstraction layer
- Verifies state management
- Settings synchronization

### `backup/test_heater_simple.py`
Simple heater control test with basic functionality:
- Basic ON/OFF operations
- Error handling
- Settings verification

## Device Tests

### `backup/test_device_toggle.py`
Tests toggling of smart devices (heater/humidifier):
```bash
python test_device_toggle.py [heater|humidifier]
```
- Tests individual device control
- Verifies state changes
- Handles error conditions

### `backup/test_new_structure.py`
Verifies the new code structure:
- Tests fan controller
- Tests sensor functionality
- Tests device manager integration
- Validates component initialization

## Web Integration Tests

### `backup/test_web_integration.py`
Tests the web interface integration:
- API endpoint testing
- Device control through web interface
- Settings management via web API

## Utility Tests

### `backup/test_setpoints.py`
Tests setpoint management:
- Temperature setpoint validation
- Humidity setpoint validation
- Phase-based setpoint changes

### `backup/settings_manager.py`
Tests the settings manager functionality:
- Settings file operations
- State persistence
- Configuration validation

## Running Tests

1. Activate the virtual environment:
```bash
source venv/bin/activate
```

2. Run individual tests:
```bash
# Temperature control test
./scripts/test_temperature_control.py

# Device toggle test
python backup/test_device_toggle.py heater

# Web integration test
python backup/test_web_integration.py
```

## Test Development Guidelines

1. **Mock Devices**: Use mock device managers for testing when possible to avoid affecting real hardware
2. **Logging**: Include detailed logging for debugging
3. **Error Handling**: Test both success and failure scenarios
4. **State Validation**: Verify device states after operations
5. **Settings Sync**: Ensure settings.json stays in sync with device states

## Common Test Scenarios

### Temperature Control
- Test around setpoint thresholds
- Verify hysteresis behavior
- Check debouncing functionality
- Validate error handling

### Device Control
- Test device initialization
- Verify state changes
- Check error recovery
- Validate settings persistence

### Web Interface
- Test API endpoints
- Verify device control
- Check settings management
- Validate error responses

## Adding New Tests

When adding new tests:
1. Follow existing naming conventions (`test_*.py`)
2. Include detailed docstrings
3. Add logging for debugging
4. Use mock devices when possible
5. Add the test to this documentation

## Test Environment Setup

Required environment variables:
- `TAPO_EMAIL`: Email for Tapo device access
- `TAPO_PASSWORD`: Password for Tapo device access

Configuration files:
- `config/settings.json`: Main configuration file
- `config/test_settings.json`: Test-specific settings 