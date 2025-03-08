# Shroombox Control System

A Raspberry Pi-based environmental control system for mushroom cultivation.

## Project Structure

The project has been reorganized into a more modular structure:

```
shroombox/
├── config/             # Configuration files
├── devices/            # Hardware device interfaces
│   ├── __init__.py
│   ├── base.py         # Base device interface
│   ├── fan.py          # Noctua PWM fan controller
│   ├── sensor.py       # SCD30 CO2 sensor controller
│   └── smart_plug.py   # Tapo smart plug controller
├── logs/               # Log files
├── managers/           # High-level managers
│   ├── __init__.py
│   ├── device_manager.py   # Manages all hardware devices
│   └── settings_manager.py # Handles configuration
├── scripts/            # Utility scripts
│   ├── run_tests.sh    # Script to run all tests
│   └── run_web.sh      # Script to run the web server
├── tests/              # Test files
│   ├── integration/    # Integration tests
│   └── unit/           # Unit tests
├── utils/              # Utility functions
│   ├── __init__.py
│   ├── logging_setup.py    # Logging configuration
│   └── singleton.py        # Singleton pattern implementation
├── web/                # Web interface
│   ├── static/         # Static files (CSS, JS, etc.)
│   ├── templates/      # HTML templates
│   └── web_server.py   # Web server implementation
├── main.py             # Main application entry point
└── README.md           # This file
```

## Key Components

### Devices

All hardware devices implement the `Device` interface defined in `devices/base.py`:

- **NoctuaFan**: Controls the PWM fan for air circulation and CO2 control
- **SCD30Controller**: Manages the SCD30 CO2, temperature, and humidity sensor
- **TapoController**: Controls Tapo smart plugs for heaters and humidifiers

### Managers

- **DeviceManager**: Provides a unified interface for accessing all hardware devices
- **SettingsManager**: Handles loading, saving, and updating configuration

### Utils

- **singleton**: Decorator for implementing the singleton pattern
- **logging_setup**: Configures logging for the application

### Web Interface

The web interface provides a user-friendly way to monitor and control the system:

- **web_server.py**: Implements the web server and API endpoints
- **templates/**: Contains HTML templates for the web interface
- **static/**: Contains static files (CSS, JS, images)

## Usage

### Running the Main Application

```bash
python main.py
```

### Running the Web Interface

```bash
./scripts/run_web.sh
```

### Running Tests

```bash
./scripts/run_tests.sh
```

## Development

When adding new devices:

1. Create a new class in the `devices` directory that implements the `Device` interface
2. Add the device to the `DeviceManager` class
3. Update the `__init__.py` files to expose the new device

## License

This project is licensed under the MIT License - see the LICENSE file for details. 