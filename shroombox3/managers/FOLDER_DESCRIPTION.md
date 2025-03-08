# Managers Directory

This directory contains manager classes that coordinate between devices and services in the Shroombox project. These managers handle higher-level functionality by orchestrating multiple devices and providing interfaces for the application logic.

## Files

- `__init__.py`: Exports the manager classes and provides package initialization
- `device_manager.py`: Manages all devices in the system
- `env_manager.py`: Manages environmental conditions (temperature, humidity, CO2)
- `influxdb_manager.py`: Manages data storage and retrieval with InfluxDB
- `settings_manager.py`: Manages application settings and configuration

## Manager Classes

### Device Manager
The `device_manager.py` file defines the `DeviceManager` class that:
- Initializes and manages all hardware devices
- Provides a unified interface for device control
- Handles device errors and recovery
- Maintains device status information

### Environment Manager
The `env_manager.py` file defines the `EnvironmentManager` class that:
- Monitors environmental conditions (temperature, humidity, CO2)
- Controls devices to maintain optimal growing conditions
- Implements environmental control algorithms
- Provides alerts for out-of-range conditions

### InfluxDB Manager
The `influxdb_manager.py` file defines the `InfluxDBManager` class that:
- Connects to the InfluxDB time-series database
- Stores sensor readings and device states
- Retrieves historical data for analysis
- Provides data aggregation and querying capabilities

### Settings Manager
The `settings_manager.py` file defines the `SettingsManager` class that:
- Loads and saves application settings
- Provides interfaces for modifying settings
- Validates setting values
- Handles setting persistence

## Usage Examples

```python
# Example: Using the DeviceManager
from managers import DeviceManager

device_manager = DeviceManager()
device_manager.initialize_devices()
sensor = device_manager.get_device('co2_sensor')
fan = device_manager.get_device('exhaust_fan')

# Example: Using the EnvironmentManager
from managers import EnvironmentManager

env_manager = EnvironmentManager()
env_manager.start_monitoring()
current_conditions = env_manager.get_current_conditions()
print(f"CO2: {current_conditions['co2']}ppm")

# Example: Using the InfluxDBManager
from managers import InfluxDBManager

db_manager = InfluxDBManager()
db_manager.connect()
db_manager.write_measurement('co2', 800)
data = db_manager.query_measurements('co2', start='-1h')
```

## Adding New Managers

When adding new manager classes:
1. Create a new file for the manager type
2. Implement the required functionality
3. Add the new class to `__init__.py` for easy importing
4. Ensure the manager integrates with existing managers as needed 