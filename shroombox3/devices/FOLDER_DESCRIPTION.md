# Devices Directory

This directory contains device controller classes for hardware components used in the Shroombox project. These classes provide interfaces to interact with physical hardware devices such as sensors, fans, and smart plugs.

## Files

- `__init__.py`: Exports the device classes and provides package initialization
- `base.py`: Contains the base device class that all other device classes inherit from
- `sensor.py`: Contains the sensor interface and implementation for CO2, temperature, and humidity sensors
- `simple_sensor.py`: Contains a simplified sensor implementation with reduced complexity
- `smart_plug.py`: Contains the smart plug interface and implementation for controlling power to devices
- `fan.py`: Contains the fan interface and implementation for controlling airflow

## Device Classes

### Base Device
The `base.py` file defines the `Device` base class that provides common functionality for all devices, including:
- Device initialization
- Status reporting
- Error handling

### Sensors
The `sensor.py` and `simple_sensor.py` files define classes for interacting with sensors:
- `SCD30Sensor`: Interface for the SCD30 CO2, temperature, and humidity sensor
- `SimpleSCD30Controller`: Simplified controller for the SCD30 sensor with reduced complexity

### Smart Plugs
The `smart_plug.py` file defines classes for interacting with smart plugs:
- `TapoSmartPlug`: Interface for Tapo smart plugs
- Methods for turning devices on/off, getting energy usage, etc.

### Fans
The `fan.py` file defines classes for interacting with fans:
- `Fan`: Interface for controlling fans
- Methods for setting fan speed, checking status, etc.

## Usage Examples

```python
# Example: Using the SCD30 sensor
from devices import SCD30Sensor

sensor = SCD30Sensor()
co2, temp, humidity = sensor.get_measurement()
print(f"CO2: {co2}ppm, Temperature: {temp}°C, Humidity: {humidity}%")

# Example: Using a smart plug
from devices import TapoSmartPlug

plug = TapoSmartPlug(ip="192.168.1.100", email="user@example.com", password="password")
plug.turn_on()
energy_usage = plug.get_energy_usage()
print(f"Current power usage: {energy_usage['current_power']}W")
```

## Adding New Devices

When adding new device classes:
1. Create a new file for the device type
2. Inherit from the base `Device` class
3. Implement the required methods
4. Add the new class to `__init__.py` for easy importing 