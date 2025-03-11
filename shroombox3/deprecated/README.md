# Deprecated Code

This folder contains deprecated code that has been removed from the main codebase but is kept for reference or backward compatibility with older test scripts.

## Contents

- `sensor.py`: The original SCD30 sensor controller implementation that has been replaced by `SimpleSCD30Controller` in the main codebase.

## Usage

The code in this folder should not be used in new development. It is kept only for:

1. Reference purposes
2. Supporting legacy test scripts
3. Historical documentation

## Migration

If you have code that depends on these deprecated implementations, you should migrate to the current implementations:

- Replace `from devices.sensor import SCD30Controller` with `from devices.simple_sensor import SimpleSCD30Controller`

## Notes

The deprecated code may be completely removed in a future version of the project. Please update any dependencies accordingly. 